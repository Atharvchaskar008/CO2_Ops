import os
import pytest
from unittest.mock import patch, MagicMock
from co2ops_agent.agents.impact_calculator_agent.agent import (
    get_carbon_emissions_per_hour,
    AWS_REGION_CARBON_INTENSITY
)

def test_carbon_emissions_fallback_model():
    with patch.dict(os.environ, {"CLIMATIQ_API_KEY": ""}):
        result = get_carbon_emissions_per_hour(
            current_instance_type="m5.2xlarge",
            current_region="us-east-1",
            target_instance_type="m5.large",
            target_region="us-east-1",
            duration_hours=24.0
        )
        assert "m5.2xlarge" in result
        assert "m5.large" in result
        # Larger instance should produce more emissions than downsized instance
        assert result["m5.2xlarge"]["total_emissions"] > result["m5.large"]["total_emissions"]
        assert result["m5.large"]["unit"] == "kg"
        assert result["m5.large"]["source"] == "AWS Carbon Emission Model"

def test_carbon_emissions_graviton_efficiency():
    with patch.dict(os.environ, {"CLIMATIQ_API_KEY": ""}):
        # m6g.large (Graviton) vs m5.large (x86) in same region
        res = get_carbon_emissions_per_hour(
            current_instance_type="m5.large",
            current_region="us-east-1",
            target_instance_type="m6g.large",
            target_region="us-east-1",
            duration_hours=24.0
        )
        # Graviton has 30% lower wattage profile
        assert res["m6g.large"]["total_emissions"] < res["m5.large"]["total_emissions"]

def test_carbon_emissions_regional_grid_variation():
    with patch.dict(os.environ, {"CLIMATIQ_API_KEY": ""}):
        # us-west-2 (clean hydro) vs ap-south-1 (coal-heavy)
        res = get_carbon_emissions_per_hour(
            current_instance_type="m5.large",
            current_region="ap-south-1",
            target_instance_type="m5.large",
            target_region="us-west-2",
            duration_hours=24.0
        )
        assert res["m5.large"]["total_emissions"] > 0

@patch("requests.post")
def test_carbon_emissions_climatiq_api_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {
                "cpu_estimate": {"co2e": 0.45},
                "memory_estimate": {"co2e": 0.12},
                "embodied_cpu_estimate": {"co2e": 0.08},
                "total_co2e": 0.65
            },
            {
                "cpu_estimate": {"co2e": 0.18},
                "memory_estimate": {"co2e": 0.05},
                "embodied_cpu_estimate": {"co2e": 0.03},
                "total_co2e": 0.26
            }
        ]
    }
    mock_post.return_value = mock_resp

    with patch.dict(os.environ, {"CLIMATIQ_API_KEY": "fake_climatiq_key"}):
        result = get_carbon_emissions_per_hour(
            current_instance_type="c5.2xlarge",
            current_region="us-east-1",
            target_instance_type="c5.large",
            target_region="us-east-1",
            duration_hours=24.0
        )
        assert result["c5.2xlarge"]["total_emissions"] == 0.65
        assert result["c5.large"]["total_emissions"] == 0.26
        assert result["c5.large"]["unit"] == "kg"
