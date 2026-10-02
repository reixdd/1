from __future__ import annotations

import pytest


def test_openai_agents_sdk_surface_is_available_when_installed():
    agents = pytest.importorskip("agents")
    for name in ("Agent", "Runner", "AsyncOpenAI", "OpenAIChatCompletionsModel", "function_tool", "set_tracing_disabled"):
        assert hasattr(agents, name), name
