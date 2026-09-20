import pytest
from unittest.mock import patch, MagicMock
from co2ops_agent.agents.safe_executor_agent.tools import (
    is_safe_to_migrate,
    change_machine_type,
    get_forecast_information
)
from co2ops_agent.bedrock.state import CO2OpsState


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


def test_change_machine_type_blocked_without_state():
    """
    Safety gate regression: calling change_machine_type without a CO2OpsState
    must return BLOCK. Previously this bypassed the safety gate entirely.
    No state = no verified safety evaluation = no execution allowed.
    """
    result = change_machine_type("i-test12345678", "t3.medium", "us-east-1")
    assert result["status"] == "blocked"
    assert result["decision"] == "BLOCK"
    assert result["execution_status"] == "blocked_no_safety_context"
    assert "Safety Gate" in result["error"]
    assert "No CO2OpsState provided" in result["message"]


def test_change_machine_type_blocked_without_state_mocked():
    """
    Safety gate regression: even with a working boto3 mock, omitting state
    must be blocked before any AWS API call is made.
    """
    with patch("boto3.client") as mock_boto:
        mock_ec2 = MagicMock()
        mock_boto.return_value = mock_ec2

        result = change_machine_type("i-0abc123def456", "m5.large", "us-east-1")

        assert result["status"] == "blocked"
        assert result["decision"] == "BLOCK"
        # No AWS calls should have been made
        mock_ec2.stop_instances.assert_not_called()
        mock_ec2.modify_instance_attribute.assert_not_called()
        mock_ec2.start_instances.assert_not_called()


def test_change_machine_type_allowed_with_state():
    """
    Execution proceeds when state contains a valid ALLOW decision.
    This confirms the safety gate accepts correct approvals.
    """
    state = CO2OpsState(session_id="allowed-exec-test")
    state.safety_eval = {"decision": "ALLOW", "is_safe": True, "reason": "All checks passed."}

    result = change_machine_type("i-test-allowed", "t3.medium", "us-east-1", state=state)

    # Without live AWS creds this falls through to simulation
    assert result["status"] == "success"
    assert result["instance_id"] == "i-test-allowed"
    assert result["new_machine_type"] == "t3.medium"
