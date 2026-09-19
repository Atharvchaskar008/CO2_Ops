"""
Unit tests for the AWS Bedrock foundation layer (State, Client, Agent, Pipeline).
"""

import sys
from unittest.mock import MagicMock, patch
import pytest

# Ensure google.adk and legacy co2ops_agent.agent do not trigger uninstalled package cascade
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
from co2ops_agent.bedrock.agent import BedrockAgent, python_func_to_bedrock_tool_spec
from co2ops_agent.bedrock.orchestrator import BedrockPipeline, BedrockOrchestrator


def test_co2ops_state_lifecycle():
    """Validates state initialization, property access, update, and serialization."""
    state = CO2OpsState(session_id="sess-123", region="us-west-2")
    assert state.session_id == "sess-123"
    assert state.region == "us-west-2"
    assert state.infra_data == []

    # Update state
    state.set("infra_data", [{"Instance_ID": "i-123", "CPU": 15.0}])
    assert len(state.infra_data) == 1
    assert state.get("infra_data")[0]["Instance_ID"] == "i-123"

    # Custom dynamic field
    state.set("custom_metric", 99.5)
    assert state.get("custom_metric") == 99.5

    # Message logging
    state.add_message("user", "Audit us-west-2")
    assert len(state.messages) == 1
    assert state.messages[0]["role"] == "user"

    # Serialization
    state_dict = state.to_dict()
    assert state_dict["session_id"] == "sess-123"
    assert state_dict["custom_metadata"]["custom_metric"] == 99.5

    # Deserialization
    restored = CO2OpsState.from_dict(state_dict)
    assert restored.session_id == "sess-123"
    assert restored.get("custom_metric") == 99.5


def test_tool_spec_generation():
    """Validates introspection of a Python function into Bedrock toolSpec format."""
    def dummy_tool(instance_id: str, max_results: int = 10) -> dict:
        """Fetches telemetry for an EC2 instance."""
        return {"instance_id": instance_id}

    spec = python_func_to_bedrock_tool_spec(dummy_tool)
    assert "toolSpec" in spec
    assert spec["toolSpec"]["name"] == "dummy_tool"
    assert spec["toolSpec"]["description"] == "Fetches telemetry for an EC2 instance."
    props = spec["toolSpec"]["inputSchema"]["json"]["properties"]
    assert "instance_id" in props
    assert props["instance_id"]["type"] == "string"
    assert "max_results" in props
    assert props["max_results"]["type"] == "integer"
    assert spec["toolSpec"]["inputSchema"]["json"]["required"] == ["instance_id"]


def test_bedrock_model_client_converse_mock():
    """Tests BedrockModelClient with a mock boto3 bedrock-runtime client."""
    mock_boto_client = MagicMock()
    mock_boto_client.converse.return_value = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": "Discovered 5 idle instances in us-east-1."}]
            }
        },
        "stopReason": "end_turn",
        "usage": {"totalTokens": 42}
    }

    client = BedrockModelClient(
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        client=mock_boto_client
    )

    response = client.converse(
        messages=[{"role": "user", "content": [{"text": "Audit fleet"}]}],
        system="You are an AWS sustainability agent."
    )

    assert response["stopReason"] == "end_turn"
    mock_boto_client.converse.assert_called_once()
    call_kwargs = mock_boto_client.converse.call_args[1]
    assert call_kwargs["modelId"] == "anthropic.claude-3-5-sonnet-20241022-v2:0"
    assert call_kwargs["system"] == [{"text": "You are an AWS sustainability agent."}]

    # Test generate_text helper
    mock_boto_client.converse.reset_mock()
    text = client.generate_text("Hello")
    assert text == "Discovered 5 idle instances in us-east-1."


def test_bedrock_agent_with_tool_call():
    """Tests BedrockAgent executing a tool call loop."""
    mock_boto_client = MagicMock()

    # Turn 1: Model requests a tool call
    turn1_resp = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "tool-1",
                            "name": "lookup_instance",
                            "input": {"inst_id": "i-01a2b3c4"}
                        }
                    }
                ]
            }
        },
        "stopReason": "tool_use"
    }

    # Turn 2: Model returns final answer after receiving tool result
    turn2_resp = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": "Instance i-01a2b3c4 is averaging 12% CPU."}]
            }
        },
        "stopReason": "end_turn"
    }

    mock_boto_client.converse.side_effect = [turn1_resp, turn2_resp]

    client = BedrockModelClient(client=mock_boto_client)

    def lookup_instance(inst_id: str) -> dict:
        """Looks up instance telemetry."""
        return {"id": inst_id, "cpu": 12.0}

    agent = BedrockAgent(
        name="telemetry_scout",
        description="Scouts EC2 instances",
        system_instruction="Analyze telemetry",
        model_client=client,
        tools=[lookup_instance],
        output_state_key="analysis_results"
    )

    state = CO2OpsState(region="us-east-1")
    updated_state = agent.run(state=state, input_text="Check i-01a2b3c4")

    assert updated_state.get("analysis_results") == "Instance i-01a2b3c4 is averaging 12% CPU."
    assert mock_boto_client.converse.call_count == 2


