"""
CO2Ops AWS Sustainability Backend - FastAPI Application
Provides REST endpoints for the Frontend Console and external integrations,
orchestrating AWS Bedrock agents and managing CO2OpsState session state.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from co2ops_agent.bedrock.state import CO2OpsState
from co2ops_agent.agent import root_agent, orchestrator

logger = logging.getLogger("co2ops_api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="CO2Ops AWS Sustainability API",
    description="AWS-native API server orchestrating Bedrock AI agents for cloud carbon and cost optimization",
    version="2.0.0"
)

# Enable CORS for frontend clients (supporting localhost and deployed origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store mapping session_id -> CO2OpsState
SESSION_STORE: Dict[str, CO2OpsState] = {}


class ChatRequest(BaseModel):
    message: Optional[str] = None
    prompt: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    # Backwards-compatibility with ADK payload format
    app_name: Optional[str] = None
    new_message: Optional[Dict[str, Any]] = None


class SessionCreateRequest(BaseModel):
    user_id: Optional[str] = "default_user"
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


@app.get("/")
@app.get("/health")
def health_check():
    """Health check endpoint for container healthchecks and status monitoring."""
    return {
        "status": "healthy",
        "service": "CO2Ops AWS Sustainability Orchestrator",
        "model_provider": "Amazon Bedrock",
        "model_id": os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-sonnet-20241022-v2:0"),
        "region": os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
        "active_sessions": len(SESSION_STORE)
    }


def _get_or_create_state(session_id: Optional[str]) -> tuple[str, CO2OpsState]:
    if not session_id:
        import uuid
        session_id = f"session-{uuid.uuid4().hex[:8]}"

    if session_id not in SESSION_STORE:
        SESSION_STORE[session_id] = CO2OpsState(session_id=session_id)
        logger.info(f"Initialized new CO2OpsState for session: {session_id}")

    return session_id, SESSION_STORE[session_id]


def _extract_prompt_text(req: ChatRequest) -> str:
    """Extracts user prompt from standard or legacy payload."""
    if req.message and req.message.strip():
        return req.message.strip()
    if req.prompt and req.prompt.strip():
        return req.prompt.strip()
    if req.new_message and isinstance(req.new_message, dict):
        parts = req.new_message.get("parts", [])
        extracted = []
        for part in parts:
            if isinstance(part, dict) and "text" in part:
                extracted.append(part["text"])
            elif isinstance(part, str):
                extracted.append(part)
        if extracted:
            return " ".join(extracted).strip()
    return ""


@app.post("/api/sessions")
def create_session(req: Optional[SessionCreateRequest] = None):
    """Creates a new session and returns its ID and fresh CO2OpsState."""
    import uuid
    session_id = f"session-{uuid.uuid4().hex[:8]}"
    SESSION_STORE[session_id] = CO2OpsState(session_id=session_id)
    return {
        "session_id": session_id,
        "status": "created",
        "user_id": req.user_id if req else "default_user",
        "state": SESSION_STORE[session_id].to_dict()
    }


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    """Retrieves an existing session state or 404 if not found."""
    if session_id not in SESSION_STORE:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return {
        "session_id": session_id,
        "state": SESSION_STORE[session_id].to_dict()
    }


@app.post("/apps/{app_name}/users/{user_id}/sessions/{session_id}")
def init_session_legacy(app_name: str, user_id: str, session_id: str):
    """Legacy session initialization endpoint for frontend backwards-compatibility."""
    if session_id not in SESSION_STORE:
        SESSION_STORE[session_id] = CO2OpsState(session_id=session_id)
    return {
        "id": session_id,
        "app_name": app_name,
        "user_id": user_id,
        "state": SESSION_STORE[session_id].to_dict()
    }


@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    """Native REST chat endpoint with state persistence and Bedrock error handling."""
    user_prompt = _extract_prompt_text(req)
    if not user_prompt:
        raise HTTPException(status_code=400, detail="Missing user message or prompt.")

    session_id, state = _get_or_create_state(req.session_id)

    # Route through the orchestrator with error handling
    try:
        updated_state = orchestrator.execute(user_prompt=user_prompt, state=state)
        SESSION_STORE[session_id] = updated_state
    except Exception as err:
        logger.error(f"Error executing orchestrator for session {session_id}: {err}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Orchestration error: {str(err)}")

    # Get the latest assistant response
    assistant_text = ""
    history = getattr(updated_state, "messages", None) or getattr(updated_state, "conversation_history", []) or []
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            assistant_text = msg.get("content", "")
            break

    return {
        "response": assistant_text,
        "session_id": session_id,
        "state": updated_state.to_dict()
    }


@app.post("/run")
def run_endpoint(req: ChatRequest):
    """
    [Compatibility-Only] Unified run endpoint supporting legacy frontend and ADK payload formats.
    Returns response in a structure compatible with both frontend styles.
    """
    user_prompt = _extract_prompt_text(req)
    if not user_prompt:
        raise HTTPException(status_code=400, detail="Missing user prompt.")

    session_id, state = _get_or_create_state(req.session_id)

    # Route prompt through orchestrator with error handling
    try:
        updated_state = orchestrator.execute(user_prompt=user_prompt, state=state)
        SESSION_STORE[session_id] = updated_state
    except Exception as err:
        logger.error(f"Error executing orchestrator for session {session_id}: {err}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Orchestration error: {str(err)}")

    assistant_text = ""
    history = getattr(updated_state, "messages", None) or getattr(updated_state, "conversation_history", []) or []
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            assistant_text = msg.get("content", "")
            break

    if not assistant_text:
        assistant_text = "Action processed by CO2Ops Bedrock Orchestrator."

    # Return response structured so both clean JSON clients and event-expecting clients parse it
    return [
        {
            "content": {
                "parts": [{"text": assistant_text}],
                "role": "model"
            },
            "step_details": {
                "step_type": "model_output",
                "model_output": {
                    "parts": [{"text": assistant_text}]
                }
            },
            "session_id": session_id,
            "response": assistant_text
        }
    ]
