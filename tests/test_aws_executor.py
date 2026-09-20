import pytest
from unittest.mock import patch, MagicMock
from co2ops_agent.agents.safe_executor_agent.tools import (
    is_safe_to_migrate,
    change_machine_type,
    get_forecast_information
)

def test_is_safe_to_migrate_safe():
    # CPU avg 15%, Memory avg 25% -> Safe
    cpu = [12.0, 15.0, 14.0, 16.0, 18.0, 15.0, 15.0]
    mem = [20.0, 25.0, 22.0, 24.0, 26.0, 25.0, 23.0]
    assert is_safe_to_migrate(cpu, mem) is True

def test_is_safe_to_migrate_unsafe_cpu():
    # CPU avg 45% -> Unsafe
    cpu = [45.0, 50.0, 42.0, 48.0, 40.0, 41.0, 49.0]
    mem = [20.0, 25.0, 22.0, 24.0, 26.0, 25.0, 23.0]
    assert is_safe_to_migrate(cpu, mem) is False

def test_is_safe_to_migrate_unsafe_mem():
    # Memory avg 60% -> Unsafe
    cpu = [15.0, 12.0, 18.0, 14.0, 16.0, 15.0, 15.0]
    mem = [60.0, 65.0, 58.0, 62.0, 60.0, 61.0, 59.0]
    assert is_safe_to_migrate(cpu, mem) is False

def test_is_safe_to_migrate_string_parsing():
    # Test handling string representations from LLM tools
    cpu_str = "[10.5, 12.0, 11.5, 14.0, 13.0, 12.5, 11.0]"
    mem_str = "[22.0, 21.0, 23.0, 20.0, 22.5, 21.5, 22.0]"
    assert is_safe_to_migrate(cpu_str, mem_str) is True

def test_get_forecast_information():
    info = get_forecast_information("i-0123456789abcdef0")
    assert "CPU Forecast" in info
    assert "Memory Forecast" in info
    assert "Dates" in info
    assert len(info["CPU Forecast"]) == 7
    assert len(info["Memory Forecast"]) == 7
    assert len(info["Dates"]) == 7

def test_change_machine_type_simulated_fallback():
    # Without real AWS credentials, verifies graceful simulated execution
    result = change_machine_type("i-test12345678", "t3.medium", "us-east-1")
    assert result["status"] == "success"
    assert result["instance_id"] == "i-test12345678"
    assert result["new_machine_type"] == "t3.medium"
    assert "message" in result

@patch("boto3.client")
def test_change_machine_type_mocked_live(mock_boto):
    mock_ec2 = MagicMock()
    mock_waiter = MagicMock()
    mock_ec2.get_waiter.return_value = mock_waiter
    mock_boto.return_value = mock_ec2

    result = change_machine_type("i-0abc123def456", "m5.large", "us-east-1")
    assert result["status"] == "success"
    assert result["mode"] == "live"
    assert result["instance_id"] == "i-0abc123def456"
    assert result["new_machine_type"] == "m5.large"

    # Verify standard AWS instance resizing lifecycle: stop -> modify -> start
    mock_ec2.stop_instances.assert_called_once_with(InstanceIds=["i-0abc123def456"])
    mock_ec2.modify_instance_attribute.assert_called_once_with(
        InstanceId="i-0abc123def456",
        InstanceType={"Value": "m5.large"}
    )
    mock_ec2.start_instances.assert_called_once_with(InstanceIds=["i-0abc123def456"])
