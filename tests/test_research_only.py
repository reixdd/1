from __future__ import annotations

from pathlib import Path


def test_clean_tree_does_not_import_legacy_backend():
    root = Path(__file__).resolve().parents[1] / "src" / "jarvis"
    text = "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*.py"))
    assert "import backend" not in text
    assert "from backend" not in text
    assert "gmgn-demos" not in text


def test_no_transaction_execution_functions_exist():
    root = Path(__file__).resolve().parents[1] / "src" / "jarvis"
    forbidden_defs = ("def buy(", "def sell(", "def swap(", "def sign_transaction(", "def transfer(")
    text = "\n".join(p.read_text(encoding="utf-8").lower() for p in root.rglob("*.py"))
    for marker in forbidden_defs:
        assert marker not in text
