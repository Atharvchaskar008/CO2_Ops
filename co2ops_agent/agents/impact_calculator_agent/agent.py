import requests
import json
import re
import os
import logging
from typing import Optional, Dict, Any

from co2ops_agent.bedrock.agent import BedrockAgent
from co2ops_agent.bedrock.state import CO2OpsState

logger = logging.getLogger(__name__)

# Standard AWS EC2 On-Demand hourly prices ($/hr) for common instance types (us-east-1 reference)
# Serves as instant local cache and fallback when AWS Pricing API credentials are unavailable
EC2_ON_DEMAND_PRICE_CACHE = {
    "t3.nano": 0.0052,
    "t3.micro": 0.0104,
    "t3.small": 0.0208,
    "t3.medium": 0.0416,
    "t3.large": 0.0832,
    "t3.xlarge": 0.1664,
    "t3.2xlarge": 0.3328,
    "t4g.nano": 0.0042,
    "t4g.micro": 0.0084,
    "t4g.small": 0.0168,
    "t4g.medium": 0.0336,
    "t4g.large": 0.0672,
    "t4g.xlarge": 0.1344,
    "m5.large": 0.096,
    "m5.xlarge": 0.192,
    "m5.2xlarge": 0.384,
    "m5.4xlarge": 0.768,
    "m6g.large": 0.077,
    "m6g.xlarge": 0.154,
    "m6g.2xlarge": 0.308,
    "c5.large": 0.085,
    "c5.xlarge": 0.170,
    "c5.2xlarge": 0.340,
    "c5.4xlarge": 0.680,
    "c6g.large": 0.068,
    "c6g.xlarge": 0.136,
    "r5.large": 0.126,
    "r5.xlarge": 0.252,
    "r5.2xlarge": 0.504,
    "r6g.large": 0.101,
    "r6g.xlarge": 0.202,
}

# Regional grid carbon emission intensities (kg CO2e per kWh) for estimation fallback.
# Fixed: Values are in true kg CO2e / kWh (previously had 1000x unit error by storing metric tons / kWh).
# Sources: EPA eGRID, European Environment Agency (EEA), CEA India, and regional utility benchmarks.
AWS_REGION_CARBON_INTENSITY = {
    "us-east-1": 0.379,       # Virginia (PJM East): ~379 gCO2e/kWh = 0.379 kgCO2e/kWh
    "us-east-2": 0.441,       # Ohio (PJM West): ~441 gCO2e/kWh = 0.441 kgCO2e/kWh
    "us-west-1": 0.210,       # California (CAISO): ~210 gCO2e/kWh = 0.210 kgCO2e/kWh
    "us-west-2": 0.121,       # Oregon (NW hydro): ~121 gCO2e/kWh = 0.121 kgCO2e/kWh
    "eu-west-1": 0.278,       # Ireland: ~278 gCO2e/kWh = 0.278 kgCO2e/kWh
    "eu-central-1": 0.338,    # Frankfurt: ~338 gCO2e/kWh = 0.338 kgCO2e/kWh
    "ap-southeast-1": 0.410,  # Singapore: ~410 gCO2e/kWh = 0.410 kgCO2e/kWh
    "ap-south-1": 0.708,      # Mumbai: ~708 gCO2e/kWh = 0.708 kgCO2e/kWh
}
DEFAULT_GRID_CARBON_INTENSITY = 0.350  # kg CO2e / kWh fallback

# Estimated average wattage by instance size
INSTANCE_WATTS = {
    "nano": 5, "micro": 10, "small": 20, "medium": 40,
    "large": 70, "xlarge": 140, "2xlarge": 280, "4xlarge": 550,
    "8xlarge": 1100, "12xlarge": 1650, "16xlarge": 2200,
    "24xlarge": 3300, "32xlarge": 4400,
}


def normalize_to_aws_region(region: str) -> str:
    """Converts formats like 'us_east_1' to standard AWS format 'us-east-1'."""
    if not region or not isinstance(region, str):
        return "us-east-1"
    return region.lower().strip().replace("_", "-")


def kg_to_g(kg: float) -> float:
    """Converts kg CO2e to g CO2e (1 kg = 1000 g)."""
    return round(float(kg) * 1000.0, 4)


def g_to_kg(g: float) -> float:
    """Converts g CO2e to kg CO2e (1000 g = 1 kg)."""
    return round(float(g) / 1000.0, 6)


