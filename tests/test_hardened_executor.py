"""
Focused unit tests for the hardened AWS EC2 executor (change_machine_type).
Verifies:
1. x86 -> compatible x86
2. x86 -> incompatible ARM
3. ARM -> ARM
4. AWS modification failure handling
5. successful modification verification
6. running instance preservation
7. stopped instance preservation
8. safety gate BLOCK prevents execution
"""

import sys
from unittest.mock import MagicMock, patch
import pytest

# Ensure optional packages don't trigger import errors
if "google.adk" not in sys.modules:
    mock_adk = MagicMock()
    sys.modules["google"] = MagicMock()
    sys.modules["google.adk"] = mock_adk
    sys.modules["google.adk.agents"] = mock_adk
    sys.modules["google.adk.tools"] = mock_adk
    sys.modules["google.adk.tools.agent_tool"] = mock_adk
if "co2ops_agent.agent" not in sys.modules:
    sys.modules["co2ops_agent.agent"] = MagicMock()

from co2ops_agent.bedrock.state import CO2OpsState
from co2ops_agent.agents.safe_executor_agent.tools import (
    change_machine_type,
    get_instance_type_architecture,
    check_architecture_compatibility
)


# ==============================================================================
# 1. x86 -> Compatible x86
# ==============================================================================
def test_x86_to_compatible_x86():
    """Validates that resizing within compatible x86 architectures succeeds."""
    mock_ec2 = MagicMock()
    mock_waiter = MagicMock()
    mock_ec2.get_waiter.return_value = mock_waiter

    # Mock describe_instances returning m5.2xlarge (x86_64) in running state
    mock_ec2.describe_instances.side_effect = [
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-x86-compat",
                            "InstanceType": "m5.2xlarge",
                            "Architecture": "x86_64",
                            "State": {"Name": "running"}
                        }
                    ]
                }
            ]
        },
        # Post-modification verification call
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-x86-compat",
                            "InstanceType": "m5.large",
                            "Architecture": "x86_64",
                            "State": {"Name": "running"}
                        }
                    ]
                }
            ]
        }
    ]

    state = CO2OpsState()
    state.safety_eval = {"decision": "ALLOW", "is_safe": True}

    with patch("boto3.client", return_value=mock_ec2):
        result = change_machine_type("i-x86-compat", "m5.large", state=state)

        assert result["status"] == "success"
        assert result["execution_status"] == "success"
        assert result["original_instance_type"] == "m5.2xlarge"
        assert result["target_instance_type"] == "m5.large"
        assert result["architecture_check"]["compatible"] is True
        assert result["architecture_check"]["current_architecture"] == "x86_64"
        assert result["architecture_check"]["target_architecture"] == "x86_64"
        assert result["verification_result"] == "verified_success"

        # State fields verification
        assert state.get("execution_status") == "success"
        assert state.get("original_instance_type") == "m5.2xlarge"
        assert state.get("target_instance_type") == "m5.large"


