"""
Hermetic Unit & Mocked Integration Tests for the Real AWS Read-Only E2E Path.
Verifies discovery, telemetry validation, error handling, deterministic selection,
and the read-only execution guard without requiring live AWS credentials.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from botocore.exceptions import ClientError, NoCredentialsError

from co2ops_agent.bedrock.state import CO2OpsState
from co2ops_agent.agents.safe_executor_agent.tools import change_machine_type
from co2ops_agent.e2e_readonly import (
    get_aws_identity_and_region,
    discover_running_ec2_instances,
    select_target_instance,
    fetch_verified_cloudwatch_telemetry,
    run_readonly_e2e,
    main,
    MissingCredentialsError,
    MissingEC2PermissionsError,
    MissingCloudWatchPermissionsError,
    MissingBedrockPermissionsError,
    InsufficientCloudWatchDataError,
    NoRunningInstancesError
)


class TestAWSIdentityAndCredentials:
    """Tests for AWS credential detection and STS caller identity verification."""

    @patch("boto3.client")
    def test_get_aws_identity_success(self, mock_boto_client):
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/admin"}
        mock_boto_client.return_value = mock_sts

        account, region = get_aws_identity_and_region("us-west-2")
        assert account == "123456789012"
        assert region == "us-west-2"

    @patch("boto3.client")
    def test_get_aws_identity_missing_credentials(self, mock_boto_client):
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = NoCredentialsError()
        mock_boto_client.return_value = mock_sts

        with pytest.raises(MissingCredentialsError) as exc_info:
            get_aws_identity_and_region("us-east-1")
        assert "Missing AWS Credentials" in str(exc_info.value)
        assert "Action Required" in str(exc_info.value)

    @patch("boto3.client")
    def test_get_aws_identity_auth_failure(self, mock_boto_client):
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = ClientError(
            {"Error": {"Code": "AuthFailure", "Message": "AWS was not able to validate the provided access credentials."}},
            "GetCallerIdentity"
        )
        mock_boto_client.return_value = mock_sts

        with pytest.raises(MissingCredentialsError) as exc_info:
            get_aws_identity_and_region("us-east-1")
        assert "Invalid AWS Credentials" in str(exc_info.value)


class TestEC2DiscoveryAndSelection:
    """Tests for discovering running instances and safe deterministic target selection."""

    def test_discover_running_ec2_instances_success(self):
        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0012345678abcdef0",
                            "InstanceType": "c5.large",
                            "State": {"Name": "running"},
                            "Architecture": "x86_64",
                            "Tags": [{"Key": "Name", "Value": "prod-app"}]
                        },
                        {
                            "InstanceId": "i-0987654321fedcba0",
                            "InstanceType": "m5.large",
                            "State": {"Name": "running"},
                            "Architecture": "x86_64",
                            "Tags": []
                        }
                    ]
                }
            ]
        }

        instances = discover_running_ec2_instances(mock_ec2)
        assert len(instances) == 2
        assert instances[0]["InstanceId"] == "i-0012345678abcdef0"
        assert instances[0]["InstanceType"] == "c5.large"
        assert instances[0]["Tags"]["Name"] == "prod-app"

    def test_discover_running_ec2_instances_permission_denied(self):
        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.side_effect = ClientError(
            {"Error": {"Code": "UnauthorizedOperation", "Message": "You are not authorized to perform this operation."}},
            "DescribeInstances"
        )

        with pytest.raises(MissingEC2PermissionsError) as exc_info:
            discover_running_ec2_instances(mock_ec2)
        assert "Missing EC2 Permissions" in str(exc_info.value)
        assert "ec2:DescribeInstances" in str(exc_info.value)

    def test_select_target_instance_preferred_env(self, monkeypatch):
        monkeypatch.setenv("CO2OPS_E2E_INSTANCE_ID", "i-target-99")
        instances = [
            {"InstanceId": "i-other-11", "InstanceType": "m5.xlarge"},
            {"InstanceId": "i-target-99", "InstanceType": "c5.2xlarge"},
        ]
        selected = select_target_instance(instances, "us-east-1")
        assert selected["InstanceId"] == "i-target-99"
        assert selected["InstanceType"] == "c5.2xlarge"

    def test_select_target_instance_preferred_not_found(self, monkeypatch):
        monkeypatch.setenv("CO2OPS_E2E_INSTANCE_ID", "i-nonexistent")
        instances = [
            {"InstanceId": "i-other-11", "InstanceType": "m5.xlarge"}
        ]
        with pytest.raises(NoRunningInstancesError) as exc_info:
            select_target_instance(instances, "us-east-1")
        assert "i-nonexistent" in str(exc_info.value)

    def test_select_target_instance_deterministic_sort(self, monkeypatch):
        monkeypatch.delenv("CO2OPS_E2E_INSTANCE_ID", raising=False)
        instances = [
            {"InstanceId": "i-zzz", "InstanceType": "t3.medium"},
            {"InstanceId": "i-aaa", "InstanceType": "c5.large"},
            {"InstanceId": "i-mmm", "InstanceType": "m5.large"},
        ]
        selected = select_target_instance(instances, "us-east-1")
        # Should deterministically sort and pick alphabetically first ID
        assert selected["InstanceId"] == "i-aaa"

    def test_select_target_instance_empty(self, monkeypatch):
        monkeypatch.delenv("CO2OPS_E2E_INSTANCE_ID", raising=False)
        with pytest.raises(NoRunningInstancesError) as exc_info:
            select_target_instance([], "us-east-1")
        assert "No running EC2 instances found" in str(exc_info.value)


class TestCloudWatchTelemetryVerification:
    """Tests for CloudWatch CPU telemetry retrieval and fail-closed behavior."""

    def test_fetch_verified_cloudwatch_telemetry_success(self):
        mock_cw = MagicMock()
        mock_cw.get_metric_statistics.return_value = {
            "Datapoints": [
                {"Timestamp": datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc), "Average": 12.5, "Maximum": 25.0, "Minimum": 5.0},
                {"Timestamp": datetime(2026, 9, 20, 11, 0, tzinfo=timezone.utc), "Average": 15.5, "Maximum": 30.0, "Minimum": 8.0},
                {"Timestamp": datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc), "Average": 14.0, "Maximum": 28.0, "Minimum": 6.0},
            ]
        }

        res = fetch_verified_cloudwatch_telemetry(mock_cw, "i-12345", "us-east-1")
        assert res["datapoints_count"] == 3
        assert res["mean_cpu"] == 14.0
        assert res["max_cpu"] == 30.0
        assert res["min_cpu"] == 5.0

    def test_fetch_verified_cloudwatch_telemetry_permission_denied(self):
        mock_cw = MagicMock()
        mock_cw.get_metric_statistics.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "User is not authorized to call GetMetricStatistics"}},
            "GetMetricStatistics"
        )

        with pytest.raises(MissingCloudWatchPermissionsError) as exc_info:
            fetch_verified_cloudwatch_telemetry(mock_cw, "i-12345", "us-east-1")
        assert "cloudwatch:GetMetricStatistics" in str(exc_info.value)

    def test_fetch_verified_cloudwatch_telemetry_zero_datapoints_fails_closed(self):
        mock_cw = MagicMock()
        mock_cw.get_metric_statistics.return_value = {"Datapoints": []}

        with pytest.raises(InsufficientCloudWatchDataError) as exc_info:
            fetch_verified_cloudwatch_telemetry(mock_cw, "i-12345", "us-east-1")
        assert "Insufficient CloudWatch Datapoints" in str(exc_info.value)
        assert "0 CPUUtilization datapoints" in str(exc_info.value)


class TestReadOnlyExecutionGuard:
    """Tests confirming that the read-only guard strictly blocks any EC2 modifications."""

    def test_change_machine_type_blocked_by_state_guard(self):
        state = CO2OpsState(session_id="test-ro")
        state.set("e2e_readonly_mode", True)
        # Even if safety decision is ALLOW, read-only mode takes precedence
        state.safety_eval = {"decision": "ALLOW", "is_safe": True, "reason": "All checks passed"}

        result = change_machine_type("i-12345", "c5.large", "us-east-1", state=state)

        assert result["status"] == "read_only"
        assert result["execution_status"] == "READ_ONLY"
        assert result["decision"] == "READ_ONLY_GUARD"
        assert "READ_ONLY mode" in result["message"]
        assert "READ-ONLY mode" in result["error"]
        assert state.get("execution_status") == "READ_ONLY"

    def test_change_machine_type_blocked_by_env_guard(self, monkeypatch):
        monkeypatch.setenv("CO2OPS_READ_ONLY_MODE", "true")
        state = CO2OpsState(session_id="test-ro-env")
        state.safety_eval = {"decision": "ALLOW", "is_safe": True}

        result = change_machine_type("i-12345", "c5.large", "us-east-1", state=state)

        assert result["status"] == "read_only"
        assert result["execution_status"] == "READ_ONLY"
        assert result["decision"] == "READ_ONLY_GUARD"


class TestFullReadOnlyE2EWorkflow:
    """Tests the full end-to-end read-only flow with mocked AWS clients."""

    @patch("co2ops_agent.e2e_readonly.get_aws_identity_and_region")
    @patch("boto3.client")
    @patch("co2ops_agent.e2e_readonly.BedrockModelClient")
    def test_run_readonly_e2e_success(self, mock_bedrock_cls, mock_boto, mock_identity):
        # 1. Identity
        mock_identity.return_value = ("123456789012", "us-east-1")

        # 2. EC2 Client
        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0e2e123456789abcd",
                            "InstanceType": "m5.2xlarge",
                            "State": {"Name": "running"},
                            "Architecture": "x86_64",
                            "Tags": [{"Key": "Environment", "Value": "staging"}]
                        }
                    ]
                }
            ]
        }

        # 3. CloudWatch Client
        mock_cw = MagicMock()
        mock_cw.get_metric_statistics.return_value = {
            "Datapoints": [
                {"Timestamp": datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc), "Average": 12.0, "Maximum": 22.0, "Minimum": 5.0},
                {"Timestamp": datetime(2026, 9, 20, 11, 0, tzinfo=timezone.utc), "Average": 14.0, "Maximum": 25.0, "Minimum": 6.0},
                {"Timestamp": datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc), "Average": 11.5, "Maximum": 20.0, "Minimum": 4.0},
                {"Timestamp": datetime(2026, 9, 20, 13, 0, tzinfo=timezone.utc), "Average": 13.0, "Maximum": 24.0, "Minimum": 5.0},
                {"Timestamp": datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc), "Average": 12.5, "Maximum": 21.0, "Minimum": 5.0},
            ]
        }

        def boto_client_side_effect(service, **kwargs):
            if service == "ec2":
                return mock_ec2
            elif service == "cloudwatch":
                return mock_cw
            return MagicMock()

        mock_boto.side_effect = boto_client_side_effect

        # 4. Bedrock Client
        mock_bedrock_instance = MagicMock()
        mock_bedrock_instance.generate_text.return_value = "READY"
        mock_bedrock_cls.return_value = mock_bedrock_instance

        # Run E2E Read-Only validation
        results = run_readonly_e2e(region="us-east-1")

        assert results["aws_account_id"] == "123456789012"
        assert results["region"] == "us-east-1"
        assert results["instance_id"] == "i-0e2e123456789abcd"
        assert results["current_instance_type"] == "m5.2xlarge"
        assert results["telemetry_provenance"] == "verified_live"
        assert results["telemetry_verified"] is True
        assert results["cloudwatch_datapoints_count"] == 5
        assert results["observed_mean_cpu_percent"] == 12.6
        assert results["observed_peak_cpu_percent"] == 25.0
        assert results["execution_status"] == "READ_ONLY"
        assert results["ec2_mutations_occurred"] is False
        assert results["safety_decision"] in ("ALLOW", "BLOCK")

    @patch("co2ops_agent.e2e_readonly.get_aws_identity_and_region")
    @patch("boto3.client")
    @patch("co2ops_agent.e2e_readonly.BedrockModelClient")
    def test_run_readonly_e2e_bedrock_access_denied(self, mock_bedrock_cls, mock_boto, mock_identity):
        mock_identity.return_value = ("123456789012", "us-east-1")
        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {
            "Reservations": [{"Instances": [{"InstanceId": "i-test", "InstanceType": "t3.medium", "State": {"Name": "running"}}]}]
        }
        mock_cw = MagicMock()
        mock_cw.get_metric_statistics.return_value = {
            "Datapoints": [{"Timestamp": datetime.now(timezone.utc), "Average": 10.0, "Maximum": 15.0, "Minimum": 5.0}]
        }

        def boto_client_side_effect(service, **kwargs):
            return mock_ec2 if service == "ec2" else mock_cw
        mock_boto.side_effect = boto_client_side_effect

        mock_bedrock_instance = MagicMock()
        mock_bedrock_instance.generate_text.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "User does not have access to model."}},
            "InvokeModel"
        )
        mock_bedrock_cls.return_value = mock_bedrock_instance

        with pytest.raises(MissingBedrockPermissionsError) as exc_info:
            run_readonly_e2e("us-east-1")
        assert "Missing Bedrock Permissions" in str(exc_info.value)
        assert "bedrock:InvokeModel" in str(exc_info.value)


class TestCLIMainEntryPoint:
    """Tests the CLI entry point handling of success and error codes."""

    @patch("co2ops_agent.e2e_readonly.run_readonly_e2e")
    def test_main_success_exit(self, mock_run):
        mock_run.return_value = {
            "aws_account_id": "123456789012",
            "region": "us-east-1",
            "instance_id": "i-12345",
            "current_instance_type": "m5.large",
            "telemetry_provenance": "verified_live",
            "telemetry_verified": True,
            "cloudwatch_datapoints_count": 10,
            "observed_mean_cpu_percent": 15.0,
            "observed_peak_cpu_percent": 25.0,
            "forecast_status": "generated",
            "impact_status": "calculated",
            "safety_decision": "ALLOW",
            "safety_reason": "Safe",
            "execution_status": "READ_ONLY",
            "ec2_mutations_occurred": False
        }

        with pytest.raises(SystemExit) as exit_info:
            main()
        assert exit_info.value.code == 0

    @patch("co2ops_agent.e2e_readonly.run_readonly_e2e")
    def test_main_prerequisite_error_exit(self, mock_run):
        mock_run.side_effect = MissingCredentialsError("No credentials configured")

        with pytest.raises(SystemExit) as exit_info:
            main()
        assert exit_info.value.code == 1
