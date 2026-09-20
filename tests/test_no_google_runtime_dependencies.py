"""
Repository-Level Enforcement Test: No Google/GCP Active Runtime Dependencies
Ensures that all ACTIVE runtime code in co2ops_agent/ is fully AWS-native,
and does not import google.adk, google.generativeai, or googleapiclient.
"""

import ast
import os
import pytest
from pathlib import Path

FORBIDDEN_MODULES = [
    "google.adk",
    "google.generativeai",
    "googleapiclient",
    "google.oauth2",
    "google.cloud"
]


def get_all_agent_python_files():
    """Finds all python files in the active runtime directory (co2ops_agent/)."""
    root_dir = Path(__file__).parent.parent / "co2ops_agent"
    return list(root_dir.rglob("*.py"))


def test_no_forbidden_google_imports_in_active_runtime():
    """
    Parses the AST of every Python file in co2ops_agent/ to assert
    zero imports of google.adk, google.generativeai, googleapiclient, etc.
    """
    py_files = get_all_agent_python_files()
    assert len(py_files) > 0, "No Python files found in co2ops_agent/"

    violations = []

    for file_path in py_files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(file_path))

        for node in ast.walk(tree):
            # Check `import X`
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in FORBIDDEN_MODULES:
                        if alias.name == forbidden or alias.name.startswith(forbidden + "."):
                            violations.append(f"{file_path.name}:{node.lineno} imports '{alias.name}'")

            # Check `from X import Y`
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                for forbidden in FORBIDDEN_MODULES:
                    if module_name == forbidden or module_name.startswith(forbidden + "."):
                        violations.append(f"{file_path.name}:{node.lineno} imports from '{module_name}'")

    assert not violations, f"Forbidden Google runtime dependencies detected:\n" + "\n".join(violations)


def test_requirements_txt_has_no_google_dependencies():
    """Verifies that co2ops_agent/requirements.txt contains no google packages."""
    req_file = Path(__file__).parent.parent / "co2ops_agent" / "requirements.txt"
    assert req_file.exists(), "co2ops_agent/requirements.txt does not exist"

    with open(req_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        cleaned = line.strip().lower()
        if not cleaned or cleaned.startswith("#"):
            continue
        for forbidden in ["google-adk", "google-generativeai", "google-api-python-client", "google-cloud"]:
            assert not cleaned.startswith(forbidden), f"Found forbidden dependency in requirements.txt: {line.strip()}"


def test_root_agent_is_aws_native():
    """Verifies that root_agent and orchestrator are AWS Bedrock-native."""
    from co2ops_agent.agent import root_agent, orchestrator
    from co2ops_agent.bedrock.agent import BedrockAgent
    from co2ops_agent.bedrock.orchestrator import BedrockOrchestrator

    assert root_agent is not None
    assert isinstance(root_agent, BedrockAgent)
    assert root_agent.name == "co2ops_agent"
    assert isinstance(orchestrator, BedrockOrchestrator)
    assert "AWS" in root_agent.instruction
    assert "EC2" in root_agent.instruction


def test_fastapi_backend_endpoints():
    """Verifies that the FastAPI application is correctly structured and configured."""
    from co2ops_agent.api import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Health check
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["model_provider"] == "Amazon Bedrock"

    # Session creation
    sess_res = client.post("/api/sessions", json={"user_id": "test-user"})
    assert sess_res.status_code == 200
    sess_data = sess_res.json()
    assert "session_id" in sess_data
    session_id = sess_data["session_id"]

    # Legacy endpoint backwards-compatibility
    legacy_sess = client.post(f"/apps/co2ops_agent/users/test-user/sessions/{session_id}")
    assert legacy_sess.status_code == 200
