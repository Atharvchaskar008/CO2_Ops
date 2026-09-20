"""
CO2Ops - AWS Bedrock Foundation: BedrockAgent
Base class for agents running on AWS Bedrock Converse API with structured state management.
"""

import inspect
import json
import logging
from typing import List, Dict, Any, Optional, Callable, Union

from .state import CO2OpsState
from .client import BedrockModelClient

logger = logging.getLogger(__name__)


def python_func_to_bedrock_tool_spec(func: Callable) -> Dict[str, Any]:
    """
    Introspects a Python function's signature and docstring to produce a Bedrock toolSpec.
    """
    sig = inspect.signature(func)
    doc = inspect.getdoc(func) or f"Executes {func.__name__}"
    
    properties = {}
    required = []

    type_mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object"
    }

    for name, param in sig.parameters.items():
        if name in ("state", "tool_context"):
            continue  # Injected runtime context, not a model parameter
        
        param_type = "string"
        if param.annotation in type_mapping:
            param_type = type_mapping[param.annotation]

        properties[name] = {
            "type": param_type,
            "description": f"Parameter {name}"
        }

        if param.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "toolSpec": {
            "name": func.__name__,
            "description": doc.split("\n")[0][:250],
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
    }


class BedrockAgent:
    """
    An AWS Bedrock-native agent that processes input, executes registered tools,
    and reads/writes to a shared CO2OpsState container.
    """

    def __init__(
        self,
        name: str,
        description: str,
        system_instruction: str,
        model_client: Optional[BedrockModelClient] = None,
        tools: Optional[List[Callable]] = None,
        input_state_key: Optional[str] = None,
        output_state_key: Optional[str] = None
    ):
        self.name = name
        self.description = description
        self.system_instruction = system_instruction
        self.model_client = model_client or BedrockModelClient()
        self.tools = tools or []
        self.input_state_key = input_state_key
        self.output_state_key = output_state_key

        self._tool_map: Dict[str, Callable] = {f.__name__: f for f in self.tools}
        self._bedrock_tool_config = self._build_tool_config()

    def _build_tool_config(self) -> Optional[Dict[str, Any]]:
        if not self.tools:
            return None
        return {
            "tools": [python_func_to_bedrock_tool_spec(f) for f in self.tools]
        }

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any], state: CO2OpsState) -> Any:
        """Executes a registered Python tool with state injection if requested."""
        if tool_name not in self._tool_map:
            raise ValueError(f"Tool {tool_name} not found in agent {self.name}")

        func = self._tool_map[tool_name]
        sig = inspect.signature(func)
        
        # Inject state if parameter exists
        kwargs = dict(tool_input)
        if "state" in sig.parameters:
            kwargs["state"] = state

        logger.info(f"Agent [{self.name}] executing tool [{tool_name}] with args: {kwargs}")
        return func(**kwargs)

    def run(self, state: CO2OpsState, input_text: Optional[str] = None) -> CO2OpsState:
        """
        Executes a reasoning turn with the Bedrock model and updates state.
        """
        # Determine effective prompt
        prompt = input_text
        if not prompt and self.input_state_key:
            state_val = state.get(self.input_state_key)
            if state_val:
                prompt = str(state_val)
            elif self.input_state_key == "forecast_data" and state.final_recommendations:
                prompt = str(state.final_recommendations)
            elif self.input_state_key in ("safety_eval", "impact_analysis") and state.final_recommendations:
                prompt = str(state.final_recommendations)

        if not prompt:
            prompt = "Proceed with your specialized task based on the current state."

        # Safely interpolate known state keys into system instruction and prompt
        effective_system = self.system_instruction
        state_dict = state.to_dict()
        state_dict.update(state.custom_metadata)
        for k, v in state_dict.items():
            token = f"{{{k}}}"
            if token in effective_system:
                effective_system = effective_system.replace(token, str(v))
            if token in prompt:
                prompt = prompt.replace(token, str(v))

        messages = [
            {
                "role": "user",
                "content": [{"text": prompt}]
            }
        ]

        logger.info(f"Running BedrockAgent [{self.name}]")

        # Initial call to Bedrock
        response = self.model_client.converse(
            messages=messages,
            system=effective_system,
            tool_config=self._bedrock_tool_config
        )

        stop_reason = response.get("stopReason")
        output_message = response.get("output", {}).get("message", {})

        # Handle tool execution loop if Bedrock requested a tool use
        max_tool_turns = 5
        turn_count = 0

        while stop_reason == "tool_use" and turn_count < max_tool_turns:
            turn_count += 1
            messages.append(output_message)

            tool_results = []
            for part in output_message.get("content", []):
                if "toolUse" in part:
                    tool_use = part["toolUse"]
                    tool_name = tool_use.get("name")
                    tool_id = tool_use.get("toolUseId")
                    tool_args = tool_use.get("input", {})

                    try:
                        raw_result = self.execute_tool(tool_name, tool_args, state)
                        result_content = [{"json": raw_result} if isinstance(raw_result, dict) else {"text": str(raw_result)}]
                        status = "success"
                    except Exception as err:
                        logger.error(f"Error executing tool {tool_name}: {err}")
                        result_content = [{"text": f"Error executing {tool_name}: {str(err)}"}]
                        status = "error"

                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_id,
                            "content": result_content,
                            "status": status
                        }
                    })

            messages.append({
                "role": "user",
                "content": tool_results
            })

            # Re-converse with tool results
            response = self.model_client.converse(
                messages=messages,
                system=self.system_instruction,
                tool_config=self._bedrock_tool_config
            )
            stop_reason = response.get("stopReason")
            output_message = response.get("output", {}).get("message", {})

        # Extract final response text
        final_text = ""
        for part in output_message.get("content", []):
            if "text" in part:
                final_text += part["text"]

        final_text = final_text.strip()

        # Update state with agent output
        if self.output_state_key:
            if self.output_state_key == "infra_data" and state.infra_data:
                state.set("infra_summary", final_text)
            elif self.output_state_key == "forecast_data":
                if isinstance(state.forecast_data, dict):
                    state.forecast_data["summary"] = final_text
                else:
                    state.forecast_data = {"summary": final_text}
                state.set("forecast_summary", final_text)
            elif self.output_state_key == "impact_analysis":
                if isinstance(state.impact_analysis, dict):
                    state.impact_analysis["summary"] = final_text
                else:
                    state.impact_analysis = {"summary": final_text}
                state.set("impact_summary", final_text)
            elif self.output_state_key == "safety_eval":
                if isinstance(state.safety_eval, dict):
                    state.safety_eval["summary"] = final_text
                else:
                    state.safety_eval = {"summary": final_text}
                state.set("safety_summary", final_text)
            elif self.output_state_key == "execution_result":
                if isinstance(state.execution_result, dict):
                    state.execution_result["summary"] = final_text
                else:
                    state.execution_result = {"summary": final_text}
                state.set("execution_summary", final_text)
            else:
                state.set(self.output_state_key, final_text)

        state.add_message("assistant", final_text)
        return state
