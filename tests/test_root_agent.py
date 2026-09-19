import pytest
from co2ops_agent.agent import root_agent
from co2ops_agent.agents.optimization_advisor_agent.agent import optimization_advisor_agent
from co2ops_agent.agents.impact_calculator_agent.agent import impact_calculator_agent
from co2ops_agent.agents.forecaster_agent.agent import forecaster_agent, forecasting_tool_agent
from co2ops_agent.agents.safe_executor_agent.agent import safe_executor_agent
from co2ops_agent.agents.summary_generator_agent.agent import summary_generator_agent
from co2ops_agent.agents.presentation_generator_agent.agent import presentation_generator_agent

def test_root_agent_initialization():
    assert root_agent is not None
    assert root_agent.name == "co2ops_agent"
    assert "AWS" in root_agent.description or "AWS" in root_agent.instruction
    assert "EC2" in root_agent.instruction

def test_sub_agents_attached_to_root():
    sub_agent_names = [agent.name for agent in root_agent.sub_agents]
    assert "OptimizationAdvisor" in sub_agent_names
    assert "impact_calculator_agent" in sub_agent_names
    assert "forecasting_tool_agent" in sub_agent_names
    assert "safe_executor_agent" in sub_agent_names or "SafeExecutor" in sub_agent_names
    assert "weekly_summary_agent" in sub_agent_names

def test_impact_calculator_agent():
    assert impact_calculator_agent.name == "impact_calculator_agent"
    assert "EC2" in impact_calculator_agent.description or "AWS" in impact_calculator_agent.description

def test_forecaster_agent():
    assert forecaster_agent.name == "forecasting_tool_agent"
    assert "EC2" in forecaster_agent.description or "AWS" in forecaster_agent.description

def test_safe_executor_agent():
    assert safe_executor_agent.name in ("safe_executor_agent", "SafeExecutor")
    assert "EC2" in safe_executor_agent.description or "AWS" in safe_executor_agent.description

def test_optimization_advisor_agent():
    assert optimization_advisor_agent.name == "OptimizationAdvisor"
    sub_names = [sa.name for sa in optimization_advisor_agent.sub_agents]
    assert "aws_server_analyst" in sub_names
    assert "workload_profiler" in sub_names

def test_summary_and_presentation_agents():
    assert summary_generator_agent.name == "weekly_summary_agent"
    summary_sub_names = [sa.name for sa in summary_generator_agent.sub_agents]
    assert "weekly_slide_agent" in summary_sub_names
