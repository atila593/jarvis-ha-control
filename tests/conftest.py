import os

import pytest

os.environ.setdefault("OPTIONS_PATH", "/nonexistent.json")


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    """Chaque test a sa propre base SQLite et se comporte comme s'il passait par Ingress."""
    monkeypatch.setenv("JARVIS_DB", str(tmp_path / "jarvis.db"))
    monkeypatch.setenv("JARVIS_DEV", "1")
