from .sub_agents.infra_scout_agent.agent import infra_scout_agent
from .sub_agents.workload_profiler_agent.agent import workload_profiler_agent
from .sub_agents.recommender_agent.agent import infra_recommender_agent

from co2ops_agent.bedrock.orchestrator import BedrockPipeline

# Create the Bedrock pipeline orchestrating scout -> profiler -> recommender
optimization_advisor_agent = BedrockPipeline(
    name="OptimizationAdvisor",
    agents=[infra_scout_agent, workload_profiler_agent, infra_recommender_agent],
    description="A pipeline that recommends optimization for the infrastructure",
)