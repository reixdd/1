"""DIT lite does one bounded local model call; no multi-agent/tool turns."""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest


@pytest.mark.asyncio
async def test_lite_direct_ollama_single_turn(monkeypatch):
    from jarvis.agent_team import AgentTeam
    real = httpx.AsyncClient
    calls = []
    async def responder(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert request.url.path == '/api/chat'
        return httpx.Response(200, json={'message': {'content': '{"name":"Cyberghost","ticker":"GHOST"}'}})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda *a, **kw: real(transport=httpx.MockTransport(responder), **kw))
    class Team(AgentTeam):
        settings = SimpleNamespace(ollama_url='http://127.0.0.1:11434')
        catalog = SimpleNamespace(models=[{'name':'qwen3.5:4b'}], selection=lambda: {'fast':'qwen3.5:4b'})
        metrics = SimpleNamespace(inc=lambda *a: None, observe=lambda *a: None)
        _dit_slots = asyncio.Semaphore(1)
        _team = lambda self: (_ for _ in ()).throw(AssertionError('No Agents SDK for lite'))
    answer = await Team.ask(object.__new__(Team), 'Create one brief evidenced concept', 'GHOST_001', 'lite', model_override='qwen3.5:4b', operator_context={'radar':'huge duplicate'})
    assert 'Cyberghost' in answer
    assert len(calls) == 1
    assert calls[0]['stream'] is False
    assert calls[0]['think'] is False
    assert calls[0]['options']['num_predict'] <= 512
    assert all('huge duplicate' not in m['content'] for m in calls[0]['messages'])
