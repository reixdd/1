from __future__ import annotations

from pathlib import Path


def test_clean_stage3_does_not_import_legacy_backend():
    root = Path(__file__).resolve().parents[1] / "src" / "jarvis"
    text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in root.rglob("*.py"))
    assert "from backend" not in text
    assert "import backend" not in text
    assert "gmgn-demos" not in text
