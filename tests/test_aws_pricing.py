import pytest
import json
from unittest.mock import patch, MagicMock
from co2ops_agent.agents.impact_calculator_agent.agent import (
    get_on_demand_price,
    normalize_to_aws_region,
    EC2_ON_DEMAND_PRICE_CACHE
)

def test_normalize_to_aws_region():
    assert normalize_to_aws_region("us_east_1") == "us-east-1"
    assert normalize_to_aws_region("EU_WEST_1") == "eu-west-1"
    assert normalize_to_aws_region("") == "us-east-1"
    assert normalize_to_aws_region("ap-south-1") == "ap-south-1"

def test_get_on_demand_price_from_cache():
    result = get_on_demand_price("t3.micro", "us-east-1")
    assert result["instance_type"] == "t3.micro"
    assert result["region"] == "us-east-1"
    assert result["hourly_rate"] == 0.0104
    assert result["on_demand_price"] == "$0.0104"
    assert "source" in result

def test_get_on_demand_price_m5_large():
    result = get_on_demand_price("m5.large")
    assert result["hourly_rate"] == 0.096
    assert result["on_demand_price"] == "$0.0960"

def test_get_on_demand_price_unknown_instance():
    result = get_on_demand_price("custom.mega.2xlarge")
    assert result["hourly_rate"] > 0
    assert result["source"] == "Estimated"

@patch("boto3.client")
def test_get_on_demand_price_live_aws_pricing_api(mock_boto):
    mock_pricing = MagicMock()
    fake_pricing_record = {
        "terms": {
            "OnDemand": {
                "term_123": {
                    "priceDimensions": {
                        "dim_abc": {
                            "pricePerUnit": {"USD": "0.1920"}
                        }
                    }
                }
            }
        }
    }
    mock_pricing.get_products.return_value = {
        "PriceList": [json.dumps(fake_pricing_record)]
    }
    mock_boto.return_value = mock_pricing

    result = get_on_demand_price("m5.xlarge", "us-east-1")
    assert result["hourly_rate"] == 0.1920
    assert result["source"] == "AWS Pricing API"
