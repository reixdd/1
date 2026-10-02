from fastapi.testclient import TestClient

from jarvis.app import create_app


def test_root_describes_clean_step3(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("JARVIS_HISTORY_DIR", str(tmp_path / "history"))
    # Make provider startup delays long so this is an API shape test, not a live network test.
    monkeypatch.setenv("JARVIS_GECKO_NEW_INTERVAL_SECONDS", "9999")
    monkeypatch.setenv("JARVIS_GECKO_TRENDING_INTERVAL_SECONDS", "9999")
    monkeypatch.setenv("JARVIS_DEX_PROFILE_INTERVAL_SECONDS", "9999")
    monkeypatch.setenv("JARVIS_DEX_RECONCILE_INTERVAL_SECONDS", "9999")
    app = create_app()
    with TestClient(app) as client:
        body = client.get("/").json()
        assert body["step"] == 3
        assert body["research_only"] is True
        assert client.get("/health").status_code == 200
        status = client.get("/api/status").json()
        assert status["architecture"] == "clean-step3"
        assert status["execution_enabled"] is False
