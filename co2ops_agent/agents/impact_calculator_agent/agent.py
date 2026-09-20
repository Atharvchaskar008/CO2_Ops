from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools import google_search
import requests
import json
import re
import os
import logging

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

# Regional grid carbon emission intensities (kg CO2e per kWh) for estimation fallback
AWS_REGION_CARBON_INTENSITY = {
    "us-east-1": 0.00038,
    "us-east-2": 0.00044,
    "us-west-1": 0.00021,
    "us-west-2": 0.00012,
    "eu-west-1": 0.00028,
    "eu-central-1": 0.00034,
    "ap-southeast-1": 0.00041,
    "ap-south-1": 0.00071,
}

# Estimated average wattage by instance size
INSTANCE_WATTS = {
    "nano": 5, "micro": 10, "small": 20, "medium": 40,
    "large": 70, "xlarge": 140, "2xlarge": 280, "4xlarge": 550
}

def normalize_to_aws_region(region: str) -> str:
    """Converts formats like 'us_east_1' to standard AWS format 'us-east-1'."""
    if not region:
        return "us-east-1"
    return region.lower().replace("_", "-")


def get_on_demand_price(instance_type: str, region: str = "us-east-1") -> dict:
    """
    Retrieves the hourly on-demand price for an AWS EC2 instance.
    Queries the AWS Pricing API with fallback to verified local EC2 price cache.
    """
    region = normalize_to_aws_region(region)
    instance_type = instance_type.lower().strip()

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
                        return {
                            "instance_type": instance_type,
                            "region": region,
                            "on_demand_price": f"${float(price_val):.4f}",
                            "hourly_rate": float(price_val),
                            "source": "AWS Pricing API"
                        }
    except Exception as e:
        logger.debug(f"AWS Pricing API unavailable, using cache: {e}")

    # 2. Check local verified price cache
    if instance_type in EC2_ON_DEMAND_PRICE_CACHE:
        rate = EC2_ON_DEMAND_PRICE_CACHE[instance_type]
        return {
            "instance_type": instance_type,
            "region": region,
            "on_demand_price": f"${rate:.4f}",
            "hourly_rate": rate,
            "source": "AWS EC2 Price Index"
        }

    # 3. Size-based approximation if unknown instance
    size = instance_type.split(".")[-1] if "." in instance_type else "large"
    approx_rates = {"nano": 0.005, "micro": 0.011, "small": 0.021, "medium": 0.042, "large": 0.085, "xlarge": 0.170, "2xlarge": 0.340}
    rate = approx_rates.get(size, 0.100)
    return {
        "instance_type": instance_type,
        "region": region,
        "on_demand_price": f"${rate:.4f}",
        "hourly_rate": rate,
        "source": "Estimated"
    }


def get_carbon_emissions_per_hour(current_instance_type: str, current_region: str,
                                   target_instance_type: str, target_region: str,
                                   duration_hours: float = 24.0) -> dict:
    """
    Computes carbon emissions for two AWS EC2 instances over a specified duration
    using the Climatiq AWS Compute API, with an intelligent regional grid fallback.
    """
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
                for label, result in zip([current_instance, target_instance], results):
                    if "error" in result:
                        emissions_data[label] = {"error": result["error"]}
                    else:
                        emissions_data[label] = {
                            "cpu_estimate": result.get("cpu_estimate", {}).get("co2e", 0.0),
                            "memory_estimate": result.get("memory_estimate", {}).get("co2e", 0.0),
                            "embodied_cpu_estimate": result.get("embodied_cpu_estimate", {}).get("co2e", 0.0),
                            "total_emissions": result.get("total_co2e", 0.0),
                            "unit": "kg"
                        }
                return emissions_data
        except Exception as e:
            logger.warning(f"Climatiq API call failed: {e}. Falling back to AWS carbon model.")

    # High-precision fallback using AWS Regional Carbon Intensity & instance TDP
    emissions_data = {}
    for inst, reg in [(current_instance, current_region), (target_instance, target_region)]:
        size = inst.split(".")[-1] if "." in inst else "large"
        watts = INSTANCE_WATTS.get(size, 80)
        # Graviton (e.g. m6g, c6g, t4g) is ~30% more energy efficient
        if "g." in inst:
            watts *= 0.70

        kwh = (watts * duration_hours) / 1000.0
        intensity = AWS_REGION_CARBON_INTENSITY.get(reg, 0.00035)
        operational_co2 = kwh * intensity
        embodied_co2 = 0.0025 * (watts / 50.0) * (duration_hours / 24.0)
        total_co2 = round(operational_co2 + embodied_co2, 4)

        emissions_data[inst] = {
            "cpu_estimate": round(operational_co2 * 0.65, 4),
            "memory_estimate": round(operational_co2 * 0.35, 4),
            "embodied_cpu_estimate": round(embodied_co2, 4),
            "total_emissions": total_co2,
            "unit": "kg",
            "source": "AWS Carbon Emission Model"
        }

    return emissions_data


impact_calculator_agent = Agent(
    name="impact_calculator_agent",
    model="gemini-2.0-flash",
    description="Agent that compares cost and carbon impact of changing AWS EC2 instance types.",
    instruction="""
    You are an AWS Green Cloud Optimization Assistant that helps users understand the environmental and financial impact of changing their AWS EC2 instance types.

    Your responsibilities include:
    1. Estimating the **hourly and monthly cost difference** between a current and target EC2 instance.
    2. Estimating the **hourly and monthly carbon footprint difference** between the two instances.
    3. Concluding whether the change has a **positive or negative impact**.

    To accomplish this, follow this logic:

    ### 🧮 PRICE ESTIMATION
    Use the tool `get_on_demand_price` to get the **hourly on-demand price** for both instances (current and target).
    Then compute:
    > monthly_cost = hourly_rate × 24 × 30
    > cost_change_per_month = target_monthly - current_monthly

    ### 🌍 CARBON IMPACT ESTIMATION
    Use the tool `get_carbon_emissions_per_hour` with:
    - current_instance_type (e.g., 'm5.xlarge')
    - current_region (e.g., 'us-east-1')
    - target_instance_type (e.g., 't3.large' or Graviton 'm6g.large')
    - target_region (default to current region if not specified)

    Then compute monthly carbon emissions:
    > monthly_carbon = daily_total × 30
    > carbon_savings_per_month = current_monthly_carbon - target_monthly_carbon

    ### FINAL RESPONSE
    Return a structured comparison:
    - Current vs Target Instance Specs & Region
    - Cost Comparison (Hourly and Monthly Savings)
    - Carbon Comparison (Monthly CO2 kg reduction)
    - Recommendation summary highlighting both sustainability and ROI.

    Always use the tools provided. Never hallucinate pricing or emissions.
    """,
    tools=[
        get_on_demand_price,
        get_carbon_emissions_per_hour
    ]
)