# ==============================================================================
# 2. x86 -> Incompatible ARM
# ==============================================================================
def test_x86_to_incompatible_arm():
    """Validates that resizing x86 to Graviton/ARM is blocked before any AWS modifications."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-x86-target-arm",
                        "InstanceType": "c5.xlarge",
                        "Architecture": "x86_64",
                        "State": {"Name": "running"}
                    }
                ]
            }
        ]
    }

    state = CO2OpsState()
    state.safety_eval = {"decision": "ALLOW", "is_safe": True}

    with patch("boto3.client", return_value=mock_ec2):
        # Target t4g.medium is ARM64 (Graviton)
        result = change_machine_type("i-x86-target-arm", "t4g.medium", state=state)

        assert result["status"] == "failed"
        assert result["execution_status"] == "incompatible_architecture"
        assert result["architecture_check"]["compatible"] is False
        assert result["architecture_check"]["current_architecture"] == "x86_64"
        assert result["architecture_check"]["target_architecture"] == "arm64"
        assert "Incompatible architecture" in result["error"]

        # Crucial: verify no modifications were performed on the instance
        mock_ec2.stop_instances.assert_not_called()
        mock_ec2.modify_instance_attribute.assert_not_called()
        mock_ec2.start_instances.assert_not_called()

        # State fields verification
        assert state.get("execution_status") == "incompatible_architecture"


# ==============================================================================
# 3. ARM -> ARM
# ==============================================================================
def test_arm_to_arm():
    """Validates that resizing between compatible ARM/Graviton instance types succeeds."""
    mock_ec2 = MagicMock()
    mock_waiter = MagicMock()
    mock_ec2.get_waiter.return_value = mock_waiter

    mock_ec2.describe_instances.side_effect = [
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-arm-compat",
                            "InstanceType": "m6g.2xlarge",
                            "Architecture": "arm64",
                            "State": {"Name": "running"}
                        }
                    ]
                }
            ]
        },
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-arm-compat",
                            "InstanceType": "m6g.large",
                            "Architecture": "arm64",
                            "State": {"Name": "running"}
                        }
                    ]
                }
            ]
        }
    ]

    state = CO2OpsState()
    state.safety_eval = {"decision": "ALLOW", "is_safe": True}

    with patch("boto3.client", return_value=mock_ec2):
        result = change_machine_type("i-arm-compat", "m6g.large", state=state)

        assert result["status"] == "success"
        assert result["execution_status"] == "success"
        assert result["original_instance_type"] == "m6g.2xlarge"
        assert result["target_instance_type"] == "m6g.large"
        assert result["architecture_check"]["compatible"] is True
        assert result["architecture_check"]["current_architecture"] == "arm64"
        assert result["architecture_check"]["target_architecture"] == "arm64"


# ==============================================================================
# 4. AWS Modification Failure
# ==============================================================================
def test_aws_modification_failure():
    """Validates that AWS API failure returns explicit failure and never reports false success."""
    mock_ec2 = MagicMock()
    mock_waiter = MagicMock()
    mock_ec2.get_waiter.return_value = mock_waiter

    mock_ec2.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-failing-modify",
                        "InstanceType": "m5.large",
                        "Architecture": "x86_64",
                        "State": {"Name": "running"}
                    }
                ]
            }
        ]
    }

    # Simulate AWS API rejection during modify_instance_attribute
    from botocore.exceptions import ClientError
    mock_ec2.modify_instance_attribute.side_effect = ClientError(
        {"Error": {"Code": "UnsupportedInstanceAttribute", "Message": "InstanceType unsupported"}},
        "ModifyInstanceAttribute"
    )

    state = CO2OpsState()
    state.safety_eval = {"decision": "ALLOW", "is_safe": True}

    with patch("boto3.client", return_value=mock_ec2):
        result = change_machine_type("i-failing-modify", "t3.micro", state=state)

        # Must be explicit failure, NEVER report success
        assert result["status"] == "failed"
        assert result["execution_status"] == "failed"
        assert result["original_instance_type"] == "m5.large"
        assert result["target_instance_type"] == "t3.micro"
        assert "UnsupportedInstanceAttribute" in result["error"]
        assert result["verification_result"] == "modification_failed"

        # Must have attempted to restart the stopped instance back to running
        mock_ec2.start_instances.assert_called_with(InstanceIds=["i-failing-modify"])
        assert result["final_state"] == "running"

        # State fields verification
        assert state.get("execution_status") == "failed"
        assert state.get("error") is not None


# ==============================================================================
# 5. Successful Modification Verification
# ==============================================================================
def test_successful_modification_verification():
    """Validates post-modification verification of instance type and state via AWS API."""
    mock_ec2 = MagicMock()
    mock_waiter = MagicMock()
    mock_ec2.get_waiter.return_value = mock_waiter

    mock_ec2.describe_instances.side_effect = [
        # Pre-flight call
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-verify-me",
                            "InstanceType": "r5.2xlarge",
                            "Architecture": "x86_64",
                            "State": {"Name": "running"}
                        }
                    ]
                }
            ]
        },
        # Post-modification verification call confirming new type and running state
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-verify-me",
                            "InstanceType": "r5.xlarge",
                            "Architecture": "x86_64",
                            "State": {"Name": "running"}
                        }
                    ]
                }
            ]
        }
    ]

    state = CO2OpsState()
    state.safety_eval = {"decision": "ALLOW", "is_safe": True}

    with patch("boto3.client", return_value=mock_ec2):
        result = change_machine_type("i-verify-me", "r5.xlarge", state=state)

        assert result["status"] == "success"
        assert result["verification_result"] == "verified_success"
        assert result["original_instance_type"] == "r5.2xlarge"
        assert result["target_instance_type"] == "r5.xlarge"
        assert result["original_state"] == "running"
        assert result["final_state"] == "running"
        assert state.get("verification_result") == "verified_success"


# ==============================================================================
# 6. Running Instance Preservation
# ==============================================================================
def test_running_instance_preservation():
    """Validates that a running instance is safely stopped, resized, and restarted to running."""
    mock_ec2 = MagicMock()
    mock_waiter = MagicMock()
    mock_ec2.get_waiter.return_value = mock_waiter

    mock_ec2.describe_instances.side_effect = [
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-run-preserve",
                            "InstanceType": "m5.4xlarge",
                            "Architecture": "x86_64",
                            "State": {"Name": "running"}
                        }
                    ]
                }
            ]
        },
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-run-preserve",
                            "InstanceType": "m5.2xlarge",
                            "Architecture": "x86_64",
                            "State": {"Name": "running"}
                        }
                    ]
                }
            ]
        }
    ]

    state = CO2OpsState()
    state.safety_eval = {"decision": "ALLOW", "is_safe": True}

    with patch("boto3.client", return_value=mock_ec2):
        result = change_machine_type("i-run-preserve", "m5.2xlarge", state=state)

        assert result["status"] == "success"
        assert result["original_state"] == "running"
        assert result["final_state"] == "running"

        # Verified standard lifecycle for running instance
        mock_ec2.stop_instances.assert_called_once_with(InstanceIds=["i-run-preserve"])
        mock_ec2.modify_instance_attribute.assert_called_once_with(
            InstanceId="i-run-preserve",
            InstanceType={"Value": "m5.2xlarge"}
        )
        mock_ec2.start_instances.assert_called_once_with(InstanceIds=["i-run-preserve"])


# ==============================================================================
# 7. Stopped Instance Preservation
# ==============================================================================
def test_stopped_instance_preservation():
    """Validates that an originally stopped instance is modified without being restarted."""
    mock_ec2 = MagicMock()

    mock_ec2.describe_instances.side_effect = [
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-stop-preserve",
                            "InstanceType": "c5.2xlarge",
                            "Architecture": "x86_64",
                            "State": {"Name": "stopped"}
                        }
                    ]
                }
            ]
        },
        {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-stop-preserve",
                            "InstanceType": "c5.xlarge",
                            "Architecture": "x86_64",
                            "State": {"Name": "stopped"}
                        }
                    ]
                }
            ]
        }
    ]

    state = CO2OpsState()
    state.safety_eval = {"decision": "ALLOW", "is_safe": True}

    with patch("boto3.client", return_value=mock_ec2):
        result = change_machine_type("i-stop-preserve", "c5.xlarge", state=state)

        assert result["status"] == "success"
        assert result["original_state"] == "stopped"
        assert result["final_state"] == "stopped"

        # Stopped instance must NOT be stopped again or started
        mock_ec2.stop_instances.assert_not_called()
        mock_ec2.start_instances.assert_not_called()
        mock_ec2.modify_instance_attribute.assert_called_once_with(
            InstanceId="i-stop-preserve",
            InstanceType={"Value": "c5.xlarge"}
        )


# ==============================================================================
# 8. Safety Gate BLOCK Prevents Execution
# ==============================================================================
def test_safety_gate_block_prevents_execution():
    """Validates that Claude / LLM cannot bypass safety gate when decision is BLOCK."""
    mock_ec2 = MagicMock()

    state = CO2OpsState()
    # Safety evaluation is BLOCK
    state.safety_eval = {
        "decision": "BLOCK",
        "is_safe": False,
        "reason": "Peak CPU utilization (78.0%) exceeds 70.0% safety threshold."
    }

    with patch("boto3.client", return_value=mock_ec2):
        result = change_machine_type("i-unsafe-candidate", "t3.micro", state=state)

        assert result["status"] == "blocked"
        assert result["execution_status"] == "blocked_by_safety_gate"
        assert result["decision"] == "BLOCK"
        assert "78.0%" in result["reason"]

        # Zero interaction with AWS EC2 API
        mock_ec2.describe_instances.assert_not_called()
        mock_ec2.stop_instances.assert_not_called()
        mock_ec2.modify_instance_attribute.assert_not_called()
        mock_ec2.start_instances.assert_not_called()
