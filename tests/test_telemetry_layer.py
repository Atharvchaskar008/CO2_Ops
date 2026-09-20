"""
Focused unit tests for the CO2Ops telemetry layer.
Verifies:
1. live EC2 telemetry
2. CloudWatch CPU retrieval
3. no hardcoded CPU
4. demo/live separation
5. missing CloudWatch data handling
6. synthetic data marked and rejected by safety engine
7. telemetry provenance correctly populated in CO2OpsState
"""

import sys
import os
from unittest.mock import MagicMock, patch
import pytest
import pandas as pd

# Ensure optional packages don't trigger uninstalled package cascade
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
from co2ops_agent.agents.safe_executor_agent.tools import evaluate_migration_safety
from co2ops_agent.agents.optimization_advisor_agent.sub_agents.infra_scout_agent.agent import (
    get_server_dataframe,
    execute_server_query,
    fetch_cloudwatch_instance_cpu,
    is_demo_mode,
    DEFAULT_AWS_SERVERS
)


# =========================================================================
# 1. Live EC2 Telemetry
# =========================================================================

def test_live_ec2_telemetry():
    """Validates that live mode fetches actual EC2 instances and attaches verified live provenance."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-live-001abc",
                        "InstanceType": "c5.xlarge",
                        "State": {"Name": "running"}
                    },
                    {
                        "InstanceId": "i-live-stopped",
                        "InstanceType": "t3.medium",
                        "State": {"Name": "stopped"}  # should be skipped
                    }
                ]
            }
        ]
    }

    mock_cw = MagicMock()
    mock_cw.get_metric_statistics.return_value = {
        "Datapoints": [{"Average": 19.4}, {"Average": 21.6}]
    }

    with patch("boto3.client") as mock_boto:
        def client_side_effect(service, region_name=None):
            if service == "ec2":
                return mock_ec2
            if service == "cloudwatch":
                return mock_cw
            return MagicMock()
        mock_boto.side_effect = client_side_effect

        df = get_server_dataframe(region="us-east-1", demo_mode=False)

        assert len(df) == 1
        row = df.iloc[0]
        assert row["Instance_ID"] == "i-live-001abc"
        assert row["Instance_Type"] == "c5.xlarge"
        assert row["Region"] == "us-east-1"
        assert row["Average_CPU_Utilization"] == 20.5
        assert row["provenance"] == "verified_live"
        assert row["telemetry_source"] == "cloudwatch"
        assert bool(row["telemetry_verified"]) is True
        assert bool(row["is_synthetic"]) is False
        assert bool(row["telemetry_missing"]) is False
        assert row["telemetry_status"] == "sufficient_data"

        # Verify none of the demo benchmark IDs are mixed in
        demo_ids = {s["Instance_ID"] for s in DEFAULT_AWS_SERVERS}
        assert row["Instance_ID"] not in demo_ids


# =========================================================================
# 2. CloudWatch CPU Retrieval
# =========================================================================

def test_cloudwatch_cpu_retrieval():
    """Validates that fetch_cloudwatch_instance_cpu accurately queries AWS/EC2 metric statistics."""
    mock_cw = MagicMock()
    mock_cw.get_metric_statistics.return_value = {
        "Datapoints": [
            {"Average": 12.3},
            {"Average": 14.7},
            {"Average": 15.0}
        ]
    }

    cpu_val = fetch_cloudwatch_instance_cpu(
        instance_id="i-test-999xyz",
        region="us-west-2",
        client=mock_cw,
        period=3600,
        days=14
    )

    # Expected average: (12.3 + 14.7 + 15.0) / 3 = 14.0
    assert cpu_val == 14.0

    mock_cw.get_metric_statistics.assert_called_once()
    call_kwargs = mock_cw.get_metric_statistics.call_args[1]
    assert call_kwargs["Namespace"] == "AWS/EC2"
    assert call_kwargs["MetricName"] == "CPUUtilization"
    assert call_kwargs["Dimensions"] == [{"Name": "InstanceId", "Value": "i-test-999xyz"}]
    assert call_kwargs["Statistics"] == ["Average"]


# =========================================================================
# 3. No Hardcoded CPU
# =========================================================================

def test_no_hardcoded_cpu():
    """Validates that live CPU utilization is never hardcoded (e.g. to 18.0) and respects actual CloudWatch values or None."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-dynamic-cpu",
                        "InstanceType": "m5.large",
                        "State": {"Name": "running"}
                    }
                ]
            }
        ]
    }

    # Case A: Real low utilization (7.4%)
    mock_cw = MagicMock()
    mock_cw.get_metric_statistics.return_value = {
        "Datapoints": [{"Average": 7.4}]
    }

    with patch("boto3.client") as mock_boto:
        mock_boto.side_effect = lambda s, **kw: mock_ec2 if s == "ec2" else mock_cw
        df = get_server_dataframe(demo_mode=False)
        assert df.iloc[0]["Average_CPU_Utilization"] == 7.4
        assert df.iloc[0]["Average_CPU_Utilization"] != 18.0

    # Case B: Real high utilization (33.8%)
    mock_cw.get_metric_statistics.return_value = {
        "Datapoints": [{"Average": 33.8}]
    }
    with patch("boto3.client") as mock_boto:
        mock_boto.side_effect = lambda s, **kw: mock_ec2 if s == "ec2" else mock_cw
        df = get_server_dataframe(demo_mode=False)
        assert df.iloc[0]["Average_CPU_Utilization"] == 33.8
        assert df.iloc[0]["Average_CPU_Utilization"] != 18.0

    # Case C: No CloudWatch datapoints available -> must be None, NOT 18.0
    mock_cw.get_metric_statistics.return_value = {"Datapoints": []}
    with patch("boto3.client") as mock_boto:
        mock_boto.side_effect = lambda s, **kw: mock_ec2 if s == "ec2" else mock_cw
        df = get_server_dataframe(demo_mode=False)
        assert df.iloc[0]["Average_CPU_Utilization"] is None
        assert df.iloc[0]["Average_CPU_Utilization"] != 18.0


