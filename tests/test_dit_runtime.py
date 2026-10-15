"""DIT regression tests: a truncated stream must surface its actual error;
the pinned Agents SDK must construct real specialist wrappers, not only import."""
import json

import httpx
import pytest


@pytest.mark.asyncio
async def test_chat_context_failure_emits_correlated_error_frame():
    from jarvis.app import app

    class BrokenOperator:
        async def radar(self, _n):
            raise RuntimeError("injected research-context failure")

    class Runtime:
        operator = BrokenOperator()

    previous = getattr(app.state, "runtime", None)
    app.state.runtime = Runtime()
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post("/api/chat", json={"message": "test context failure", "mode": "fast", "identity_key": "GHOST_001"})
        assert response.status_code == 200
        frames = [json.loads(line) for line in response.text.splitlines() if line.strip()]
        assert frames[0]["type"] == "state"
        errors = [frame for frame in frames if frame.get("type") == "error"]
        assert len(errors) == 1
        assert errors[0]["phase"] == "context"
        assert "injected research-context failure" in errors[0]["text"]
        assert errors[0]["request_id"] == frames[0]["request_id"]
        assert not any(frame["type"] == "done" for frame in frames)
    finally:
        if previous is None:
            del app.state.runtime
        else:
            app.state.runtime = previous


@pytest.mark.asyncio
async def test_pinned_agents_sdk_constructs_actual_dit_specialists():
    pytest.importorskip("agents")
    from jarvis.config import Settings
    from jarvis.runtime import JarvisRuntime
    runtime = JarvisRuntime(Settings.from_env())
    runtime.ollama.models = [{"name": "test-installed:4b", "parameter_billions": 4}]
    try:
        team = runtime.agents._team()
        assert team is not None, runtime.agents.status()
        assert len(team["manager_lite"].tools) == 7
        assert all(tool.name.startswith("ask_") for tool in team["manager_lite"].tools)
        assert team["OpenAIChatCompletionsModel"] is not None
    finally:
        if runtime.agents._team_cache:
            await runtime.agents._team_cache[1]["client"].close()
        await runtime.ollama.close()
        await runtime.risk.close()
        await runtime.sense.close()

@pytest.mark.asyncio
async def test_dit_lite_skips_expensive_radar_and_streams_its_single_turn():
    from jarvis.app import app
    class Operator:
        async def radar(self, _): raise AssertionError("lite must not poll radar")
        async def append_chat(self, *args): return None
    class Agent:
        async def ask(self, message, identity_key, mode, model_override=None, operator_context=None):
            assert mode == 'lite'
            assert operator_context == {}
            return '{"name":"Cyberghost","ticker":"GHOST"}'
    class Runtime:
        operator=Operator()
        agents=Agent()
    previous=getattr(app.state,'runtime',None)
    app.state.runtime=Runtime()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
            response=await client.post('/api/chat',json={'message':'Pitch from pre-scanned data','mode':'lite','identity_key':'GHOST_001','model':'qwen3.5:4b'})
        assert response.status_code == 200
        frames=[json.loads(line) for line in response.text.splitlines() if line.strip()]
        assert [r['type'] for r in frames]==['state','answer','done']
    finally:
        if previous is None: del app.state.runtime
        else: app.state.runtime=previous
