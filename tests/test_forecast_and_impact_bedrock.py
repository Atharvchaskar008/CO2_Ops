"""
Unit and state handoff tests for the Forecasting and Impact Calculator agents:
- forecasting_tool_agent (forecaster_agent)
- impact_calculator_agent
- Cross-agent state handoff: Optimization Advisor -> Forecaster -> Impact Calculator
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
from co2ops_agent.bedrock.agent import BedrockAgent

from co2ops_agent.agents.forecaster_agent.agent import (
    forecasting_tool_agent,
    forecaster_agent,
    execute_forecast_query,
    generate_aws_forecast
)
from co2ops_agent.agents.impact_calculator_agent.agent import (
    impact_calculator_agent,
    get_on_demand_price,
    get_carbon_emissions_per_hour
)


def test_forecaster_agent_definition():
    """Validates that forecasting_tool_agent and forecaster_agent are BedrockAgents with correct tools and state keys."""
    assert isinstance(forecasting_tool_agent, BedrockAgent)
    assert forecaster_agent is forecasting_tool_agent
    assert forecasting_tool_agent.name == "forecasting_tool_agent"
    assert len(forecasting_tool_agent.tools) == 1
    assert forecasting_tool_agent.tools[0].__name__ == "execute_forecast_query"
    assert forecasting_tool_agent.input_state_key == "final_recommendations"
    assert forecasting_tool_agent.output_state_key == "forecast_data"


def test_execute_forecast_query_with_direct_query():
    """Tests execute_forecast_query extracting instance ID and metric from query string."""
    res = execute_forecast_query("Forecast 7 days CPU usage for i-0123456789abcdef0")
    assert res["status"] == "success"
    assert res["instance_id"] == "i-0123456789abcdef0"
    assert res["metric"] == "cpu"
    assert res["horizon_days"] == 7
    assert len(res["values"]) == 7
    assert len(res["dates"]) == 7


def test_execute_forecast_query_consumes_recommendation_from_state():
    """Tests that execute_forecast_query extracts instance ID from state.final_recommendations when not in query."""
    state = CO2OpsState(session_id="test-session")
    state.final_recommendations = "Recommend downsizing instance i-0abcdef1234567890 from m5.xlarge to t3.large due to 14% CPU."

    res = execute_forecast_query("Forecast 7 days CPU", state=state)
    assert res["status"] == "success"
    assert res["instance_id"] == "i-0abcdef1234567890"
    assert res["metric"] == "cpu"
    assert len(res["values"]) == 7
    # Verify state was directly populated
    assert state.forecast_data == res
    assert state.forecast_data["instance_id"] == "i-0abcdef1234567890"


def test_forecasting_agent_mock_run():
    """Tests running forecasting_tool_agent with a mocked Bedrock client."""
    mock_boto = MagicMock()

    t1 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "forecast-call-1",
                            "name": "execute_forecast_query",
                            "input": {"query_or_text": "Forecast CPU for i-01122334455667788"}
                        }
                    }
                ]
            }
        },
        "stopReason": "tool_use"
    }

    t2 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"text": "7-day CPU forecast for i-01122334455667788 averages ~15.2%, confirming safe downsizing window."}
                ]
            }
        },
        "stopReason": "end_turn"
    }

    mock_boto.converse.side_effect = [t1, t2]

    state = CO2OpsState(session_id="test-forecaster")
    client = BedrockModelClient(client=mock_boto)
    agent = BedrockAgent(
        name=forecasting_tool_agent.name,
        description=forecasting_tool_agent.description,
        system_instruction=forecasting_tool_agent.system_instruction,
        model_client=client,
        tools=forecasting_tool_agent.tools,
        input_state_key=forecasting_tool_agent.input_state_key,
        output_state_key=forecasting_tool_agent.output_state_key
    )

    state = agent.run(state, input_text="Predict CPU for i-01122334455667788")

    assert mock_boto.converse.call_count == 2
    assert state.forecast_data["instance_id"] == "i-01122334455667788"
    assert state.forecast_data["summary"] == "7-day CPU forecast for i-01122334455667788 averages ~15.2%, confirming safe downsizing window."
    assert "forecast_summary" in state.custom_metadata


def test_impact_calculator_agent_definition():
    """Validates that impact_calculator_agent is a BedrockAgent with pricing and carbon tools."""
    assert isinstance(impact_calculator_agent, BedrockAgent)
    assert impact_calculator_agent.name == "impact_calculator_agent"
    assert len(impact_calculator_agent.tools) == 2
    tool_names = [t.__name__ for t in impact_calculator_agent.tools]
    assert "get_on_demand_price" in tool_names
    assert "get_carbon_emissions_per_hour" in tool_names
    assert impact_calculator_agent.input_state_key == "forecast_data"
    assert impact_calculator_agent.output_state_key == "impact_analysis"


def test_impact_calculator_tools_populate_state():
    """Tests get_on_demand_price and get_carbon_emissions_per_hour populating state.impact_analysis."""
    state = CO2OpsState(session_id="test-impact-tools")

    price_curr = get_on_demand_price("m5.xlarge", region="us-east-1", state=state)
    assert price_curr["instance_type"] == "m5.xlarge"
    assert price_curr["hourly_rate"] == 0.192

    price_target = get_on_demand_price("t3.large", region="us-east-1", state=state)
    assert price_target["instance_type"] == "t3.large"
    assert price_target["hourly_rate"] == 0.0832

    # Check pricing cached in state.impact_analysis
    assert "pricing" in state.impact_analysis
    assert state.impact_analysis["pricing"]["m5.xlarge"]["hourly_rate"] == 0.192
    assert state.impact_analysis["pricing"]["t3.large"]["hourly_rate"] == 0.0832

    # Call carbon tool with state
    emissions = get_carbon_emissions_per_hour("m5.xlarge", "us-east-1", "t3.large", "us-east-1", duration_hours=24.0, state=state)
    assert "m5.xlarge" in emissions
    assert "t3.large" in emissions
    assert "carbon_emissions" in state.impact_analysis
    assert state.impact_analysis["current_instance"] == "m5.xlarge"
    assert state.impact_analysis["target_instance"] == "t3.large"
    assert "monthly_carbon_savings_kg" in state.impact_analysis
    assert "monthly_cost_savings" in state.impact_analysis
    assert state.impact_analysis["monthly_cost_savings"] > 0
    assert state.impact_analysis["monthly_carbon_savings_kg"] > 0


def test_impact_calculator_agent_mock_run():
    """Tests running impact_calculator_agent with Bedrock tool execution loop."""
    mock_boto = MagicMock()

    t1 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "price-call-1",
                            "name": "get_on_demand_price",
                            "input": {"instance_type": "m5.xlarge", "region": "us-east-1"}
                        }
                    }
                ]
            }
        },
        "stopReason": "tool_use"
    }

    t2 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "carbon-call-1",
                            "name": "get_carbon_emissions_per_hour",
                            "input": {
                                "current_instance_type": "m5.xlarge",
                                "current_region": "us-east-1",
                                "target_instance_type": "t3.large",
                                "target_region": "us-east-1",
                                "duration_hours": 24.0
                            }
                        }
                    }
                ]
            }
        },
        "stopReason": "tool_use"
    }

    t3 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"text": "Downsizing from m5.xlarge to t3.large saves $78.34/month and reduces CO2 emissions by ~1.65 kg/month."}
                ]
            }
        },
        "stopReason": "end_turn"
    }

    mock_boto.converse.side_effect = [t1, t2, t3]

    state = CO2OpsState(session_id="test-impact-agent")
    state.final_recommendations = "Downsize i-0998877 from m5.xlarge to t3.large in us-east-1"
    state.forecast_data = {"instance_id": "i-0998877", "values": [14.0, 15.0, 16.0], "metric": "cpu"}

    client = BedrockModelClient(client=mock_boto)
    agent = BedrockAgent(
        name=impact_calculator_agent.name,
        description=impact_calculator_agent.description,
        system_instruction=impact_calculator_agent.system_instruction,
        model_client=client,
        tools=impact_calculator_agent.tools,
        input_state_key=impact_calculator_agent.input_state_key,
        output_state_key=impact_calculator_agent.output_state_key
    )

    state = agent.run(state)

    assert mock_boto.converse.call_count == 3
    assert "carbon_emissions" in state.impact_analysis
    assert state.impact_analysis["summary"] == "Downsizing from m5.xlarge to t3.large saves $78.34/month and reduces CO2 emissions by ~1.65 kg/month."
    assert "impact_summary" in state.custom_metadata


def test_state_handoff_optimization_to_forecast_to_impact():
    """
    Tests complete end-to-end state handoff across agents:
    Optimization Advisor -> Forecaster Agent -> Impact Calculator Agent.
    """
    # 1. State initialized with fleet telemetry and recommendations
    state = CO2OpsState(
        session_id="handoff-session-001",
        region="us-east-1",
        infra_data=[{
            "Instance_ID": "i-04a3f2b1c8e901234",
            "Instance_Type": "m5.2xlarge",
            "Avg_CPU": 12.4,
            "State": "running",
            "Region": "us-east-1"
        }],
        final_recommendations="Recommend downsizing i-04a3f2b1c8e901234 from m5.2xlarge to t3.xlarge in us-east-1."
    )

    # 2. Forecaster consumes recommendation from state without explicit instance argument
    forecast_result = execute_forecast_query("Forecast 7-day CPU utilization", state=state)
    assert state.forecast_data["instance_id"] == "i-04a3f2b1c8e901234"
    assert state.forecast_data["metric"] == "cpu"
    assert len(state.forecast_data["values"]) == 7

    # 3. Impact Calculator consumes forecast_data and recommendations from state
    price_curr = get_on_demand_price("m5.2xlarge", region=state.region, state=state)
    price_target = get_on_demand_price("t3.xlarge", region=state.region, state=state)
    emissions = get_carbon_emissions_per_hour(
        current_instance_type="m5.2xlarge",
        current_region=state.region,
        target_instance_type="t3.xlarge",
        target_region=state.region,
        duration_hours=24.0,
        state=state
    )

    # 4. Verify all state stages are intact and cleanly populated
    assert len(state.infra_data) == 1
    assert state.final_recommendations is not None
    assert state.forecast_data["status"] == "success"
    assert "pricing" in state.impact_analysis
    assert "carbon_emissions" in state.impact_analysis
    assert state.impact_analysis["monthly_cost_savings"] > 0
    assert state.impact_analysis["monthly_carbon_savings_kg"] > 0
