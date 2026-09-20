"""
CO2Ops - Root Agent and Orchestrator Coordinator (AWS Native)
Coordinates specialized Bedrock agents for EC2 rightsizing, carbon forecasting,
impact evaluation, and safe execution using shared CO2OpsState.
"""

import os
import logging
from .agents.optimization_advisor_agent.agent import optimization_advisor_agent
from .agents.forecaster_agent.agent import forecasting_tool_agent
from .agents.impact_calculator_agent.agent import impact_calculator_agent
from .agents.safe_executor_agent.agent import safe_executor_agent
from .agents.summary_generator_agent.agent import summary_generator_agent
from .secrets_access_manager import access_secret
from .bedrock.agent import BedrockAgent
from .bedrock.orchestrator import BedrockOrchestrator, BedrockPipeline
from .bedrock.state import CO2OpsState

logger = logging.getLogger(__name__)

# Safely initialize API keys from environment or AWS Secrets Manager
climatiq_key = access_secret(secret_id="CLIMATIQ_API_KEY")
if climatiq_key:
    os.environ["CLIMATIQ_API_KEY"] = climatiq_key

# Instantiate the AWS-native Bedrock Orchestrator
orchestrator = BedrockOrchestrator(name="co2ops_orchestrator")

# Register pipelines and agents
if hasattr(optimization_advisor_agent, "agents") or isinstance(optimization_advisor_agent, BedrockPipeline):
    orchestrator.register_pipeline(optimization_advisor_agent)
else:
    orchestrator.register_agent(optimization_advisor_agent)

if hasattr(safe_executor_agent, "agents") or isinstance(safe_executor_agent, BedrockPipeline):
    orchestrator.register_pipeline(safe_executor_agent)
else:
    orchestrator.register_agent(safe_executor_agent)

orchestrator.register_agent(forecasting_tool_agent)
orchestrator.agents["forecaster"] = forecasting_tool_agent

orchestrator.register_agent(impact_calculator_agent)
orchestrator.agents["impact_calculator"] = impact_calculator_agent

orchestrator.register_agent(summary_generator_agent)
orchestrator.agents["weekly_summary"] = summary_generator_agent

# Root coordinator agent instruction
root_instruction = """
You are the CO2Ops manager agent responsible for auditing, forecasting, and optimizing AWS cloud infrastructure for cost and carbon emissions.
You orchestrate the following specialized expert sub-agents:

- `optimization_advisor_agent`: Scans AWS EC2 instances, identifies underutilized and carbon-inefficient resources, and provides actionable rightsizing recommendations.
- `forecasting_tool_agent`: Provides 7-day statistical ARIMA forecasts for CPU utilization, memory utilization, and carbon emissions for AWS EC2 instances.
- `impact_calculator_agent`: Compares hourly and monthly cost and carbon emission differences between two AWS EC2 instance types (e.g. m5.xlarge vs t3.large or Graviton m6g.large).
- `safe_executor_agent`: Performs forecast-validated safe instance migrations (stopping, modifying EC2 instance type attribute, and restarting).
- `summary_generator_agent`: Generates the weekly AWS sustainability executive summary report with embedded charts, saved to Amazon S3.

### Instructions:

1. If the user asks for **recommendations** or infrastructure audit (e.g. "How can I reduce cost in us-east-1?"), call `optimization_advisor_agent`.
2. Once recommendations are returned, ask the user if they wish to apply any recommendation. If the user replies with approval to execute (e.g., "Execute recommendation 1" or "Migrate i-01a2b3c4d5e6f7g80 to m5.large"):
   - Extract the `Instance ID` and `target instance type`.
   - Call `safe_executor_agent` with instructions to migrate the instance.
3. If the user asks about **forecasts** or usage predictions over time, delegate to `forecasting_tool_agent`.
4. If the user asks to **compare impact** between two EC2 instance types or calculate savings, delegate to `impact_calculator_agent`.
5. If the user wants to **generate the weekly summary report** or slides, delegate to `summary_generator_agent`.

ALWAYS clearly mention the AWS sub-agent you are delegating to and provide user-friendly, professional summaries for each action taken.
"""

root_agent = BedrockAgent(
    name="co2ops_agent",
    description="CO2Ops AWS Sustainability and FinOps Manager agent",
    system_instruction=root_instruction
)
root_agent.instruction = root_instruction
root_agent.sub_agents = [
    optimization_advisor_agent,
    forecasting_tool_agent,
    impact_calculator_agent,
    safe_executor_agent,
    summary_generator_agent
]

# Attach orchestrator run/execute methods for seamless invocation
def _root_execute(user_prompt: str, state: CO2OpsState = None) -> CO2OpsState:
    return orchestrator.execute(user_prompt=user_prompt, state=state)

def _root_run(state: CO2OpsState = None, input_text: str = None) -> CO2OpsState:
    prompt = input_text or (state.get_last_user_message() if state else "Run CO2Ops assessment")
    return orchestrator.execute(user_prompt=prompt, state=state)

root_agent.execute = _root_execute
root_agent.run = _root_run
