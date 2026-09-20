"""
Focused unit tests for the infra_scout_agent using AWS Bedrock architecture.
Tests tool execution, state storage in CO2OpsState, and mock Bedrock Converse interactions.
"""

import sys
from unittest.mock import MagicMock, patch
import pytest

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
from co2ops_agent.bedrock.client import BedrockModelClient
from co2ops_agent.agents.optimization_advisor_agent.sub_agents.infra_scout_agent.agent import (
    infra_scout_agent,
    execute_server_query,
    get_server_dataframe,
    DEFAULT_AWS_SERVERS
)


def test_infra_scout_is_bedrock_agent():
    """Validates that infra_scout_agent is an instance of BedrockAgent."""
    from co2ops_agent.bedrock.agent import BedrockAgent
    assert isinstance(infra_scout_agent, BedrockAgent)
    assert infra_scout_agent.name == "aws_server_analyst"
    assert len(infra_scout_agent.tools) == 1
    assert infra_scout_agent.tools[0].__name__ == "execute_server_query"
    assert infra_scout_agent.output_state_key == "infra_data"


def test_get_server_dataframe_benchmark_fallback():
    """Validates that get_server_dataframe returns benchmark EC2 records when boto3 fails or has no credentials."""
    with patch("boto3.client") as mock_boto:
        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.side_effect = Exception("No AWS credentials")
        mock_boto.return_value = mock_ec2

        df = get_server_dataframe()
        assert len(df) == len(DEFAULT_AWS_SERVERS)
        assert "Instance_ID" in df.columns
        assert "Average_CPU_Utilization" in df.columns


def test_execute_server_query_populates_state():
    """Validates that execute_server_query populates state.infra_data and preserves output format."""
    state = CO2OpsState(region="us-east-1")
    assert state.infra_data == []

    # Query with state injection
    result = execute_server_query(
        sql="SELECT Instance_ID, Region, Average_CPU_Utilization FROM server_metrics WHERE Region = 'us-east-1'",
        state=state
    )

    # Validate tool output structure
    assert result["status"] == "success"
    assert result["row_count"] > 0
    assert isinstance(result["rows"], list)

    # Validate state update
    assert len(state.infra_data) == result["row_count"]
    for row in state.infra_data:
        assert row["Region"] == "us-east-1"


def test_infra_scout_agent_bedrock_converse_flow():
    """Validates full agent reasoning loop with mocked Bedrock Converse API."""
    mock_boto_client = MagicMock()

    # Turn 1: Bedrock model decides to invoke execute_server_query
    model_turn1 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "tool-scout-1",
                            "name": "execute_server_query",
                            "input": {
                                "sql": "SELECT Instance_ID, Region, Average_CPU_Utilization FROM server_metrics WHERE Region = 'us-east-1'"
                            }
                        }
                    }
                ]
            }
        },
        "stopReason": "tool_use"
    }

    # Turn 2: Bedrock model provides analysis after receiving tool output
    model_turn2 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "text": "Scouted 4 EC2 instances in us-east-1. Average CPU is 16.4%."
                    }
                ]
            }
        },
        "stopReason": "end_turn"
    }

    mock_boto_client.converse.side_effect = [model_turn1, model_turn2]

    # Inject mock client into infra_scout_agent
    infra_scout_agent.model_client = BedrockModelClient(client=mock_boto_client)

    state = CO2OpsState(region="us-east-1")
    updated_state = infra_scout_agent.run(
        state=state,
        input_text="Find all underutilized EC2 servers in us-east-1"
    )

    # Verify Bedrock API calls
    assert mock_boto_client.converse.call_count == 2

    # Verify state was populated with both structured rows and text summary
    assert len(updated_state.infra_data) > 0
    assert updated_state.get("infra_summary") == "Scouted 4 EC2 instances in us-east-1. Average CPU is 16.4%."
    assert updated_state.messages[-1]["content"] == "Scouted 4 EC2 instances in us-east-1. Average CPU is 16.4%."
