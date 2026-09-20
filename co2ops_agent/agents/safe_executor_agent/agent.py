from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from .tools import change_machine_type, is_safe_to_migrate, get_forecast_information

safe_executor_agent = LlmAgent(
    name="safe_executor_agent",
    model="gemini-2.0-flash",
    description="Safely executes AWS EC2 infrastructure rightsizing from current to target instance type.",
    instruction="""
    You are responsible for validating whether an AWS EC2 instance migration is safe for the given instance ID and executing the migration using the provided tools.

    Steps to follow:
    1. **Forecast CPU and Memory**: Call `get_forecast_information(instance_id)` to get the 7-day forecast for CPU and Memory.
    2. **Decide if migration is safe**: Call `is_safe_to_migrate(cpu_forecast, memory_forecast)`.
    3. **Migrate the Machine Type**: If the decision is safe, call `change_machine_type(instance_id, target_instance_type)` to resize the EC2 instance.
    4. If unsafe (utilization too high): Warn the user and do not proceed with the change.

    Always report the result clearly, including instance ID, old type, new type, and safety status.
    """,
    tools=[
        get_forecast_information,
        is_safe_to_migrate,
        change_machine_type
    ],
    output_key="safe_execution_result"
)
