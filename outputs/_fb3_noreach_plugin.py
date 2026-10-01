"""Part 2 red check: the reachability filter patched out (the accessor always False)."""
import pytest
import agents


@pytest.fixture(autouse=True)
def _fb3_no_reachability(monkeypatch):
    monkeypatch.setattr(agents, "searcher_targeting_reachability", lambda: False)
