import os

import pytest

from coala_runtime.runtime.engine import ContainerEngine, get_engine_from_env, make_container_manager


def test_xrunner_engine_value():
    assert ContainerEngine("xrunner") is ContainerEngine.XRUNNER


def test_env_selects_xrunner(monkeypatch):
    monkeypatch.setenv("COALA_CONTAINER_ENGINE", "xrunner")
    assert get_engine_from_env() is ContainerEngine.XRUNNER


def test_make_manager_returns_adapter(monkeypatch, tmp_path):
    pytest.importorskip("xcodon_runtime")
    monkeypatch.setenv("COALA_CONTAINER_ENGINE", "xrunner")
    monkeypatch.setenv("XCODON_RUNTIME_HOME", str(tmp_path))
    mgr = make_container_manager()
    assert type(mgr).__name__ == "XcodonContainerManager"
    assert mgr.system_site_packages_writable is True
