"""
Focused unit, state handoff, and safety gate enforcement tests for the Bedrock Safety Engine:
1. safe utilization -> ALLOW
2. high P95 -> BLOCK
3. high peak -> BLOCK
4. high volatility -> BLOCK
5. missing forecast -> BLOCK
6. invalid forecast -> BLOCK
7. missing telemetry / synthetic data -> BLOCK
8. empty input -> BLOCK
9. LLM attempting to bypass safety -> BLOCK
Plus agent definitions and end-to-end pipeline flows.
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

from co2ops_agent.agents.safe_executor_agent.agent import (
    safety_agent,
    executor_agent,
    safe_executor_agent
)
from co2ops_agent.agents.safe_executor_agent.tools import (
    is_safe_to_migrate,
    evaluate_migration_safety,
    change_machine_type,
    get_forecast_information
)


# ==============================================================================
# 1. Safe Utilization -> ALLOW
# ==============================================================================
def test_safe_utilization_allow():
    """1. Safe utilization (P95 < 45%, Peak < 70%, Volatility < 15%, Avg CPU < 30%, Avg Mem < 40%) -> ALLOW."""
    cpu = [12.0, 14.0, 13.0, 15.0, 14.0, 13.0, 14.0]
    mem = [20.0, 22.0, 21.0, 23.0, 22.0, 21.0, 20.0]

    # Tool function check
    assert is_safe_to_migrate(cpu, mem) is True

    # State evaluation check
    state = CO2OpsState(session_id="safe-allow-01")
    state.final_recommendations = "Recommend downsizing i-0123456789abcdef0 to t3.large"
    state.forecast_data = {
        "status": "success",
        "instance_id": "i-0123456789abcdef0",
        "metric": "cpu",
        "values": cpu,
        "mem_values": mem
    }

    res = evaluate_migration_safety(state=state)
    assert res["is_safe"] is True
    assert res["decision"] == "ALLOW"
    assert "All safety checks passed" in res["reason"]
    assert state.safety_eval["decision"] == "ALLOW"


# ==============================================================================
# 2. High P95 -> BLOCK
# ==============================================================================
def test_high_p95_block():
    """2. Workload with high 95th percentile utilization (P95 >= 45.0%) -> BLOCK."""
    # Peak is 50 (<70), avg is ~30, but P95 is 49.4 (>= 45.0)
    cpu_high_p95 = [20.0, 22.0, 21.0, 23.0, 22.0, 48.0, 50.0]
    mem_safe = [20.0, 22.0, 21.0, 23.0, 22.0, 21.0, 20.0]

    assert is_safe_to_migrate(cpu_high_p95, mem_safe) is False

    res = evaluate_migration_safety(
        instance_id="i-highp95",
        cpu_forecast=cpu_high_p95,
        mem_forecast=mem_safe
    )
    assert res["is_safe"] is False
    assert res["decision"] == "BLOCK"
    assert "P95 utilization exceeds safety threshold" in res["reason"]


# ==============================================================================
# 3. High Peak -> BLOCK
# ==============================================================================
def test_high_peak_block():
    """3. Workload with high peak spike (Peak >= 70.0%) -> BLOCK."""
    # Average is low (~24%), P95 ~40%, but peak spikes to 76.0% (>= 70%)
    cpu_spike = [15.0, 16.0, 18.0, 17.0, 15.0, 76.0, 16.0]
    mem_safe = [20.0, 22.0, 21.0, 23.0, 22.0, 21.0, 20.0]

    assert is_safe_to_migrate(cpu_spike, mem_safe) is False

    res = evaluate_migration_safety(
        instance_id="i-spike",
        cpu_forecast=cpu_spike,
        mem_forecast=mem_safe
    )
    assert res["is_safe"] is False
    assert res["decision"] == "BLOCK"
    assert "Peak utilization exceeds safety threshold" in res["reason"]


# ==============================================================================
# 4. High Volatility -> BLOCK
# ==============================================================================
def test_high_volatility_block():
    """4. Workload with high utilization volatility (Standard Deviation >= 15.0%) -> BLOCK."""
    # Wild swings between 5% and 45%: avg is 22.4% (<30), peak is 45% (<70), but std is 18.7% (>=15%)
    cpu_volatile = [5.0, 42.0, 6.0, 45.0, 7.0, 44.0, 8.0]
    mem_safe = [20.0, 22.0, 21.0, 23.0, 22.0, 21.0, 20.0]

    assert is_safe_to_migrate(cpu_volatile, mem_safe) is False

    res = evaluate_migration_safety(
        instance_id="i-volatile",
        cpu_forecast=cpu_volatile,
        mem_forecast=mem_safe
    )
    assert res["is_safe"] is False
    assert res["decision"] == "BLOCK"
    assert "Workload volatility exceeds safety threshold" in res["reason"]


# ==============================================================================
# 5. Missing Forecast -> BLOCK
# ==============================================================================
def test_missing_forecast_block():
    """5. Missing forecast data in state and arguments -> Fail CLOSED (BLOCK)."""
    state = CO2OpsState(session_id="missing-fc-01")
    state.final_recommendations = "Recommend downsizing i-nofc123456 to t3.micro"
    state.forecast_data = {}  # Empty forecast

    res = evaluate_migration_safety(state=state)
    assert res["is_safe"] is False
    assert res["decision"] == "BLOCK"
    assert "Missing forecast data" in res["reason"]
    assert state.safety_eval["decision"] == "BLOCK"


# ==============================================================================
# 6. Invalid Forecast -> BLOCK
# ==============================================================================
def test_invalid_forecast_block():
    """6. Invalid or unparsable forecast data (NaN, negative, strings, > 100%) -> Fail CLOSED (BLOCK)."""
    # Negative percentage
    assert is_safe_to_migrate([-5.0, 10.0, 12.0, 15.0, 14.0], [20.0, 20.0, 20.0, 20.0, 20.0]) is False

    # Out of bounds (> 100%)
    assert is_safe_to_migrate([150.0, 20.0, 15.0, 12.0, 14.0], [20.0, 20.0, 20.0, 20.0, 20.0]) is False

    # Unparsable string
    assert is_safe_to_migrate("invalid string format", "[20, 20, 20, 20, 20]") is False

    # String with non-numeric items
    res = evaluate_migration_safety(
        instance_id="i-invalid",
        cpu_forecast="[12.0, 'N/A', 14.0, None, 15.0]",
        mem_forecast=[20.0, 22.0, 21.0, 23.0, 22.0]
    )
    assert res["is_safe"] is False
    assert res["decision"] == "BLOCK"
    assert "Invalid forecast data" in res["reason"]


# ==============================================================================
# 7. Missing Telemetry / Synthetic Fallback Data -> BLOCK
# ==============================================================================
def test_missing_telemetry_block():
    """7. Missing telemetry or synthetic fallback data detected -> Fail CLOSED (BLOCK)."""
    # A. Explicit missing telemetry flag
    state1 = CO2OpsState(session_id="missing-telem-01")
    state1.final_recommendations = "Downsize i-001122"
    state1.forecast_data = {"values": [12.0, 14.0, 13.0, 15.0, 14.0], "mem_values": [20.0, 22.0, 21.0, 23.0, 22.0]}
    state1.custom_metadata["missing_telemetry"] = True

    res1 = evaluate_migration_safety(state=state1)
    assert res1["is_safe"] is False
    assert res1["decision"] == "BLOCK"
    assert "Missing telemetry" in res1["reason"]

    # B. Synthetic forecast source
    state2 = CO2OpsState(session_id="synthetic-telem-01")
    state2.final_recommendations = "Downsize i-001122"
    state2.forecast_data = {
        "values": [12.0, 14.0, 13.0, 15.0, 14.0],
        "mem_values": [20.0, 22.0, 21.0, 23.0, 22.0],
        "is_synthetic": True,
        "source": "baseline_synthesis"
    }

    res2 = evaluate_migration_safety(state=state2)
    assert res2["is_safe"] is False
    assert res2["decision"] == "BLOCK"
    assert "Synthetic" in res2["reason"]

    # C. Instance telemetry marked synthetic in infra_data
    state3 = CO2OpsState(session_id="synthetic-infra-01")
    state3.final_recommendations = "Downsize i-001122"
    state3.forecast_data = {"values": [12.0, 14.0, 13.0, 15.0, 14.0], "mem_values": [20.0, 22.0, 21.0, 23.0, 22.0]}
    state3.infra_data = [{"Instance_ID": "i-001122", "is_synthetic": True}]

    res3 = evaluate_migration_safety(state=state3)
    assert res3["is_safe"] is False
    assert res3["decision"] == "BLOCK"
    assert "Synthetic telemetry" in res3["reason"]


# ==============================================================================
# 8. Empty Input -> BLOCK
# ==============================================================================
def test_empty_input_block():
    """8. Empty or insufficient inputs -> Fail CLOSED (BLOCK)."""
    # Empty lists
    assert is_safe_to_migrate([], []) is False
    assert is_safe_to_migrate("", "") is False

    # Fewer than 5 points
    assert is_safe_to_migrate([10.0, 12.0, 11.0], [20.0, 20.0, 20.0]) is False

    # Completely empty evaluate_migration_safety call
    res = evaluate_migration_safety("", state=None)
    assert res["is_safe"] is False
    assert res["decision"] == "BLOCK"
    assert "Empty input" in res["reason"]


# ==============================================================================
# 9. LLM Attempting to Bypass Safety -> BLOCK
# ==============================================================================
def test_llm_attempting_to_bypass_safety_block():
    """9. Validates that when safety evaluates to BLOCK, the LLM cannot bypass the decision."""
    state = CO2OpsState(session_id="bypass-blocked-01")
    state.final_recommendations = "Downsize i-0danger to t3.nano"
    # Unsafe evaluation decision
    state.safety_eval = {
        "instance_id": "i-0danger",
        "is_safe": False,
        "decision": "BLOCK",
        "reason": "CPU peak 82% violates safety threshold."
    }

    mock_boto = MagicMock()
    # LLM hallucinates/ignores instruction and attempts to execute resize anyway
    t1 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "rogue-call-1",
                            "name": "change_machine_type",
                            "input": {"instance_id": "i-0danger", "new_machine_type": "t3.nano"}
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
                    {"text": "Execution was refused due to safety gate rejection."}
                ]
            }
        },
        "stopReason": "end_turn"
    }
    mock_boto.converse.side_effect = [t1, t2]

    agent = BedrockAgent(
        name=executor_agent.name,
        description=executor_agent.description,
        system_instruction=executor_agent.system_instruction,
        model_client=BedrockModelClient(client=mock_boto),
        tools=executor_agent.tools,
        input_state_key=executor_agent.input_state_key,
        output_state_key=executor_agent.output_state_key
    )

    state = agent.run(state)

    # Tool interceptor must catch and strictly block the operation
    assert state.execution_result["status"] == "blocked"
    assert state.execution_result["decision"] == "BLOCK"
    assert "BLOCKED by Safety Gate" in state.execution_result["message"]


# ==============================================================================
# Agent Definitions & Pipeline State Handoff Tests
# ==============================================================================
def test_safety_agent_definition():
    """Validates safety_agent configuration, tools, and state keys."""
    assert isinstance(safety_agent, BedrockAgent)
    assert safety_agent.name == "safety_agent"
    assert len(safety_agent.tools) == 3
    tool_names = [t.__name__ for t in safety_agent.tools]
    assert "evaluate_migration_safety" in tool_names
    assert "is_safe_to_migrate" in tool_names
    assert "get_forecast_information" in tool_names
    assert safety_agent.input_state_key == "impact_analysis"
    assert safety_agent.output_state_key == "safety_eval"


def test_executor_agent_definition():
    """Validates executor_agent configuration, tools, and state keys."""
    assert isinstance(executor_agent, BedrockAgent)
    assert executor_agent.name == "executor_agent"
    assert len(executor_agent.tools) == 1
    assert executor_agent.tools[0].__name__ == "change_machine_type"
    assert executor_agent.input_state_key == "safety_eval"
    assert executor_agent.output_state_key == "execution_result"


def test_safe_executor_pipeline_composition():
    """Validates that safe_executor_agent is a BedrockPipeline composed of safety_agent and executor_agent."""
    assert isinstance(safe_executor_agent, BedrockPipeline)
    assert safe_executor_agent.name == "SafeExecutor"
    assert len(safe_executor_agent.agents) == 2
    assert safe_executor_agent.agents[0] is safety_agent
    assert safe_executor_agent.agents[1] is executor_agent


def test_safety_state_handoff():
    """Tests safety evaluation consuming recommendation, forecast, and impact data from state."""
    state = CO2OpsState(session_id="safety-test-01")
    state.final_recommendations = "Recommend downsizing i-0123456789abcdef0 from m5.xlarge to t3.large in us-east-1."
    state.forecast_data = {
        "status": "success",
        "instance_id": "i-0123456789abcdef0",
        "metric": "cpu",
        "values": [12.5, 14.0, 13.2, 15.1, 14.8, 13.9, 14.2],
        "mem_values": [20.0, 22.0, 21.0, 23.0, 22.0, 21.0, 20.0]
    }
    state.impact_analysis = {
        "monthly_cost_savings": 78.34,
        "monthly_carbon_savings_kg": 1.65
    }

    eval_result = evaluate_migration_safety(state=state)

    assert eval_result["instance_id"] == "i-0123456789abcdef0"
    assert eval_result["is_safe"] is True
    assert eval_result["decision"] == "ALLOW"
    assert eval_result["avg_cpu_forecast"] < 30.0
    assert eval_result["avg_mem_forecast"] < 40.0
    assert eval_result["peak_cpu_forecast"] < 70.0
    assert eval_result["p95_cpu_forecast"] < 45.0
    assert eval_result["volatility_cpu"] < 15.0
    assert state.safety_eval == eval_result
    assert state.safety_eval["decision"] == "ALLOW"
    assert "78.34" in state.safety_eval["impact_summary"]


def test_executor_state_handoff():
    """Tests that executor consumes the approved safety decision from state and executes migration."""
    state = CO2OpsState(session_id="exec-test-01")
    state.final_recommendations = "Recommend downsizing i-0123456789abcdef0 to t3.large."
    state.safety_eval = {
        "instance_id": "i-0123456789abcdef0",
        "is_safe": True,
        "decision": "ALLOW",
        "avg_cpu_forecast": 14.2,
        "avg_mem_forecast": 25.0,
        "reason": "Forecasted utilization is safely below threshold."
    }

    result = change_machine_type(
        instance_id="i-0123456789abcdef0",
        new_machine_type="t3.large",
        region="us-east-1",
        state=state
    )

    assert result["status"] == "success"
    assert result["instance_id"] == "i-0123456789abcdef0"
    assert result["new_machine_type"] == "t3.large"
    assert state.execution_result == result
    assert state.execution_result["status"] == "success"


def test_safety_to_executor_flow_allowed():
    """Tests the full Safety -> Executor pipeline flow when migration is ALLOWED."""
    mock_safety_boto = MagicMock()
    s1 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "safety-call-1",
                            "name": "evaluate_migration_safety",
                            "input": {"instance_id": "i-099887766aabbccdd"}
                        }
                    }
                ]
            }
        },
        "stopReason": "tool_use"
    }
    s2 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"text": "Safety Evaluation PASSED (Decision: ALLOW). All metrics are safely below thresholds. Migration approved."}
                ]
            }
        },
        "stopReason": "end_turn"
    }
    mock_safety_boto.converse.side_effect = [s1, s2]

    mock_exec_boto = MagicMock()
    e1 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "exec-call-1",
                            "name": "change_machine_type",
                            "input": {"instance_id": "i-099887766aabbccdd", "new_machine_type": "t3.large"}
                        }
                    }
                ]
            }
        },
        "stopReason": "tool_use"
    }
    e2 = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"text": "Successfully executed downsizing of i-099887766aabbccdd to t3.large."}
                ]
            }
        },
        "stopReason": "end_turn"
    }
    mock_exec_boto.converse.side_effect = [e1, e2]

    state = CO2OpsState(session_id="pipeline-flow-01")
    state.final_recommendations = "Downsize i-099887766aabbccdd to t3.large"
    state.forecast_data = {
        "instance_id": "i-099887766aabbccdd",
        "metric": "cpu",
        "values": [12.0, 14.0, 15.0, 16.0, 15.0, 14.0, 13.0],
        "mem_values": [20.0, 22.0, 21.0, 23.0, 22.0, 21.0, 20.0]
    }
    state.impact_analysis = {
        "monthly_cost_savings": 80.0,
        "monthly_carbon_savings_kg": 2.0
    }

    test_safety = BedrockAgent(
        name=safety_agent.name,
        description=safety_agent.description,
        system_instruction=safety_agent.system_instruction,
        model_client=BedrockModelClient(client=mock_safety_boto),
        tools=safety_agent.tools,
        input_state_key=safety_agent.input_state_key,
        output_state_key=safety_agent.output_state_key
    )

    test_executor = BedrockAgent(
        name=executor_agent.name,
        description=executor_agent.description,
        system_instruction=executor_agent.system_instruction,
        model_client=BedrockModelClient(client=mock_exec_boto),
        tools=executor_agent.tools,
        input_state_key=executor_agent.input_state_key,
        output_state_key=executor_agent.output_state_key
    )

    pipeline = BedrockPipeline(name="TestSafeExecutor", agents=[test_safety, test_executor])
    final_state = pipeline.run(state=state)

    assert final_state.safety_eval["decision"] == "ALLOW"
    assert final_state.safety_eval["is_safe"] is True
    assert final_state.execution_result["status"] == "success"
    assert final_state.execution_result["instance_id"] == "i-099887766aabbccdd"
    assert final_state.execution_result["new_machine_type"] == "t3.large"