def test_bedrock_pipeline_and_orchestrator():
    """Tests multi-agent pipeline and orchestrator routing."""
    mock_boto_client = MagicMock()
    mock_boto_client.converse.return_value = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": "Step completed successfully."}]
            }
        },
        "stopReason": "end_turn"
    }
    client = BedrockModelClient(client=mock_boto_client)

    agent_a = BedrockAgent(
        name="step_a",
        description="First step",
        system_instruction="Execute A",
        model_client=client,
        output_state_key="step_a_out"
    )
    agent_b = BedrockAgent(
        name="step_b",
        description="Second step",
        system_instruction="Execute B",
        model_client=client,
        output_state_key="step_b_out"
    )

    pipeline = BedrockPipeline(
        name="OptimizationAdvisor",
        agents=[agent_a, agent_b]
    )

    initial_state = CO2OpsState()
    result_state = pipeline.run(state=initial_state, initial_input="Start flow")

    assert result_state.get("step_a_out") == "Step completed successfully."
    assert result_state.get("step_b_out") == "Step completed successfully."
    assert mock_boto_client.converse.call_count == 2

    # Test Orchestrator routing
    orchestrator = BedrockOrchestrator(model_client=client)
    orchestrator.register_pipeline(pipeline)

    assert orchestrator.route("Please recommend infrastructure optimizations") == "OptimizationAdvisor"
    assert orchestrator.route("Forecast CPU load") == "forecaster"


def test_claude_model_configuration():
    """Validates that Anthropic Claude Sonnet 4.6 is the default model on Amazon Bedrock."""
    import os
    from unittest.mock import patch

    mock_boto = MagicMock()

    # 1. Default model is Anthropic Claude Sonnet 4.6
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("BEDROCK_MODEL_ID", None)
        client = BedrockModelClient(client=mock_boto)
        assert client.model_id == "anthropic.claude-sonnet-4-6"

    # 2. Configurable via BEDROCK_MODEL_ID environment variable
    with patch.dict(os.environ, {"BEDROCK_MODEL_ID": "us.anthropic.claude-sonnet-4-6", "AWS_REGION": "us-east-1"}):
        client = BedrockModelClient(client=mock_boto)
        assert client.model_id == "us.anthropic.claude-sonnet-4-6"
        assert client.region_name == "us-east-1"

    # 3. Explicit parameter override
    client = BedrockModelClient(model_id="custom.anthropic-claude", region_name="eu-west-1", client=mock_boto)
    assert client.model_id == "custom.anthropic-claude"
    assert client.region_name == "eu-west-1"


def test_bedrock_converse_request_construction_for_claude():
    """Validates that BedrockModelClient correctly constructs Converse API request for Claude."""
    mock_boto = MagicMock()
    mock_boto.converse.return_value = {
        "output": {"message": {"role": "assistant", "content": [{"text": "Claude response"}]}},
        "stopReason": "end_turn"
    }

    client = BedrockModelClient(client=mock_boto)
    messages = [{"role": "user", "content": [{"text": "Evaluate EC2 right-sizing"}]}]
    system = "You are a cloud sustainability expert."
    tool_cfg = {
        "tools": [
            {
                "toolSpec": {
                    "name": "query_metrics",
                    "description": "Queries EC2 telemetry",
                    "inputSchema": {"json": {"type": "object", "properties": {}}}
                }
            }
        ]
    }

    resp = client.converse(
        messages=messages,
        system=system,
        inference_config={"temperature": 0.1, "maxTokens": 1024},
        tool_config=tool_cfg
    )

    mock_boto.converse.assert_called_once()
    kwargs = mock_boto.converse.call_args[1]
    assert kwargs["modelId"] == "anthropic.claude-sonnet-4-6"
    assert kwargs["messages"] == messages
    assert kwargs["system"] == [{"text": system}]
    assert kwargs["inferenceConfig"]["temperature"] == 0.1
    assert kwargs["inferenceConfig"]["maxTokens"] == 1024
    assert kwargs["inferenceConfig"]["topP"] == 0.9
    assert kwargs["toolConfig"] == tool_cfg


