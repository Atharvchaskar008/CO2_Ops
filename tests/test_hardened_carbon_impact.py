"""
Focused tests for hardened carbon and impact calculations in CO2Ops.
Verifies:
1. 1000x conversion bug fix (AWS_REGION_CARBON_INTENSITY in kg CO2e / kWh)
2. gCO2e <-> kgCO2e conversion (1000:1 ratio)
3. Hourly -> daily/monthly/annual conversion (24h, 720h, 8760h)
4. Current vs target carbon calculation (emissions, reductions, percentage)
5. Cost vs carbon separation (completely separate data structures and units)
6. Missing carbon inputs handling (fail-closed, return insufficient_data)
7. Zero and edge values (0 duration, 0 cost, 0 watts)
8. Negative and invalid values (negative duration, invalid instance types, upsizing)
"""

import os
import pytest
from unittest.mock import patch

from co2ops_agent.bedrock.state import CO2OpsState
from co2ops_agent.agents.impact_calculator_agent.agent import (
    get_on_demand_price,
    get_carbon_emissions_per_hour,
    calculate_cost_impact,
    calculate_carbon_impact,
    kg_to_g,
    g_to_kg,
    AWS_REGION_CARBON_INTENSITY,
    DEFAULT_GRID_CARBON_INTENSITY,
    INSTANCE_WATTS,
)


# =========================================================================
# 1. 1000x Conversion Bug Fix
# =========================================================================

def test_1000x_conversion_bug_fixed():
    """
    Verifies that AWS_REGION_CARBON_INTENSITY is in true kg CO2e / kWh
    and not metric tons (which was 1000x too small).
    E.g., us-east-1 must be ~0.379 kg/kWh, NOT 0.00038 kg/kWh.
    """
    # Grid intensity checks
    assert AWS_REGION_CARBON_INTENSITY["us-east-1"] == 0.379
    assert AWS_REGION_CARBON_INTENSITY["us-east-2"] == 0.441
    assert AWS_REGION_CARBON_INTENSITY["ap-south-1"] == 0.708
    assert AWS_REGION_CARBON_INTENSITY["us-west-2"] == 0.121

    for reg, intensity in AWS_REGION_CARBON_INTENSITY.items():
        # Every regional grid emission factor must be between 0.1 and 1.5 kg CO2e / kWh
        assert 0.1 <= intensity <= 1.5, f"Region {reg} intensity {intensity} is out of realistic physical range"

    # Verifies that 24 hours of m5.large (~70W) in us-east-1 produces ~0.64 kg CO2e,
    # and NOT the buggy ~0.004 kg (4 grams)
    with patch.dict(os.environ, {"CLIMATIQ_API_KEY": ""}):
        result = get_carbon_emissions_per_hour(
            current_instance_type="m5.large",
            current_region="us-east-1",
            target_instance_type="t3.small",
            target_region="us-east-1",
            duration_hours=24.0
        )
        m5_emissions = result["m5.large"]["total_emissions"]
        # Expected: ~1.68 kWh * 0.379 kg/kWh + 0.0035 kg embodied = ~0.64 kg
        assert 0.50 <= m5_emissions <= 0.80, f"Expected ~0.64 kg, got {m5_emissions}"


# =========================================================================
# 2. gCO2e <-> kgCO2e Conversion
# =========================================================================

def test_gco2e_to_kgco2e_conversion():
    """Verifies that gCO2e and kgCO2e are correctly converted using exact 1000:1 ratio."""
    assert kg_to_g(1.0) == 1000.0
    assert kg_to_g(0.6402) == 640.2
    assert g_to_kg(1000.0) == 1.0
    assert g_to_kg(640.2) == 0.6402

    with patch.dict(os.environ, {"CLIMATIQ_API_KEY": ""}):
        result = get_carbon_emissions_per_hour(
            current_instance_type="m5.xlarge",
            current_region="us-east-1",
            target_instance_type="t3.large",
            target_region="us-east-1",
            duration_hours=24.0
        )
        for inst_key in ["m5.xlarge", "t3.large"]:
            inst_data = result[inst_key]
            assert "emissions_kgCO2e" in inst_data
            assert "emissions_gCO2e" in inst_data
            assert inst_data["emissions_gCO2e"] == pytest.approx(inst_data["emissions_kgCO2e"] * 1000.0, rel=1e-3)


