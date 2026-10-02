from __future__ import annotations

from jarvis.sense.dexscreener import DexScreenerProvider


def test_profile_links_are_preserved_as_provenance_source_code():
    import inspect
    source = inspect.getsource(DexScreenerProvider.profiles)
    assert "profile_links" in source
    assert "launch_recency_proven" in source