def test_claude_tool_use_response_parsing():
    """Validates parsing of Claude's toolUse block and returning structured toolResult to Converse."""
    mock_boto = MagicMock()

    # Step 1: Claude asks to use tool
    turn1 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "claude-tool-call-001",
                            "name": "get_instance_carbon",
                            "input": {"instance_type": "m5.2xlarge", "region": "us-east-1"}
                        }
                    }
                ]
            }
        },
        "stopReason": "tool_use"
    }

    # Step 2: Claude produces final response after tool response
    turn2 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": "Emissions for m5.2xlarge in us-east-1: 2.85 kg CO2e/day."}]
            }
        },
        "stopReason": "end_turn"
    }

    mock_boto.converse.side_effect = [turn1, turn2]

    def get_instance_carbon(instance_type: str, region: str) -> dict:
        return {"instance_type": instance_type, "region": region, "co2_kg": 2.85}

    client = BedrockModelClient(client=mock_boto)
    agent = BedrockAgent(
        name="claude_carbon_analyst",
        description="Analyzes carbon footprint",
        system_instruction="Calculate carbon footprint",
        model_client=client,
        tools=[get_instance_carbon],
        output_state_key="impact_analysis"
    )

    state = CO2OpsState(region="us-east-1")
    agent.run(state=state, input_text="Check m5.2xlarge emissions")

    assert mock_boto.converse.call_count == 2
    # Verify the tool result message sent in step 2
    second_call_messages = mock_boto.converse.call_args_list[1][1]["messages"]
    tool_result_msg = second_call_messages[-1]
    assert tool_result_msg["role"] == "user"
    tool_res_content = tool_result_msg["content"][0]["toolResult"]
    assert tool_res_content["toolUseId"] == "claude-tool-call-001"
    assert tool_res_content["status"] == "success"
    assert tool_res_content["content"] == [{"json": {"instance_type": "m5.2xlarge", "region": "us-east-1", "co2_kg": 2.85}}]


def test_structured_tool_result_to_co2ops_state():
    """Validates that structured tool execution results seamlessly populate CO2OpsState."""
    mock_boto = MagicMock()
    mock_boto.converse.side_effect = [
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool-scout-id",
                                "name": "store_telemetry_in_state",
                                "input": {"inst_id": "i-claude-999"}
                            }
                        }
                    ]
                }
            },
            "stopReason": "tool_use"
        },
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Stored telemetry for i-claude-999."}]
                }
            },
            "stopReason": "end_turn"
        }
    ]

    def store_telemetry_in_state(inst_id: str, state: CO2OpsState) -> dict:
        state.infra_data = [{"Instance_ID": inst_id, "Average_CPU_Utilization": 14.2, "provenance": "verified_live"}]
        return {"status": "stored", "count": 1}

    client = BedrockModelClient(client=mock_boto)
    agent = BedrockAgent(
        name="telemetry_collector",
        description="Stores telemetry",
        system_instruction="Collect telemetry",
        model_client=client,
        tools=[store_telemetry_in_state],
        output_state_key="infra_data"
    )

    state = CO2OpsState(region="us-east-1")
    agent.run(state=state, input_text="Collect for i-claude-999")

    assert len(state.infra_data) == 1
    assert state.infra_data[0]["Instance_ID"] == "i-claude-999"
    assert state.infra_data[0]["provenance"] == "verified_live"
    assert state.get("infra_summary") == "Stored telemetry for i-claude-999."


def test_configurable_bedrock_model_id():
    """Validates that another Bedrock model can still be selected via BEDROCK_MODEL_ID."""
    import os
    from unittest.mock import patch

    mock_boto = MagicMock()

    # Selecting Claude 3.5 Sonnet v2
    with patch.dict(os.environ, {"BEDROCK_MODEL_ID": "anthropic.claude-3-5-sonnet-20241022-v2:0"}):
        client = BedrockModelClient(client=mock_boto)
        assert client.model_id == "anthropic.claude-3-5-sonnet-20241022-v2:0"

    # Selecting Amazon Nova
    with patch.dict(os.environ, {"BEDROCK_MODEL_ID": "amazon.nova-pro-v1:0"}):
        client = BedrockModelClient(client=mock_boto)
        assert client.model_id == "amazon.nova-pro-v1:0"


def test_no_google_adk_dependency_in_bedrock_foundation():
    """Validates that the co2ops_agent.bedrock foundation modules have zero imports of Google ADK/GenAI."""
    import co2ops_agent.bedrock.client as client_mod
    import co2ops_agent.bedrock.agent as agent_mod
    import co2ops_agent.bedrock.state as state_mod
    import co2ops_agent.bedrock.orchestrator as orch_mod

    for mod in [client_mod, agent_mod, state_mod, orch_mod]:
        with open(mod.__file__, "r", encoding="utf-8") as f:
            content = f.read()
            assert "google.adk" not in content, f"Found google.adk in {mod.__file__}"
            assert "google.genai" not in content, f"Found google.genai in {mod.__file__}"
            assert "google.cloud" not in content, f"Found google.cloud in {mod.__file__}"