# =========================================================================
# 4. Demo / Live Separation
# =========================================================================

def test_demo_live_separation():
    """Validates that LIVE mode never mixes demo instances, and DEMO_MODE never calls AWS APIs."""
    # Sub-test A: DEMO mode returns demo servers without invoking boto3
    with patch("boto3.client") as mock_boto:
        df_demo = get_server_dataframe(demo_mode=True)
        assert mock_boto.call_count == 0
        assert len(df_demo) == len(DEFAULT_AWS_SERVERS)
        for _, row in df_demo.iterrows():
            assert row["provenance"] == "demo"
            assert bool(row["is_synthetic"]) is True
            assert bool(row["telemetry_verified"]) is False

    # Sub-test B: LIVE mode with 0 running EC2 instances returns empty DataFrame, NOT DEFAULT_AWS_SERVERS
    mock_ec2 = MagicMock()
    mock_ec2.describe_instances.return_value = {"Reservations": []}
    with patch("boto3.client") as mock_boto:
        mock_boto.return_value = mock_ec2
        df_live_empty = get_server_dataframe(demo_mode=False)
        assert df_live_empty.empty
        assert len(df_live_empty) == 0

    # Sub-test C: LIVE mode with AWS client error returns empty DataFrame, NEVER injecting demo instances
    mock_ec2.describe_instances.side_effect = Exception("AWS Auth Failure")
    with patch("boto3.client") as mock_boto:
        mock_boto.return_value = mock_ec2
        df_error = get_server_dataframe(demo_mode=False)
        assert df_error.empty
        assert len(df_error) == 0


# =========================================================================
# 5. Missing CloudWatch Data
# =========================================================================

