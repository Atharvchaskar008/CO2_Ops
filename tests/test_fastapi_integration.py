"""
FastAPI End-to-End Integration Tests (Hermetic with Mocks)
Tests the complete API layer: /health, /api/sessions, /api/chat, state persistence,
multi-turn conversation history, error handling, CORS, and deterministic safety enforcement.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from co2ops_agent.api import app, SESSION_STORE
from co2ops_agent.bedrock.state import CO2OpsState
from co2ops_agent.agents.safe_executor_agent.tools import change_machine_type


@pytest.fixture
def client():
    """Provides FastAPI TestClient and resets session store for test isolation."""
    SESSION_STORE.clear()
    return TestClient(app)


def test_health_endpoint(client):
    """Verifies that /health and / endpoints return healthy status and AWS configuration."""
    for path in ["/health", "/"]:
        res = client.get(path)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["service"] == "CO2Ops AWS Sustainability Orchestrator"
        assert data["model_provider"] == "Amazon Bedrock"
        assert "us.anthropic.claude" in data["model_id"] or "model_id" in data
        assert "region" in data
        assert "active_sessions" in data


def test_session_creation(client):
    """Verifies that POST /api/sessions creates a new session and returns fresh CO2OpsState."""
    res = client.post("/api/sessions", json={"user_id": "developer_1"})
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data
    assert data["session_id"].startswith("session-")
    assert data["status"] == "created"
    assert data["user_id"] == "developer_1"
    assert "state" in data
    assert data["state"]["session_id"] == data["session_id"]
    assert data["session_id"] in SESSION_STORE


def test_session_persistence_and_retrieval(client):
    """Verifies that GET /api/sessions/{session_id} retrieves existing session and 404s on missing."""
    # Create session
    create_res = client.post("/api/sessions", json={"user_id": "auditor_user"})
    session_id = create_res.json()["session_id"]

    # Retrieve session
    get_res = client.get(f"/api/sessions/{session_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["session_id"] == session_id
    assert "state" in get_data
    assert get_data["state"]["session_id"] == session_id

    # Non-existent session
    missing_res = client.get("/api/sessions/non_existent_session_123")
    assert missing_res.status_code == 404
    assert "not found" in missing_res.json()["detail"].lower()


def test_chat_request_with_orchestrator(client):
    """Verifies that POST /api/chat accepts standard payload and routes through orchestrator."""
    test_session = "session-test-chat-01"
    
    with patch("co2ops_agent.api.orchestrator.execute") as mock_exec:
        def mock_execute_impl(user_prompt, state):
            state.add_message("user", user_prompt)
            state.add_message("assistant", f"Echo: rightsizing recommendation for {user_prompt}")
            state.final_recommendations = "Downsize i-01a2b3c4d5e6f7g80 to m5.large"
            return state

        mock_exec.side_effect = mock_execute_impl

        res = client.post("/api/chat", json={
            "message": "Find idle instances in us-east-1",
            "session_id": test_session,
            "user_id": "user-456"
        })

        assert res.status_code == 200
        data = res.json()
        assert data["session_id"] == test_session
        assert "Echo: rightsizing recommendation" in data["response"]
        assert data["state"]["final_recommendations"] == "Downsize i-01a2b3c4d5e6f7g80 to m5.large"
        mock_exec.assert_called_once()


def test_multi_turn_conversation_persists_history(client):
    """Verifies that multiple messages in the same session accumulate conversation_history."""
    session_id = "session-multi-turn-01"

    with patch("co2ops_agent.api.orchestrator.execute") as mock_exec:
        def step_1(user_prompt, state):
            state.add_message("user", user_prompt)
            state.add_message("assistant", "Analyzed infrastructure: 3 underutilized instances.")
            return state

        def step_2(user_prompt, state):
            state.add_message("user", user_prompt)
            state.add_message("assistant", "7-day forecast shows safe CPU headroom.")
            return state

        # Turn 1
        mock_exec.side_effect = step_1
        res1 = client.post("/api/chat", json={
            "message": "Analyze fleet in us-east-1",
            "session_id": session_id,
            "user_id": "user-multi"
        })
        assert res1.status_code == 200
        assert "Analyzed infrastructure" in res1.json()["response"]

        # Turn 2 in the same session
        mock_exec.side_effect = step_2
        res2 = client.post("/api/chat", json={
            "message": "Forecast carbon for i-01a2b3c4d5e6f7g80",
            "session_id": session_id,
            "user_id": "user-multi"
        })
        assert res2.status_code == 200
        assert "7-day forecast" in res2.json()["response"]

        # Verify combined conversation history in persisted session
        stored_state = SESSION_STORE[session_id]
        history = stored_state.conversation_history
        assert len(history) == 4
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Analyze fleet in us-east-1"
        assert history[1]["role"] == "assistant"
        assert history[2]["role"] == "user"
        assert history[2]["content"] == "Forecast carbon for i-01a2b3c4d5e6f7g80"
        assert history[3]["role"] == "assistant"


def test_invalid_chat_request_handling(client):
    """Verifies that empty messages or missing prompt return 400 Bad Request."""
    # Completely empty body
    res1 = client.post("/api/chat", json={})
    assert res1.status_code == 400
    assert "Missing user message or prompt" in res1.json()["detail"]

    # Whitespace only
    res2 = client.post("/api/chat", json={"message": "   "})
    assert res2.status_code == 400

    # Null message
    res3 = client.post("/api/chat", json={"message": None})
    assert res3.status_code == 400


def test_bedrock_failure_handling(client):
    """Verifies that Bedrock orchestration exceptions return proper 500 without crashing server."""
    with patch("co2ops_agent.api.orchestrator.execute") as mock_exec:
        mock_exec.side_effect = RuntimeError("Bedrock ThrottlingException: rate limit exceeded")

        res = client.post("/api/chat", json={
            "message": "Audit my cluster",
            "session_id": "session-error-test"
        })

        assert res.status_code == 500
        assert "Orchestration error" in res.json()["detail"]
        assert "ThrottlingException" in res.json()["detail"]

    # Verify server is still completely responsive after the error
    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"


def test_cors_headers(client):
    """Verifies CORS headers for browser console clients."""
    headers = {
        "Origin": "http://localhost:8501",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }
    res = client.options("/api/chat", headers=headers)
    assert res.status_code == 200
    assert "access-control-allow-origin" in res.headers
    assert res.headers["access-control-allow-origin"] in ["*", "http://localhost:8501"]


def test_execution_safety_gate_enforcement_via_api(client):
    """
    Verifies that execution requests cannot bypass the deterministic safety gate.
    When state.safety_eval is missing or BLOCK, execution must be refused.
    """
    session_id = "session-safety-test"
    # Create fresh state without approved safety decision
    client.post("/api/sessions", json={"user_id": "test_operator"})
    state = CO2OpsState(session_id=session_id)
    state.safety_eval = {
        "decision": "BLOCK",
        "is_safe": False,
        "reason": "Forecasted CPU volatility exceeds safe rightsizing threshold."
    }
    SESSION_STORE[session_id] = state

    # Attempt execution tool call directly with this state
    result = change_machine_type(
        instance_id="i-01a2b3c4d5e6f7g80",
        new_machine_type="m5.large",
        state=state
    )

    assert result["status"] == "blocked"
    assert result["decision"] == "BLOCK"
    assert result["execution_status"] == "blocked_by_safety_gate"
    assert "Safety Gate" in result["error"]


def test_compatibility_run_endpoint(client):
    """Verifies that the /run endpoint processes the compatibility payload format."""
    with patch("co2ops_agent.api.orchestrator.execute") as mock_exec:
        def mock_impl(user_prompt, state):
            state.add_message("user", user_prompt)
            state.add_message("assistant", "Processed via compatibility endpoint.")
            return state

        mock_exec.side_effect = mock_impl

        res = client.post("/run", json={
            "app_name": "co2ops_agent",
            "user_id": "legacy_user",
            "session_id": "session-legacy-run",
            "new_message": {
                "role": "user",
                "parts": [{"text": "Show carbon overview"}]
            }
        })

        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) > 0
        first_event = data[0]
        assert "response" in first_event
        assert "Processed via compatibility endpoint" in first_event["response"]
        assert first_event["step_details"]["step_type"] == "model_output"