def calculate_cost_impact(current_rate: float, target_rate: float) -> dict:
    """
    Deterministically computes hourly, daily, monthly, and annual cost savings.
    Keeps cost impact completely separate from carbon metrics.
    """
    if current_rate is None or target_rate is None:
        return {"status": "insufficient_data", "error": "Missing price rates"}

    hourly_savings = round(float(current_rate) - float(target_rate), 4)
    daily_savings = round(hourly_savings * 24.0, 4)
    monthly_savings = round(hourly_savings * 24.0 * 30.0, 2)
    annual_savings = round(hourly_savings * 24.0 * 365.0, 2)
    percent_reduction = round(((float(current_rate) - float(target_rate)) / float(current_rate)) * 100.0, 2) if float(current_rate) > 0 else 0.0

    return {
        "currency": "USD",
        "current_hourly_cost": round(float(current_rate), 4),
        "target_hourly_cost": round(float(target_rate), 4),
        "hourly_cost_savings": hourly_savings,
        "daily_cost_savings": daily_savings,
        "monthly_cost_savings": monthly_savings,
        "annual_cost_savings": annual_savings,
        "cost_reduction_percent": percent_reduction,
        "status": "calculated"
    }


def calculate_carbon_impact(curr_total_co2: float, target_total_co2: float, duration_hours: float) -> dict:
    """
    Deterministically computes hourly, daily, monthly, and annual carbon emissions
    and reductions for both current and target instances with explicit unit labelling.
    """
    if duration_hours is None or duration_hours <= 0:
        return {
            "status": "insufficient_data",
            "error": "duration_hours must be a positive number"
        }
    if curr_total_co2 is None or target_total_co2 is None:
        return {
            "status": "insufficient_data",
            "error": "Missing total emissions data"
        }

    curr_total = float(curr_total_co2)
    target_total = float(target_total_co2)

    curr_hourly = curr_total / duration_hours
    curr_daily = curr_hourly * 24.0
    curr_monthly = curr_daily * 30.0
    curr_annual = curr_daily * 365.0

    target_hourly = target_total / duration_hours
    target_daily = target_hourly * 24.0
    target_monthly = target_daily * 30.0
    target_annual = target_daily * 365.0

    hourly_red = curr_hourly - target_hourly
    daily_red = curr_daily - target_daily
    monthly_red = curr_monthly - target_monthly
    annual_red = curr_annual - target_annual

    pct_red = round(((curr_hourly - target_hourly) / curr_hourly) * 100.0, 2) if curr_hourly > 0 else 0.0

    return {
        "current_emissions": {
            "kgCO2e_per_hour": round(curr_hourly, 6),
            "kgCO2e_per_day": round(curr_daily, 4),
            "kgCO2e_per_month": round(curr_monthly, 4),
            "kgCO2e_per_year": round(curr_annual, 4),
            "gCO2e_per_hour": round(curr_hourly * 1000.0, 4),
            "gCO2e_per_day": round(curr_daily * 1000.0, 2),
            "gCO2e_per_month": round(curr_monthly * 1000.0, 2),
            "gCO2e_per_year": round(curr_annual * 1000.0, 2),
            "total_for_duration_kgCO2e": round(curr_total, 4),
            "total_for_duration_gCO2e": round(curr_total * 1000.0, 2),
            "duration_hours": duration_hours,
            "unit": "kgCO2e"
        },
        "target_emissions": {
            "kgCO2e_per_hour": round(target_hourly, 6),
            "kgCO2e_per_day": round(target_daily, 4),
            "kgCO2e_per_month": round(target_monthly, 4),
            "kgCO2e_per_year": round(target_annual, 4),
            "gCO2e_per_hour": round(target_hourly * 1000.0, 4),
            "gCO2e_per_day": round(target_daily * 1000.0, 2),
            "gCO2e_per_month": round(target_monthly * 1000.0, 2),
            "gCO2e_per_year": round(target_annual * 1000.0, 2),
            "total_for_duration_kgCO2e": round(target_total, 4),
            "total_for_duration_gCO2e": round(target_total * 1000.0, 2),
            "duration_hours": duration_hours,
            "unit": "kgCO2e"
        },
        "reduction": {
            "kgCO2e_per_hour": round(hourly_red, 6),
            "kgCO2e_per_day": round(daily_red, 4),
            "kgCO2e_per_month": round(monthly_red, 4),
            "kgCO2e_per_year": round(annual_red, 4),
            "gCO2e_per_hour": round(hourly_red * 1000.0, 4),
            "gCO2e_per_day": round(daily_red * 1000.0, 2),
            "gCO2e_per_month": round(monthly_red * 1000.0, 2),
            "gCO2e_per_year": round(annual_red * 1000.0, 2),
            "carbon_reduction_percent": pct_red
        },
        "units": {
            "hourly": "kgCO2e/hour",
            "daily": "kgCO2e/day",
            "monthly": "kgCO2e/month",
            "annual": "kgCO2e/year",
            "g_hourly": "gCO2e/hour",
            "g_daily": "gCO2e/day",
            "g_monthly": "gCO2e/month",
            "g_annual": "gCO2e/year",
            "mass": "kgCO2e"
        },
        "status": "calculated"
    }


