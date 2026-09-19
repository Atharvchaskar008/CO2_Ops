"""
CO2Ops - AWS Bedrock Migration Foundation: Model Client Wrapper
Wraps the boto3 Bedrock Runtime Converse API for structured LLM interactions.
Uses environment/IAM-based AWS authentication. Never hardcodes credentials.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, Union, Callable

logger = logging.getLogger(__name__)

# Default foundation model: Anthropic Claude Sonnet 4.6 on Amazon Bedrock
DEFAULT_CLAUDE_MODEL_ID = "anthropic.claude-sonnet-4-6"
DEFAULT_BEDROCK_MODEL_ID = DEFAULT_CLAUDE_MODEL_ID


def resolve_aws_region(region_name: Optional[str] = None) -> str:
    """
    Resolves the AWS region from explicit argument, AWS_REGION, or AWS_DEFAULT_REGION.
    """
    if region_name and region_name.strip():
        return region_name.strip()
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"


def resolve_default_model_id(region: Optional[str] = None) -> str:
    """
    Resolves the foundation model ID:
    1. Returns BEDROCK_MODEL_ID environment variable if explicitly configured.
    2. Otherwise defaults to Anthropic Claude Sonnet 4.6 on Amazon Bedrock.
    """
    configured_model = os.getenv("BEDROCK_MODEL_ID")
    if configured_model and configured_model.strip():
        return configured_model.strip()

    return DEFAULT_CLAUDE_MODEL_ID


class BedrockModelClient:
    """
    Reusable client wrapper around the AWS Bedrock Runtime Converse API.
    Handles authentication via IAM roles / standard AWS environment variables.
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        region_name: Optional[str] = None,
        client: Optional[Any] = None
    ):
        """
        Initializes the Bedrock client.
        :param model_id: AWS Bedrock foundation model ID. If omitted, uses BEDROCK_MODEL_ID or region default.
        :param region_name: AWS region. If omitted, uses AWS_REGION / AWS_DEFAULT_REGION.
        :param client: Optional pre-configured boto3 bedrock-runtime client (useful for mocks/tests).
        """
        self.region_name = resolve_aws_region(region_name)
        self.model_id = model_id or resolve_default_model_id(self.region_name)
        self._client = client

    @property
    def client(self) -> Any:
        """Lazily creates and returns the boto3 bedrock-runtime client using IAM / env credentials."""
        if self._client is None:
            import boto3
            self._client = boto3.client("bedrock-runtime", region_name=self.region_name)
        return self._client

    def converse(
        self,
        messages: List[Dict[str, Any]],
        system: Optional[Union[str, List[Dict[str, str]]]] = None,
        inference_config: Optional[Dict[str, Any]] = None,
        tool_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calls the boto3 Bedrock Runtime Converse API.
        
        :param messages: List of messages in Bedrock Converse format [{'role': 'user'|'assistant', 'content': [{'text': ...}]}]
        :param system: Optional system prompt string or list of Bedrock system dicts.
        :param inference_config: Optional inference parameters (maxTokens, temperature, topP).
        :param tool_config: Optional tool specifications in Bedrock format.
        :return: Standardized Bedrock response dictionary.
        """
        # Format system prompt for Bedrock
        bedrock_system = []
        if isinstance(system, str) and system.strip():
            bedrock_system = [{"text": system}]
        elif isinstance(system, list):
            bedrock_system = system

        # Default inference configuration
        inf_config = {
            "maxTokens": 2048,
            "temperature": 0.2,
            "topP": 0.9
        }
        if inference_config:
            inf_config.update(inference_config)

        # Build request parameters
        params: Dict[str, Any] = {
            "modelId": self.model_id,
            "messages": messages,
            "inferenceConfig": inf_config
        }
        if bedrock_system:
            params["system"] = bedrock_system
        if tool_config:
            params["toolConfig"] = tool_config

        logger.debug(f"Calling Bedrock Converse API with model: {self.model_id}")
        return self.client.converse(**params)

    def generate_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048
    ) -> str:
        """
        Convenience method to generate text given a single user prompt.
        """
        messages = [
            {
                "role": "user",
                "content": [{"text": prompt}]
            }
        ]
        inf_config = {
            "temperature": temperature,
            "maxTokens": max_tokens
        }
        response = self.converse(
            messages=messages,
            system=system,
            inference_config=inf_config
        )

        output_message = response.get("output", {}).get("message", {})
        content_parts = output_message.get("content", [])
        text_parts = [p.get("text", "") for p in content_parts if "text" in p]
        return "".join(text_parts).strip()