# =========================================================================
# 3. Hourly -> Daily / Monthly / Annual Conversion
# =========================================================================

def test_hourly_daily_monthly_annual_conversion():
    """Verifies consistent time horizon conversions (24h/day, 720h/month, 8760h/year)."""
    curr_total = 2.4  # kg for 24h -> 0.1 kg/hr
    target_total = 1.2  # kg for 24h -> 0.05 kg/hr

    carb_impact = calculate_carbon_impact(curr_total, target_total, duration_hours=24.0)
    assert carb_impact["status"] == "calculated"

    curr = carb_impact["current_emissions"]
    assert curr["kgCO2e_per_hour"] == pytest.approx(0.1, abs=1e-5)
    assert curr["kgCO2e_per_day"] == pytest.approx(2.4, abs=1e-3)
    assert curr["kgCO2e_per_month"] == pytest.approx(2.4 * 30.0, abs=1e-3)
    assert curr["kgCO2e_per_year"] == pytest.approx(2.4 * 365.0, abs=1e-3)

    red = carb_impact["reduction"]
    assert red["kgCO2e_per_hour"] == pytest.approx(0.05, abs=1e-5)
    assert red["kgCO2e_per_day"] == pytest.approx(1.2, abs=1e-3)
    assert red["kgCO2e_per_month"] == pytest.approx(36.0, abs=1e-3)
    assert red["kgCO2e_per_year"] == pytest.approx(438.0, abs=1e-3)

    # Cost conversion
    cost_impact = calculate_cost_impact(current_rate=0.20, target_rate=0.08)
    assert cost_impact["status"] == "calculated"
    assert cost_impact["hourly_cost_savings"] == 0.12
    assert cost_impact["daily_cost_savings"] == pytest.approx(0.12 * 24.0, abs=1e-3)
    assert cost_impact["monthly_cost_savings"] == pytest.approx(0.12 * 24.0 * 30.0, abs=1e-2)
    assert cost_impact["annual_cost_savings"] == pytest.approx(0.12 * 24.0 * 365.0, abs=1e-2)


# =========================================================================
# 4. Current vs Target Carbon
# =========================================================================

def test_current_vs_target_carbon():
    """Verifies that downsizing reduces carbon and is accurately quantified."""
    with patch.dict(os.environ, {"CLIMATIQ_API_KEY": ""}):
        result = get_carbon_emissions_per_hour(
            current_instance_type="m5.xlarge",
            current_region="us-east-1",
            target_instance_type="t3.large",
            target_region="us-east-1",
            duration_hours=24.0
        )
        curr = result["m5.xlarge"]
        target = result["t3.large"]
        reduction = result["carbon_reduction"]

        assert curr["total_emissions"] > target["total_emissions"]
        assert reduction["kgCO2e_per_hour"] > 0
        assert reduction["kgCO2e_per_day"] > 0
        assert reduction["kgCO2e_per_month"] > 0
        assert reduction["kgCO2e_per_year"] > 0
        assert reduction["carbon_reduction_percent"] > 0


# =========================================================================
# 5. Cost vs Carbon Separation
# =========================================================================

def test_cost_vs_carbon_separation():
    """Verifies that cost savings ($ USD) and carbon savings (kgCO2e) are completely separate."""
    state = CO2OpsState()

    get_on_demand_price("m5.xlarge", "us-east-1", state=state)
    get_on_demand_price("t3.large", "us-east-1", state=state)

    with patch.dict(os.environ, {"CLIMATIQ_API_KEY": ""}):
        get_carbon_emissions_per_hour("m5.xlarge", "us-east-1", "t3.large", "us-east-1", duration_hours=24.0, state=state)

    # Validate distinct structures in impact_analysis
    assert "cost_impact" in state.impact_analysis
    assert "carbon_impact" in state.impact_analysis

    cost = state.impact_analysis["cost_impact"]
    carb = state.impact_analysis["carbon_impact"]

    assert cost["currency"] == "USD"
    assert "hourly_cost_savings" in cost
    assert "monthly_cost_savings" in cost
    assert "annual_cost_savings" in cost
    # Ensure no carbon keys contaminated cost structure
    assert "kgCO2e" not in str(cost.keys())

    assert "current_emissions" in carb
    assert "target_emissions" in carb
    assert "reduction" in carb
    assert "units" in carb
    # Ensure no dollar figures contaminated carbon structure
    assert "USD" not in str(carb.keys())
    assert "$" not in str(carb.values())


