from pathlib import Path

from jarvis.metrics import Metrics
from jarvis.research_ledger import ResearchLedger
from jarvis.online import OnlineLearner


def test_online_dependency_failure_is_explicit_and_nonfatal(tmp_path: Path):
    ledger = ResearchLedger(tmp_path / "op.sqlite3", Metrics())
    learner = OnlineLearner(ledger, Metrics())
    status = learner.status()
    assert "available" in status
    if not status["available"]:
        assert status["dependency_error"]


def test_stage2_source_still_has_no_legacy_runtime_imports():
    root = Path(__file__).resolve().parents[1] / "src" / "jarvis"
    text = "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*.py"))
    assert "from backend" not in text
    assert "import backend" not in text
    assert "gmgn-demos" not in text