def test_missing_cloudwatch_data():
    """Validates that missing CloudWatch data returns explicit insufficient-data result with telemetry_missing=True."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-live-no-cw",
                        "InstanceType": "r5.xlarge",
                        "State": {"Name": "running"}
                    }
                ]
            }
        ]
    }
    mock_cw = MagicMock()
    mock_cw.get_metric_statistics.return_value = {"Datapoints": []}

    with patch("boto3.client") as mock_boto:
        mock_boto.side_effect = lambda s, **kw: mock_ec2 if s == "ec2" else mock_cw
        df = get_server_dataframe(demo_mode=False)

        assert len(df) == 1
        row = df.iloc[0]
        assert row["Instance_ID"] == "i-live-no-cw"
        assert row["Average_CPU_Utilization"] is None
        assert bool(row["telemetry_missing"]) is True
        assert row["telemetry_status"] == "insufficient_data"
        assert bool(row["telemetry_verified"]) is False
        assert row["provenance"] == "unverified_live"
        assert row["telemetry_source"] == "none"
        # Not synthetic: it's a real live instance that simply lacks CW metrics
        assert bool(row["is_synthetic"]) is False


# =========================================================================
# 6. Synthetic Data Marked and Rejected by Safety Engine
# =========================================================================

def test_synthetic_data_marked_and_rejected():
    """Validates that synthetic/demo telemetry is explicitly marked and blocked by the deterministic safety engine."""
    state = CO2OpsState(region="us-east-1")

    # In DEMO mode, execute_server_query returns demo data with is_synthetic=True
    result = execute_server_query(
        sql="SELECT Instance_ID, Average_CPU_Utilization FROM server_metrics WHERE Region = 'us-east-1' LIMIT 1",
        state=state,
        demo_mode=True
    )
    assert result["status"] == "success"
    assert len(state.infra_data) == 1
    assert state.infra_data[0]["is_synthetic"] is True
    assert state.custom_metadata.get("is_synthetic") is True

    # Even with low forecast values, safety engine must FAIL CLOSED due to synthetic telemetry
    state.forecast_data = {
        "instance_id": state.infra_data[0]["Instance_ID"],
        "CPU Forecast": [12.0] * 7,
        "Memory Forecast": [20.0] * 7,
        "is_synthetic": False
    }

    eval_result = evaluate_migration_safety(
        instance_id=state.infra_data[0]["Instance_ID"],
        state=state
    )

    assert eval_result["decision"] == "BLOCK"
    assert eval_result["is_safe"] is False
    assert "Synthetic telemetry detected" in eval_result["reason"]


# =========================================================================
# 7. Telemetry Provenance in CO2OpsState
# =========================================================================

def test_telemetry_provenance_in_co2ops_state():
    """Validates that verified live telemetry populates CO2OpsState provenance and is accepted by safety engine."""
    mock_ec2 = MagicMock()
    mock_ec2.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-live-verified-777",
                        "InstanceType": "m5.2xlarge",
                        "State": {"Name": "running"}
                    }
                ]
            }
        ]
    }
    mock_cw = MagicMock()
    mock_cw.get_metric_statistics.return_value = {
        "Datapoints": [{"Average": 16.5}]
    }

    state = CO2OpsState(region="us-east-1")

    with patch("boto3.client") as mock_boto:
        mock_boto.side_effect = lambda s, **kw: mock_ec2 if s == "ec2" else mock_cw

        result = execute_server_query(
            sql="SELECT Instance_ID, Instance_Type, Region, Average_CPU_Utilization FROM server_metrics",
            state=state,
            demo_mode=False
        )

        assert result["status"] == "success"
        assert len(state.infra_data) == 1
        record = state.infra_data[0]
        assert record["Instance_ID"] == "i-live-verified-777"
        assert record["provenance"] == "verified_live"
        assert record["telemetry_source"] == "cloudwatch"
        assert record["telemetry_verified"] is True
        assert record["is_synthetic"] is False
        assert record["telemetry_missing"] is False

        # Check state.custom_metadata aggregation
        assert state.custom_metadata["telemetry_provenance"] == "verified_live"
        assert state.custom_metadata["telemetry_source"] == "cloudwatch"
        assert state.custom_metadata["telemetry_verified"] is True
        assert state.custom_metadata["is_synthetic"] is False
        assert state.custom_metadata["missing_telemetry"] is False

        # Provide safe verified forecast data
        state.forecast_data = {
            "instance_id": "i-live-verified-777",
            "CPU Forecast": [16.5, 17.0, 15.8, 16.2, 17.5, 16.0, 16.8],
            "Memory Forecast": [28.0, 29.0, 28.5, 27.8, 29.2, 28.1, 28.4],
            "is_synthetic": False,
            "source": "verified_history"
        }

        eval_result = evaluate_migration_safety(
            instance_id="i-live-verified-777",
            state=state
        )

        # Safety engine recognizes verified live telemetry and safe thresholds -> ALLOW
        assert eval_result["decision"] == "ALLOW"
        assert eval_result["is_safe"] is True
        assert "All safety checks passed" in eval_result["reason"]
