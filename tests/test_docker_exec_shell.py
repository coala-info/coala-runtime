"""Docker/Podman exec runs a string command through a shell, like Singularity and xcrunner.

docker-py splits a string ``cmd`` on whitespace and execs the first word. The install
command ``(uv pip install ... || (echo ... >&2; python -m pip install ...))`` then failed
with exit 127: ``exec: "(uv": executable file not found in $PATH``.
"""

from unittest.mock import MagicMock

import pytest

from coala_runtime.runtime.container_manager import ContainerManager
from coala_runtime.tools.python_executor import PythonExecutor


def _mock_container() -> MagicMock:
    container = MagicMock()
    container.status = "running"
    container.id = "abc123def456"
    exec_result = MagicMock()
    exec_result.exit_code = 0
    exec_result.output = b"ok"
    container.exec_run.return_value = exec_result
    return container


@pytest.mark.asyncio
async def test_string_command_reaches_exec_as_shell_invocation(monkeypatch):
    monkeypatch.setenv("COALA_CONTAINER_USER", "")
    mgr = ContainerManager(docker_client=MagicMock())
    install_cmd = PythonExecutor(container_manager=mgr).get_install_command(["statsmodels"])
    assert install_cmd.startswith("(uv ")  # the compound form that broke 0.1.10
    container = _mock_container()

    await mgr.exec_command(container, install_cmd)

    assert container.exec_run.call_args.kwargs["cmd"] == ["/bin/sh", "-c", install_cmd]


@pytest.mark.asyncio
async def test_argv_command_is_passed_unchanged(monkeypatch):
    monkeypatch.setenv("COALA_CONTAINER_USER", "")
    mgr = ContainerManager(docker_client=MagicMock())
    container = _mock_container()

    await mgr.exec_command(container, ["mkdir", "-p", "/workspace/a b"])

    assert container.exec_run.call_args.kwargs["cmd"] == ["mkdir", "-p", "/workspace/a b"]


_REAL_IMAGE = "python:3.12-slim"


def _docker_client_with_image():
    """A Docker client when the daemon answers and the test image is local; else skip.

    The image is never pulled, so the test stays offline and fast.
    """
    docker = pytest.importorskip("docker")
    try:
        client = docker.from_env()
        client.ping()
        client.images.get(_REAL_IMAGE)
    except Exception as e:  # noqa: BLE001 — any failure means "no usable Docker here"
        pytest.skip(f"Docker or local image {_REAL_IMAGE} unavailable: {e}")
    return client


@pytest.mark.asyncio
async def test_uv_to_pip_fallback_runs_in_real_container(monkeypatch):
    """The real install command runs in a container that has no ``uv``.

    uv is missing, so the shell runs the pip fallback. ``pip`` is already installed in the
    image, so pip reports it satisfied without network access and exits 0.
    """
    client = _docker_client_with_image()
    monkeypatch.setenv("COALA_CONTAINER_USER", "")
    mgr = ContainerManager(docker_client=client)
    install_cmd = PythonExecutor(container_manager=mgr).get_install_command(["pip"])
    assert install_cmd.startswith("(uv ")

    container = client.containers.run(_REAL_IMAGE, ["sleep", "120"], detach=True, remove=True)
    try:
        code, out, _ = await mgr.exec_command(container, install_cmd)
    finally:
        container.kill()

    text = out.decode("utf-8", errors="replace")
    assert code == 0, text
    assert "uv pip install failed, retrying with pip" in text
    assert "Requirement already satisfied: pip" in text
