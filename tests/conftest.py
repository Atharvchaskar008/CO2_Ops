"""
Pytest configuration for CO2Ops test suite.
Provides module mocks for optional packages (google.adk, pptx, lxml)
that may not be installed in the test environment.
"""

import sys
import types
from unittest.mock import MagicMock

# Setup 'google' as a package namespace so subpackages can be safely mocked
if "google" not in sys.modules:
    google_pkg = types.ModuleType("google")
    google_pkg.__path__ = []
    sys.modules["google"] = google_pkg
elif not hasattr(sys.modules["google"], "__path__"):
    sys.modules["google"].__path__ = []


class MockADKAgent:
    """Mock Agent/LlmAgent preserving properties for tests."""
    def __init__(self, name="", **kwargs):
        self.name = name or kwargs.get("name", "")
        self.description = kwargs.get("description", "")
        self.instruction = kwargs.get("instruction", "")
        self.sub_agents = kwargs.get("sub_agents", [])
        for k, v in kwargs.items():
            setattr(self, k, v)


# Mock google.adk if not installed
if "google.adk" not in sys.modules:
    mock_adk = MagicMock()
    mock_adk.Agent = MockADKAgent
    mock_adk.LlmAgent = MockADKAgent
    mock_adk.agents = MagicMock()
    mock_adk.agents.Agent = MockADKAgent
    mock_adk.agents.LlmAgent = MockADKAgent
    mock_adk.tools = MagicMock()
    mock_adk.tools.agent_tool = MagicMock()

    sys.modules["google.adk"] = mock_adk
    sys.modules["google.adk.agents"] = mock_adk.agents
    sys.modules["google.adk.tools"] = mock_adk.tools
    sys.modules["google.adk.tools.agent_tool"] = mock_adk.tools.agent_tool

# Mock google.api_core and googleapiclient if not installed
if "google.api_core" not in sys.modules:
    sys.modules["google.api_core"] = MagicMock()
    sys.modules["google.api_core.client_options"] = MagicMock()

if "googleapiclient" not in sys.modules:
    sys.modules["googleapiclient"] = MagicMock()
    sys.modules["googleapiclient.discovery"] = MagicMock()
    sys.modules["googleapiclient.http"] = MagicMock()

# Mock pptx if not installed
if "pptx" not in sys.modules:
    mock_pptx = MagicMock()
    sys.modules["pptx"] = mock_pptx
    sys.modules["pptx.util"] = MagicMock()
    sys.modules["pptx.dml"] = MagicMock()
    sys.modules["pptx.dml.color"] = MagicMock()
    sys.modules["pptx.enum"] = MagicMock()
    sys.modules["pptx.enum.text"] = MagicMock()

# Mock lxml if not installed
if "lxml" not in sys.modules:
    mock_lxml = MagicMock()
    sys.modules["lxml"] = mock_lxml
    sys.modules["lxml.etree"] = MagicMock()
