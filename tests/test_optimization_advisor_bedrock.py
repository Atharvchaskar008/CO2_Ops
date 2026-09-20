"""
Focused unit tests for the Optimization Advisor suite using AWS Bedrock architecture:
- infra_scout_agent
- workload_profiler_agent
- infra_recommender_agent
- optimization_advisor_agent (BedrockPipeline)
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
from co2ops_agent.bedrock.orchestrator import BedrockPipeline

from co2ops_agent.agents.optimization_advisor_agent.sub_agents.infra_scout_agent.agent import (
    infra_scout_agent,
    execute_server_query
)
from co2ops_agent.agents.optimization_advisor_agent.sub_agents.workload_profiler_agent.agent import (
    workload_profiler_agent
)
from co2ops_agent.agents.optimization_advisor_agent.sub_agents.recommender_agent.agent import (
    infra_recommender_agent
)
from co2ops_agent.agents.optimization_advisor_agent.agent import (
    optimization_advisor_agent
)


def test_workload_profiler_agent_definition():
    """Validates that workload_profiler_agent is an instance of BedrockAgent with tools and state keys."""
    assert isinstance(workload_profiler_agent, BedrockAgent)
    assert workload_profiler_agent.name == "workload_profiler"
    assert len(workload_profiler_agent.tools) == 2
    tool_names = [t.__name__ for t in workload_profiler_agent.tools]
    assert "get_on_demand_price" in tool_names
    assert "get_carbon_emissions_per_hour" in tool_names
    assert workload_profiler_agent.input_state_key == "infra_data"
    assert workload_profiler_agent.output_state_key == "analysis_results"


def test_recommender_agent_definition():
    """Validates that infra_recommender_agent is an instance of BedrockAgent with input and output keys."""
    assert isinstance(infra_recommender_agent, BedrockAgent)
    assert infra_recommender_agent.name == "infra_recommender"
    assert infra_recommender_agent.input_state_key == "analysis_results"
    assert infra_recommender_agent.output_state_key == "final_recommendations"


def test_optimization_advisor_pipeline_composition():
    """Validates that optimization_advisor_agent is a BedrockPipeline with all 3 agents."""
    assert isinstance(optimization_advisor_agent, BedrockPipeline)
    assert optimization_advisor_agent.name == "OptimizationAdvisor"
    assert len(optimization_advisor_agent.agents) == 3
    assert optimization_advisor_agent.agents[0] == infra_scout_agent
    assert optimization_advisor_agent.agents[1] == workload_profiler_agent
    assert optimization_advisor_agent.agents[2] == infra_recommender_agent


def test_workload_profiler_converse_with_pricing_and_carbon_tools():
    """Tests workload_profiler executing pricing/carbon tool calls and saving analysis_results to CO2OpsState."""
    mock_boto = MagicMock()

    # Turn 1: Model calls get_on_demand_price
    t1 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "price-call-1",
                            "name": "get_on_demand_price",
                            "input": {"instance_type": "m5.2xlarge", "region": "us-east-1"}
                        }
                    }
                ]
            }
        },
        "stopReason": "tool_use"
    }

    # Turn 2: Model finishes reasoning with analysis
    t2 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"text": "Instance i-01a2b3c4d5e6f7g80 (m5.2xlarge) is 14.5% CPU. Target: m5.large. Monthly savings: $207.36, Carbon savings: 43.2 kg."}
                ]
            }
        },
        "stopReason": "end_turn"
    }

    mock_boto.converse.side_effect = [t1, t2]
    workload_profiler_agent.model_client = BedrockModelClient(client=mock_boto)

    state = CO2OpsState(region="us-east-1")
    state.infra_data = [
        {
            "Instance_ID": "i-01a2b3c4d5e6f7g80",
            "Instance_Type": "m5.2xlarge",
            "Region": "us-east-1",
            "Average_CPU_Utilization": 14.5,
            "Memory_Utilization": 32.0,
            "Total_Carbon_Emission_in_kg": 2.85
        }
    ]

    updated_state = workload_profiler_agent.run(state=state)

    assert mock_boto.converse.call_count == 2
    assert updated_state.analysis_results is not None
    assert "i-01a2b3c4d5e6f7g80" in updated_state.analysis_results
    assert "m5.large" in updated_state.analysis_results


def test_recommender_agent_consumes_analysis_results():
    """Tests infra_recommender_agent consuming analysis_results and writing final_recommendations to CO2OpsState."""
    mock_boto = MagicMock()
    mock_boto.converse.return_value = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "text": "# Infrastructure Recommendations for us-east-1\n## Summary\n- Found 1 underutilized instance.\n## Detailed Recommendations:\n- i-01a2b3c4d5e6f7g80 | m5.2xlarge -> m5.large | Savings: $207.36/mo\n-----------------------------------"
                    }
                ]
            }
        },
        "stopReason": "end_turn"
    }

    infra_recommender_agent.model_client = BedrockModelClient(client=mock_boto)

    state = CO2OpsState(region="us-east-1")
    state.analysis_results = "Instance i-01a2b3c4d5e6f7g80 (m5.2xlarge) is 14.5% CPU. Target: m5.large."

    updated_state = infra_recommender_agent.run(state=state)

    assert mock_boto.converse.call_count == 1
    assert updated_state.final_recommendations is not None
    assert "Infrastructure Recommendations" in updated_state.final_recommendations
    assert "-----------------------------------" in updated_state.final_recommendations


def test_optimization_advisor_full_pipeline_state_handoff():
    """
    Tests the complete 3-agent BedrockPipeline execution:
    Infra Scout -> Workload Profiler -> Recommender
    Verifies that CO2OpsState threads through each step cleanly.
    """
    # 1. Scout client mock
    mock_scout_boto = MagicMock()
    mock_scout_boto.converse.side_effect = [
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "scout-tool-1",
                                "name": "execute_server_query",
                                "input": {"sql": "SELECT * FROM server_metrics WHERE Region = 'us-east-1'"}
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
                    "content": [{"text": "Found 4 instances in us-east-1."}]
                }
            },
            "stopReason": "end_turn"
        }
    ]
    infra_scout_agent.model_client = BedrockModelClient(client=mock_scout_boto)

    # 2. Profiler client mock
    mock_profiler_boto = MagicMock()
    mock_profiler_boto.converse.return_value = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": "Candidate for downsizing: i-01a2b3c4d5e6f7g80 to m5.large."}]
            }
        },
        "stopReason": "end_turn"
    }
    workload_profiler_agent.model_client = BedrockModelClient(client=mock_profiler_boto)

    # 3. Recommender client mock
    mock_recommender_boto = MagicMock()
    mock_recommender_boto.converse.return_value = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": "# Final Recommendations for us-east-1\n- i-01a2b3c4d5e6f7g80 -> m5.large"}]
            }
        },
        "stopReason": "end_turn"
    }
    infra_recommender_agent.model_client = BedrockModelClient(client=mock_recommender_boto)

    # Assemble and run the pipeline
    pipeline = BedrockPipeline(
        name="OptimizationAdvisor",
        agents=[infra_scout_agent, workload_profiler_agent, infra_recommender_agent]
    )

    state = CO2OpsState(region="us-east-1")
    final_state = pipeline.run(state=state, initial_input="Audit us-east-1 servers")

    # Step 1 Handoff verification
    assert len(final_state.infra_data) > 0
    assert any(inst["Region"] == "us-east-1" for inst in final_state.infra_data)

    # Step 2 Handoff verification
    assert final_state.analysis_results is not None
    assert "m5.large" in final_state.analysis_results

    # Step 3 Handoff verification
    assert final_state.final_recommendations is not None
    assert "Final Recommendations" in final_state.final_recommendations