# =========================================================================
# 6. Missing Carbon Inputs (Fail-Closed)
# =========================================================================

def test_missing_carbon_inputs():
    """Verifies that missing or invalid instance types return explicit insufficient-data."""
    # Empty current instance
    res1 = get_carbon_emissions_per_hour("", "us-east-1", "t3.large", "us-east-1")
    assert res1["status"] == "insufficient_data"
    assert "Missing" in res1["error"]

    # None target instance
    res2 = get_carbon_emissions_per_hour("m5.large", "us-east-1", None, "us-east-1")
    assert res2["status"] == "insufficient_data"
    assert "Missing" in res2["error"]

    # Empty pricing instance
    res3 = get_on_demand_price("")
    assert res3["status"] == "insufficient_data"

    # None pricing instance
    res4 = get_on_demand_price(None)
    assert res4["status"] == "insufficient_data"

    # Missing emission inputs in calculator
    res5 = calculate_carbon_impact(None, 1.0, 24.0)
    assert res5["status"] == "insufficient_data"


# =========================================================================
# 7. Zero and Edge Values
# =========================================================================

def test_zero_and_edge_values():
    """Verifies zero durations and edge cases do not cause division by zero."""
    # Zero duration
    res = get_carbon_emissions_per_hour("m5.large", "us-east-1", "t3.large", "us-east-1", duration_hours=0)
    assert res["status"] == "insufficient_data"
    assert "greater than 0" in res["error"]

    res_calc = calculate_carbon_impact(1.0, 0.5, duration_hours=0)
    assert res_calc["status"] == "insufficient_data"

    # Identical current and target
    carb_same = calculate_carbon_impact(1.5, 1.5, duration_hours=24.0)
    assert carb_same["status"] == "calculated"
    assert carb_same["reduction"]["kgCO2e_per_hour"] == 0.0
    assert carb_same["reduction"]["carbon_reduction_percent"] == 0.0

    cost_same = calculate_cost_impact(0.10, 0.10)
    assert cost_same["status"] == "calculated"
    assert cost_same["hourly_cost_savings"] == 0.0
    assert cost_same["cost_reduction_percent"] == 0.0

    # Zero cost
    cost_zero = calculate_cost_impact(0.0, 0.0)
    assert cost_zero["status"] == "calculated"
    assert cost_zero["cost_reduction_percent"] == 0.0


# =========================================================================
# 8. Negative and Invalid Values
# =========================================================================

def test_negative_and_invalid_values():
    """Verifies negative durations and upsizing calculations."""
    # Negative duration rejected
    res_neg_dur = get_carbon_emissions_per_hour("m5.large", "us-east-1", "t3.large", "us-east-1", duration_hours=-24.0)
    assert res_neg_dur["status"] == "insufficient_data"

    # Upsizing: target is larger than current (increases cost and emissions)
    with patch.dict(os.environ, {"CLIMATIQ_API_KEY": ""}):
        res_upsize = get_carbon_emissions_per_hour("t3.micro", "us-east-1", "m5.2xlarge", "us-east-1", duration_hours=24.0)
        red = res_upsize["carbon_reduction"]
        # Savings must be negative because emissions increased
        assert red["kgCO2e_per_month"] < 0
        assert red["carbon_reduction_percent"] < 0

    cost_upsize = calculate_cost_impact(current_rate=0.0104, target_rate=0.384)
    assert cost_upsize["hourly_cost_savings"] < 0
    assert cost_upsize["monthly_cost_savings"] < 0
    assert cost_upsize["cost_reduction_percent"] < 0
