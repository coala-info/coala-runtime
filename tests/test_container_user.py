"""Host uid:gid for Docker/Podman so bind-mount files are not root-owned."""

import os
from unittest.mock import MagicMock

import pytest

from coala_runtime.runtime.container_manager import ContainerManager
from coala_runtime.runtime.engine import host_container_user


def test_host_container_user_defaults_to_process_ids(monkeypatch):
    monkeypatch.delenv("COALA_CONTAINER_USER", raising=False)
    monkeypatch.setattr(os, "getuid", lambda: 1001, raising=False)
    monkeypatch.setattr(os, "getgid", lambda: 27, raising=False)
    assert host_container_user() == "1001:27"


def test_host_container_user_override(monkeypatch):
    monkeypatch.setenv("COALA_CONTAINER_USER", "0:0")
    assert host_container_user() == "0:0"


def test_host_container_user_empty_keeps_image_user(monkeypatch):
    monkeypatch.setenv("COALA_CONTAINER_USER", "  ")
    assert host_container_user() is None


def _clear_proxy_env(monkeypatch) -> None:
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "FTP_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "ftp_proxy",
        "NO_PROXY",
        "no_proxy",
        "COALA_KEEP_PROXY",
    ):
        monkeypatch.delenv(key, raising=False)


def test_container_manager_passes_user_on_create(monkeypatch):
    monkeypatch.setenv("COALA_CONTAINER_USER", "1001:27")
    _clear_proxy_env(monkeypatch)
    client = MagicMock()
    created = MagicMock()
    created.id = "abc123def456"
    client.containers.create.return_value = created
    client.images.get.return_value = MagicMock()
    mgr = ContainerManager(docker_client=client)
    assert mgr.system_site_packages_writable is False

    import asyncio

    asyncio.run(mgr.create_container("coala-runtime-python:latest", command=["true"]))
    kwargs = client.containers.create.call_args.kwargs
    assert kwargs["user"] == "1001:27"
    assert kwargs["environment"]["NO_PROXY"] == "*"
    assert kwargs["environment"]["HTTP_PROXY"] == ""


def test_container_manager_root_user_keeps_system_site(monkeypatch):
    monkeypatch.setenv("COALA_CONTAINER_USER", "0:0")
    mgr = ContainerManager(docker_client=MagicMock())
    assert mgr.system_site_packages_writable is True


@pytest.mark.asyncio
async def test_exec_run_passes_user(monkeypatch):
    monkeypatch.setenv("COALA_CONTAINER_USER", "1001:27")
    _clear_proxy_env(monkeypatch)
    client = MagicMock()
    mgr = ContainerManager(docker_client=client)
    container = MagicMock()
    container.status = "running"
    container.id = "abc123def456"
    exec_result = MagicMock()
    exec_result.exit_code = 0
    exec_result.output = b"ok"
    container.exec_run.return_value = exec_result
    code, out, err = await mgr.exec_command(container, ["echo", "ok"])
    assert code == 0
    assert out == b"ok"
    assert container.exec_run.call_args.kwargs["user"] == "1001:27"
    assert container.exec_run.call_args.kwargs["environment"]["NO_PROXY"] == "*"
