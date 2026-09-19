"""
CO2Ops - AWS Bedrock Migration Foundation: State Management
Defines the shared state container for passing data between Bedrock-based agents.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
import json


@dataclass
class CO2OpsState:
    """
    Shared execution state passed across Bedrock agents in the CO2Ops pipeline.
    Replaces ADK's implicit ToolContext and output_key string injections.
    """
    session_id: str = ""
    user_id: str = ""
    region: str = "us-east-1"

    # Stage 1: Fleet Telemetry & Scout Data
    infra_data: List[Dict[str, Any]] = field(default_factory=list)

    # Stage 2: Profiling & Recommendations
    analysis_results: Optional[str] = None
    final_recommendations: Optional[str] = None

    # Stage 3: Time-Series Forecasting
    forecast_data: Dict[str, Any] = field(default_factory=dict)

    # Stage 4: Safety Evaluation
    safety_eval: Dict[str, Any] = field(default_factory=dict)

    # Stage 5: Cost & Carbon Impact
    impact_analysis: Dict[str, Any] = field(default_factory=dict)

    # Stage 6: Remediation / Execution
    execution_result: Dict[str, Any] = field(default_factory=dict)

    # Stage 7: Reporting & Presentations
    report_metadata: Dict[str, Any] = field(default_factory=dict)
    chart_links: Dict[str, str] = field(default_factory=dict)

    # Interaction History & Context
    messages: List[Dict[str, Any]] = field(default_factory=list)
    custom_metadata: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Dictionary-like accessor for flexible tool/agent access."""
        if hasattr(self, key):
            val = getattr(self, key)
            return val if val is not None else default
        return self.custom_metadata.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Sets an attribute on state or stores in custom_metadata."""
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            self.custom_metadata[key] = value

    def update(self, **kwargs) -> "CO2OpsState":
        """Updates multiple state fields at once."""
        for k, v in kwargs.items():
            self.set(k, v)
        return self

    def add_message(self, role: str, content: str) -> None:
        """Appends a conversation message to the history."""
        self.messages.append({"role": role, "content": content})

    @property
    def conversation_history(self) -> List[Dict[str, Any]]:
        """Alias for messages list to support conversation history access."""
        return self.messages

    @conversation_history.setter
    def conversation_history(self, val: List[Dict[str, Any]]) -> None:
        self.messages = val

    def to_dict(self) -> Dict[str, Any]:
        """Serializes state to a standard Python dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serializes state to JSON string."""
        return json.dumps(self.to_dict(), default=str, indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CO2OpsState":
        """Initializes CO2OpsState from a dictionary."""
        known_fields = {f for f in cls.__dataclass_fields__}
        known_kwargs = {k: v for k, v in data.items() if k in known_fields}
        custom = {k: v for k, v in data.items() if k not in known_fields}
        state = cls(**known_kwargs)
        state.custom_metadata.update(custom)
        return state
