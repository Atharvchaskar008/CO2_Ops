"""
CO2Ops - AWS Bedrock Migration Foundation: Pipeline & Orchestrator
Coordinates Bedrock agents, manages multi-step execution flows, and propagates shared CO2OpsState.
"""

import logging
from typing import List, Dict, Any, Optional

from .state import CO2OpsState
from .agent import BedrockAgent
from .client import BedrockModelClient

logger = logging.getLogger(__name__)


class BedrockPipeline:
    """
    Executes a sequence of BedrockAgent steps, threading a single CO2OpsState instance through each.
    Direct replacement for Google ADK's SequentialAgent.
    """

    def __init__(self, name: str, agents: List[BedrockAgent], description: str = ""):
        self.name = name
        self.agents = agents
        self.sub_agents = agents
        self.description = description

    def run(self, state: Optional[CO2OpsState] = None, initial_input: Optional[str] = None) -> CO2OpsState:
        """Runs each agent in the pipeline sequentially, updating state."""
        if state is None:
            state = CO2OpsState()

        current_input = initial_input
        logger.info(f"Starting BedrockPipeline [{self.name}] with {len(self.agents)} agents")

        for idx, agent in enumerate(self.agents):
            logger.info(f"Pipeline [{self.name}] executing step {idx+1}/{len(self.agents)}: {agent.name}")
            state = agent.run(state=state, input_text=current_input)
            # Subsequent agents read from state unless explicitly passed input
            current_input = None

        return state


class BedrockOrchestrator:
    """
    Root orchestrator that routes user requests to specialized Bedrock sub-agents or pipelines.
    Direct replacement for Google ADK's root Agent coordinator.
    """

    def __init__(
        self,
        name: str = "co2ops_orchestrator",
        model_client: Optional[BedrockModelClient] = None,
        agents: Optional[Dict[str, BedrockAgent]] = None,
        pipelines: Optional[Dict[str, BedrockPipeline]] = None
    ):
        self.name = name
        self.model_client = model_client or BedrockModelClient()
        self.agents: Dict[str, BedrockAgent] = agents or {}
        self.pipelines: Dict[str, BedrockPipeline] = pipelines or {}

    def register_agent(self, agent: BedrockAgent) -> None:
        self.agents[agent.name] = agent
        self.agents[agent.name.lower()] = agent

    def register_pipeline(self, pipeline: BedrockPipeline) -> None:
        self.pipelines[pipeline.name] = pipeline
        self.pipelines[pipeline.name.lower()] = pipeline

    def route(self, user_prompt: str) -> Optional[str]:
        """
        Determines the appropriate agent or pipeline name for a given user prompt.
        Can be keyword-based or powered by Bedrock classification.
        """
        prompt_lower = user_prompt.lower()

        if any(w in prompt_lower for w in ["recommend", "optimize", "scout", "audit", "idle"]):
            return "OptimizationAdvisor" if "OptimizationAdvisor" in self.pipelines else "infra_scout"
        elif any(w in prompt_lower for w in ["forecast", "predict", "arima", "future"]):
            return "forecaster"
        elif any(w in prompt_lower for w in ["compare", "price", "emission", "impact", "cost difference"]):
            return "impact_calculator"
        elif any(w in prompt_lower for w in ["migrate", "resize", "execute", "apply"]):
            return "safe_executor"
        elif any(w in prompt_lower for w in ["report", "summary", "weekly", "slide", "deck"]):
            return "weekly_summary"

        return None

    def execute(self, user_prompt: str, state: Optional[CO2OpsState] = None) -> CO2OpsState:
        """
        Routes the prompt to the target agent/pipeline and returns the updated state.
        """
        if state is None:
            state = CO2OpsState()

        state.add_message("user", user_prompt)
        target = self.route(user_prompt)

        if target:
            pipe = self.pipelines.get(target) or self.pipelines.get(target.lower())
            if pipe:
                logger.info(f"Routing to BedrockPipeline: {pipe.name}")
                return pipe.run(state=state, initial_input=user_prompt)

            ag = self.agents.get(target) or self.agents.get(target.lower())
            if ag:
                logger.info(f"Routing to BedrockAgent: {ag.name}")
                return ag.run(state=state, input_text=user_prompt)

        # Fallback: run general response using Bedrock client
        logger.info("Handling prompt with default orchestrator synthesis")
        response = self.model_client.generate_text(
            prompt=user_prompt,
            system="You are the CO2Ops AWS Sustainability Manager. Guide the user on auditing, forecasting, and optimizing AWS compute resources."
        )
        state.add_message("assistant", response)
        return state