def get_on_demand_price(instance_type: str, region: str = "us-east-1", state: Optional[CO2OpsState] = None) -> dict:
    """
    Retrieves the hourly on-demand price for an AWS EC2 instance.
    Queries the AWS Pricing API with fallback to verified local EC2 price cache.
    Returns explicit insufficient-data result on invalid/missing input.
    """
    if not instance_type or not isinstance(instance_type, str) or not instance_type.strip():
        return {
            "status": "insufficient_data",
            "error": "Missing or invalid instance_type",
            "instance_type": str(instance_type or "")
        }

    region = normalize_to_aws_region(region)
    instance_type = instance_type.lower().strip()

    result = None

    # 1. Attempt AWS Pricing API via boto3 if configured
    try:
        import boto3
        pricing = boto3.client("pricing", region_name="us-east-1")
        response = pricing.get_products(
            ServiceCode="AmazonEC2",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
                {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
                {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
                {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"}
            ],
            MaxResults=1
        )
        for price_str in response.get("PriceList", []):
            price_data = json.loads(price_str)
            terms = price_data.get("terms", {}).get("OnDemand", {})
            for term in terms.values():
                for price_dim in term.get("priceDimensions", {}).values():
                    price_val = price_dim.get("pricePerUnit", {}).get("USD")
                    if price_val:
                        val = float(price_val)
                        if val < 0:
                            return {"status": "insufficient_data", "error": "Negative price returned by AWS"}
                        result = {
                            "instance_type": instance_type,
                            "region": region,
                            "on_demand_price": f"${val:.4f}",
                            "hourly_rate": val,
                            "currency": "USD",
                            "source": "AWS Pricing API"
                        }
                        break
                if result:
                    break
            if result:
                break
    except Exception as e:
        logger.debug(f"AWS Pricing API unavailable, using cache: {e}")

    # 2. Check local verified price cache
    if not result and instance_type in EC2_ON_DEMAND_PRICE_CACHE:
        rate = EC2_ON_DEMAND_PRICE_CACHE[instance_type]
        result = {
            "instance_type": instance_type,
            "region": region,
            "on_demand_price": f"${rate:.4f}",
            "hourly_rate": rate,
            "currency": "USD",
            "source": "AWS EC2 Price Index"
        }

    # 3. Size-based approximation if unknown instance
    if not result:
        size = instance_type.split(".")[-1] if "." in instance_type else "large"
        approx_rates = {"nano": 0.005, "micro": 0.011, "small": 0.021, "medium": 0.042, "large": 0.085, "xlarge": 0.170, "2xlarge": 0.340}
        rate = approx_rates.get(size, 0.100)
        result = {
            "instance_type": instance_type,
            "region": region,
            "on_demand_price": f"${rate:.4f}",
            "hourly_rate": rate,
            "currency": "USD",
            "source": "Estimated"
        }

    # Store in CO2OpsState if provided
    if state is not None and result:
        if not isinstance(state.impact_analysis, dict):
            state.impact_analysis = {}
        pricing_cache = state.impact_analysis.setdefault("pricing", {})
        pricing_cache[instance_type] = result

        # If current and target instances are recorded, update cost impact
        curr_inst = state.impact_analysis.get("current_instance")
        tgt_inst = state.impact_analysis.get("target_instance")
        if curr_inst and tgt_inst and curr_inst in pricing_cache and tgt_inst in pricing_cache:
            curr_rate = pricing_cache[curr_inst].get("hourly_rate")
            tgt_rate = pricing_cache[tgt_inst].get("hourly_rate")
            if curr_rate is not None and tgt_rate is not None:
                cost_impact = calculate_cost_impact(curr_rate, tgt_rate)
                state.impact_analysis["cost_impact"] = cost_impact
                state.impact_analysis["hourly_cost_savings"] = cost_impact["hourly_cost_savings"]
                state.impact_analysis["daily_cost_savings"] = cost_impact["daily_cost_savings"]
                state.impact_analysis["monthly_cost_savings"] = cost_impact["monthly_cost_savings"]
                state.impact_analysis["annual_cost_savings"] = cost_impact["annual_cost_savings"]

    return result


def get_carbon_emissions_per_hour(current_instance_type: str, current_region: str,
                                   target_instance_type: str, target_region: str,
                                   duration_hours: float = 24.0,
                                   state: Optional[CO2OpsState] = None) -> dict:
    """
    Computes carbon emissions for two AWS EC2 instances over a specified duration
    using the Climatiq AWS Compute API, with an intelligent regional grid fallback.
    Returns explicit insufficient-data result when required inputs are missing or invalid.
    """
    # 1. Input Validation - fail closed if inputs are missing or invalid
    if not current_instance_type or not isinstance(current_instance_type, str) or not current_instance_type.strip():
        return {
            "status": "insufficient_data",
            "error": "Missing or invalid current_instance_type",
            "current_instance": str(current_instance_type or ""),
            "target_instance": str(target_instance_type or "")
        }
    if not target_instance_type or not isinstance(target_instance_type, str) or not target_instance_type.strip():
        return {
            "status": "insufficient_data",
            "error": "Missing or invalid target_instance_type",
            "current_instance": str(current_instance_type or ""),
            "target_instance": str(target_instance_type or "")
        }
    if duration_hours is None or not isinstance(duration_hours, (int, float)):
        return {
            "status": "insufficient_data",
            "error": "duration_hours must be a numeric value",
            "duration_hours": duration_hours
        }
    if duration_hours <= 0:
        return {
            "status": "insufficient_data",
            "error": "duration_hours must be greater than 0",
            "duration_hours": duration_hours
        }

    target_region = normalize_to_aws_region(target_region)
    current_region = normalize_to_aws_region(current_region)
    current_instance = current_instance_type.lower().strip()
    target_instance = target_instance_type.lower().strip()

    climatiq_key = os.getenv("CLIMATIQ_API_KEY", "").strip()

    if climatiq_key:
        endpoint = "https://api.climatiq.io/compute/v1/aws/instance/batch"
        payload = [
            {
                "region": current_region,
                "instance": current_instance,
                "duration": duration_hours,
                "duration_unit": "h"
            },
            {
                "region": target_region,
                "instance": target_instance,
                "duration": duration_hours,
                "duration_unit": "h"
            }
        ]
        headers = {
            "Authorization": f"Bearer {climatiq_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                results = response.json().get("results", [])
                emissions_data = {}
                records = []
                for label, reg, result in zip([current_instance, target_instance], [current_region, target_region], results):
                    if "error" in result:
                        rec = {"error": result["error"], "status": "error"}
                        emissions_data[label] = rec
                        records.append(rec)
                    else:
                        tot_kg = float(result.get("total_co2e", 0.0))
                        rec = {
                            "cpu_estimate": result.get("cpu_estimate", {}).get("co2e", 0.0),
                            "memory_estimate": result.get("memory_estimate", {}).get("co2e", 0.0),
                            "embodied_cpu_estimate": result.get("embodied_cpu_estimate", {}).get("co2e", 0.0),
                            "total_emissions": tot_kg,
                            "unit": "kg",
                            "unit_label": "kgCO2e",
                            "emissions_kgCO2e": tot_kg,
                            "emissions_gCO2e": kg_to_g(tot_kg),
                            "kgCO2e_per_hour": round(tot_kg / duration_hours, 6),
                            "kgCO2e_per_day": round(tot_kg * (24.0 / duration_hours), 4),
                            "kgCO2e_per_month": round(tot_kg * (24.0 / duration_hours) * 30.0, 4),
                            "kgCO2e_per_year": round(tot_kg * (24.0 / duration_hours) * 365.0, 4),
                            "gCO2e_per_hour": round((tot_kg / duration_hours) * 1000.0, 4),
                            "gCO2e_per_day": round(tot_kg * (24.0 / duration_hours) * 1000.0, 2),
                            "gCO2e_per_month": round(tot_kg * (24.0 / duration_hours) * 30.0 * 1000.0, 2),
                            "gCO2e_per_year": round(tot_kg * (24.0 / duration_hours) * 365.0 * 1000.0, 2),
                            "source": "Climatiq API",
                            "instance_type": label,
                            "region": reg
                        }
                        emissions_data[label] = rec
                        records.append(rec)

                emissions_data["current"] = records[0]
                emissions_data["target"] = records[1]
                if len(records) == 2 and "total_emissions" in records[0] and "total_emissions" in records[1]:
                    impact_calc = calculate_carbon_impact(records[0]["total_emissions"], records[1]["total_emissions"], duration_hours)
                    emissions_data["carbon_reduction"] = impact_calc["reduction"]
                    emissions_data["units"] = impact_calc["units"]

                if state is not None:
                    _record_emissions_in_state(state, emissions_data, current_instance, target_instance, duration_hours)
                return emissions_data
        except Exception as e:
            logger.warning(f"Climatiq API call failed: {e}. Falling back to AWS carbon model.")

    # High-precision fallback using AWS Regional Carbon Intensity & instance TDP
    # Grid intensities are in true kg CO2e / kWh (e.g. 0.379 kg/kWh for us-east-1)
    emissions_data = {}
    records = []
    for inst, reg in [(current_instance, current_region), (target_instance, target_region)]:
        size = inst.split(".")[-1] if "." in inst else "large"
        watts = INSTANCE_WATTS.get(size, 80)
        # Graviton (e.g. m6g, c6g, t4g) is ~30% more energy efficient
        if "g." in inst:
            watts *= 0.70

        kwh = (watts * duration_hours) / 1000.0
        intensity = AWS_REGION_CARBON_INTENSITY.get(reg, DEFAULT_GRID_CARBON_INTENSITY)
        operational_co2 = kwh * intensity
        embodied_co2 = 0.0025 * (watts / 50.0) * (duration_hours / 24.0)
        total_co2 = round(operational_co2 + embodied_co2, 4)

        hourly_kg = total_co2 / duration_hours
        daily_kg = hourly_kg * 24.0
        monthly_kg = daily_kg * 30.0
        annual_kg = daily_kg * 365.0

        rec = {
            "cpu_estimate": round(operational_co2 * 0.65, 4),
            "memory_estimate": round(operational_co2 * 0.35, 4),
            "embodied_cpu_estimate": round(embodied_co2, 4),
            "total_emissions": total_co2,
            "unit": "kg",
            "unit_label": "kgCO2e",
            "emissions_kgCO2e": total_co2,
            "emissions_gCO2e": kg_to_g(total_co2),
            "kgCO2e_per_hour": round(hourly_kg, 6),
            "kgCO2e_per_day": round(daily_kg, 4),
            "kgCO2e_per_month": round(monthly_kg, 4),
            "kgCO2e_per_year": round(annual_kg, 4),
            "gCO2e_per_hour": round(hourly_kg * 1000.0, 4),
            "gCO2e_per_day": round(daily_kg * 1000.0, 2),
            "gCO2e_per_month": round(monthly_kg * 1000.0, 2),
            "gCO2e_per_year": round(annual_kg * 1000.0, 2),
            "source": "AWS Carbon Emission Model",
            "instance_type": inst,
            "region": reg
        }
        emissions_data[inst] = rec
        records.append(rec)

    emissions_data["current"] = records[0]
    emissions_data["target"] = records[1]
    if len(records) == 2 and "total_emissions" in records[0] and "total_emissions" in records[1]:
        impact_calc = calculate_carbon_impact(records[0]["total_emissions"], records[1]["total_emissions"], duration_hours)
        emissions_data["carbon_reduction"] = impact_calc["reduction"]
        emissions_data["units"] = impact_calc["units"]

    if state is not None:
        _record_emissions_in_state(state, emissions_data, current_instance, target_instance, duration_hours)

    return emissions_data


def _record_emissions_in_state(state: CO2OpsState, emissions_data: dict, current_instance: str, target_instance: str, duration_hours: float):
    """Internal helper to store emissions data and calculate separate cost and carbon metrics in CO2OpsState."""
    if not isinstance(state.impact_analysis, dict):
        state.impact_analysis = {}

    state.impact_analysis["carbon_emissions"] = emissions_data
    state.impact_analysis["duration_hours"] = duration_hours
    state.impact_analysis["current_instance"] = current_instance
    state.impact_analysis["target_instance"] = target_instance

    # Compute carbon reduction if records are present
    curr_rec = emissions_data.get("current") or emissions_data.get(current_instance)
    target_rec = emissions_data.get("target") or emissions_data.get(target_instance)

    if curr_rec and target_rec and "total_emissions" in curr_rec and "total_emissions" in target_rec:
        curr_co2 = curr_rec["total_emissions"]
        target_co2 = target_rec["total_emissions"]
        if duration_hours > 0 and isinstance(curr_co2, (int, float)) and isinstance(target_co2, (int, float)):
            carbon_impact = calculate_carbon_impact(curr_co2, target_co2, duration_hours)
            state.impact_analysis["carbon_impact"] = carbon_impact

            # Preserve top-level fields for backwards-compatibility
            red = carbon_impact["reduction"]
            state.impact_analysis["monthly_carbon_savings_kg"] = red["kgCO2e_per_month"]
            state.impact_analysis["annual_carbon_savings_kg"] = red["kgCO2e_per_year"]
            state.impact_analysis["daily_carbon_savings_kg"] = red["kgCO2e_per_day"]
            state.impact_analysis["hourly_carbon_savings_kg"] = red["kgCO2e_per_hour"]

    # Compute cost savings if both pricing entries are present
    pricing = state.impact_analysis.get("pricing", {})
    if current_instance in pricing and target_instance in pricing:
        curr_rate = pricing[current_instance].get("hourly_rate")
        target_rate = pricing[target_instance].get("hourly_rate")
        if curr_rate is not None and target_rate is not None:
            cost_impact = calculate_cost_impact(curr_rate, target_rate)
            state.impact_analysis["cost_impact"] = cost_impact
            state.impact_analysis["hourly_cost_savings"] = cost_impact["hourly_cost_savings"]
            state.impact_analysis["daily_cost_savings"] = cost_impact["daily_cost_savings"]
            state.impact_analysis["monthly_cost_savings"] = cost_impact["monthly_cost_savings"]
            state.impact_analysis["annual_cost_savings"] = cost_impact["annual_cost_savings"]


impact_calculator_agent = BedrockAgent(
    name="impact_calculator_agent",
    description="Agent that compares cost and carbon impact of changing AWS EC2 instance types.",
    system_instruction="""
    You are an AWS Green Cloud Optimization Assistant that helps users understand the environmental and financial impact of changing their AWS EC2 instance types.

    Context from pipeline state:
    Current Recommendations: {final_recommendations}
    Forecast Data: {forecast_data}

    Your responsibilities include:
    1. Estimating the **hourly, daily, monthly, and annual cost difference** between a current and target EC2 instance.
    2. Estimating the **hourly, daily, monthly, and annual carbon footprint difference** between the two instances.
    3. Concluding whether the change has a **positive or negative impact**.

    IMPORTANT:
    - Do NOT perform arithmetic or invent numbers yourself. Calculations are deterministic.
    - Always call the tools `get_on_demand_price` and `get_carbon_emissions_per_hour`.
    - Report the exact values returned by the tools.
    - Keep cost metrics (in USD) and carbon metrics (in kgCO2e and gCO2e) completely distinct and separate.

    To accomplish this, follow this logic:

    ### 🧮 PRICE ESTIMATION
    Use the tool `get_on_demand_price` to get the **hourly on-demand price** for both instances (current and target).
    The tool will automatically calculate hourly, daily, monthly, and annual cost savings and store them into pipeline state.

    ### 🌍 CARBON IMPACT ESTIMATION
    Use the tool `get_carbon_emissions_per_hour` with:
    - current_instance_type (e.g., 'm5.xlarge')
    - current_region (e.g., 'us-east-1')
    - target_instance_type (e.g., 't3.large' or Graviton 'm6g.large')
    - target_region (default to current region if not specified)
    The tool will automatically calculate hourly, daily, monthly, and annual carbon emissions and reductions, storing both kgCO2e and gCO2e metrics into state.

    ### FINAL RESPONSE
    Return a structured comparison:
    - Current vs Target Instance Specs & Region
    - Cost Comparison:
      - Current vs Target Hourly Cost ($/hr)
      - Hourly, Monthly, and Annual Cost Savings ($)
    - Carbon Comparison:
      - Current vs Target Emissions (kgCO2e/hour, kgCO2e/day, kgCO2e/month, kgCO2e/year)
      - Carbon Reduction (kgCO2e and gCO2e across hourly, daily, monthly, annual)
      - Reduction percentage
    - Recommendation summary highlighting both sustainability and ROI.

    Always use the tools provided. Never hallucinate pricing or emissions.
    """,
    tools=[
        get_on_demand_price,
        get_carbon_emissions_per_hour
    ],
    input_state_key="forecast_data",
    output_state_key="impact_analysis"
)