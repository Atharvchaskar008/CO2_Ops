"""
CO2Ops - AWS Safe Executor Agent and BedrockPipeline
Coordinates safety evaluation and hardened AWS EC2 rightsizing execution.
"""

from co2ops_agent.bedrock.agent import BedrockAgent
from co2ops_agent.bedrock.orchestrator import BedrockPipeline
from .tools import (
    change_machine_type,
    is_safe_to_migrate,
    get_forecast_information,
    evaluate_migration_safety
)

# 1. Safety Agent: Evaluates forecast and impact data to produce ALLOW or BLOCK decision
safety_agent = BedrockAgent(
    name="safety_agent",
    description="Validates whether an AWS EC2 instance rightsizing migration is safe based on forecasted CPU/Memory utilization and projected impact.",
    system_instruction="""
    You are the AWS Infrastructure Safety Evaluation Agent.
    Your responsibility is to strictly evaluate whether a proposed EC2 instance rightsizing is safe before execution.

    Context from pipeline state:
    Recommendations: {final_recommendations}
    Forecast Data: {forecast_data}
    Impact Analysis: {impact_analysis}

    Your rules:
    1. Extract the Instance ID from recommendations or forecast data.
    2. Call `evaluate_migration_safety` to test forecasted CPU (<30%) and Memory (<40%) against safety thresholds.
    3. If safe, the decision is 'ALLOW'.
    4. If unsafe, the decision is 'BLOCK' to avoid cloud performance degradation.
    5. Summarize the safety evaluation, clearly stating whether the migration is ALLOWED or BLOCKED, the average forecasted metrics, and the reason.
    """,
    tools=[
        evaluate_migration_safety,
        is_safe_to_migrate,
        get_forecast_information
    ],
    input_state_key="impact_analysis",
    output_state_key="safety_eval"
)

# 2. Executor Agent: Consumes safety decision and executes migration only if approved
executor_agent = BedrockAgent(
    name="executor_agent",
    description="Executes approved AWS EC2 instance rightsizing migrations after validating the safety gate decision.",
    system_instruction="""
    You are the AWS EC2 Rightsizing Execution Agent.
    Your responsibility is to execute instance rightsizing migrations only when approved by the Safety Gate.

    Context from pipeline state:
    Safety Evaluation: {safety_eval}
    Recommendations: {final_recommendations}

    Your strict rules:
    1. Check the safety evaluation decision in `{safety_eval}`.
    2. If decision is 'BLOCK' or unsafe:
       - DO NOT call `change_machine_type`.
       - Report that execution is BLOCKED by the safety evaluation and state the reason.
    3. If decision is 'ALLOW' and safe:
       - Extract the instance ID and target machine type from recommendations.
       - Call `change_machine_type` to resize the instance.
       - Report the execution status, instance ID, new machine type, and AWS operation result.
    """,
    tools=[
        change_machine_type
    ],
    input_state_key="safety_eval",
    output_state_key="execution_result"
)

# 3. Composite Pipeline: Safe Executor Agent
safe_executor_agent = BedrockPipeline(
    name="SafeExecutor",
    agents=[safety_agent, executor_agent],
    description="Pipeline that evaluates migration safety and executes EC2 instance rightsizing."
)

# Compatibility attributes
safe_executor_agent.tools = [
    evaluate_migration_safety,
    is_safe_to_migrate,
    get_forecast_information,
    change_machine_type
]
safe_executor_agent.output_key = "execution_result"
