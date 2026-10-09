"""GPU passthrough: COALA_GPU env default, per-call flag, and backend wiring."""

import asyncio
from unittest.mock import MagicMock

import pytest
from docker.types import DeviceRequest

from coala_runtime.runtime.container_manager import ContainerManager
from coala_runtime.runtime.engine import gpu_requested_from_env
from coala_runtime.runtime.singularity_container_manager import SingularityContainerManager
from coala_runtime.tools.python_executor import PythonExecutor

# --- COALA_GPU env var -------------------------------------------------------


def test_gpu_env_unset_is_off(monkeypatch):
    monkeypatch.delenv("COALA_GPU", raising=False)
    assert gpu_requested_from_env() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", " on "])
def test_gpu_env_truthy_values(monkeypatch, value):
    monkeypatch.setenv("COALA_GPU", value)
    assert gpu_requested_from_env() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
def test_gpu_env_falsy_values(monkeypatch, value):
    monkeypatch.setenv("COALA_GPU", value)
    assert gpu_requested_from_env() is False


# --- Docker / Podman ----------------------------------------------------------


def _docker_manager():
    client = MagicMock()
    created = MagicMock()
    created.id = "abc123def456"
    client.containers.create.return_value = created
    client.images.get.return_value = MagicMock()
    return client, ContainerManager(docker_client=client)


def test_docker_create_container_requests_all_gpus():
    client, mgr = _docker_manager()
    asyncio.run(mgr.create_container("coala-runtime-python:latest", command=["true"], gpu=True))
    reqs = client.containers.create.call_args.kwargs["device_requests"]
    assert len(reqs) == 1
    req = reqs[0]
    assert isinstance(req, DeviceRequest)
    assert req["Count"] == -1
    assert ["gpu"] in req["Capabilities"]


def test_docker_create_container_without_gpu_has_no_device_requests():
    client, mgr = _docker_manager()
    asyncio.run(mgr.create_container("coala-runtime-python:latest", command=["true"]))
    assert "device_requests" not in client.containers.create.call_args.kwargs


# --- Singularity / Apptainer --------------------------------------------------


def _singularity_manager(monkeypatch):
    monkeypatch.setattr(
        "coala_runtime.runtime.singularity_container_manager.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        r = MagicMock()
        r.returncode = 0
        r.stdout = ""
        r.stderr = ""
        return r

    monkeypatch.setattr(
        "coala_runtime.runtime.singularity_container_manager.subprocess.run", fake_run
    )
    return SingularityContainerManager(cli_binary="apptainer"), calls


def test_singularity_instance_start_adds_nv_flag(monkeypatch):
    mgr, calls = _singularity_manager(monkeypatch)
    asyncio.run(mgr.create_container("coala-runtime-python:latest", gpu=True))
    start = calls[0]
    assert start[1:3] == ["instance", "start"]
    assert "--nv" in start
    # --nv must come before the image URI
    assert start.index("--nv") < start.index("docker://hubentu/coala-runtime-python:latest")


def test_singularity_instance_start_without_gpu_has_no_nv(monkeypatch):
    mgr, calls = _singularity_manager(monkeypatch)
    asyncio.run(mgr.create_container("coala-runtime-python:latest"))
    assert "--nv" not in calls[0]


# --- Executor pass-through ----------------------------------------------------


class _RecordingManager:
    """Records create_container kwargs then aborts the run."""

    system_site_packages_writable = True

    def __init__(self):
        self.create_kwargs = None

    async def create_container(
        self,
        image,
        command=None,
        volumes=None,
        working_dir="/workspace",
        environment=None,
        name=None,
        gpu=False,
    ):
        self.create_kwargs = {"image": image, "gpu": gpu}
        raise RuntimeError("stop after create")

    async def cleanup_all(self):
        pass


class _NoGpuManager:
    """Backend whose create_container has no ``gpu`` parameter (e.g. xcrunner)."""

    system_site_packages_writable = True

    def __init__(self):
        self.called = False

    async def create_container(
        self,
        image,
        command=None,
        volumes=None,
        working_dir="/workspace",
        environment=None,
        name=None,
    ):
        self.called = True
        raise RuntimeError("stop after create")

    async def cleanup_all(self):
        pass


@pytest.mark.asyncio
async def test_executor_forwards_gpu_to_backend(tmp_path):
    mgr = _RecordingManager()
    ex = PythonExecutor(container_manager=mgr, output_dir=str(tmp_path))
    await ex.execute(script="print(1)", gpu=True)
    assert mgr.create_kwargs["gpu"] is True


@pytest.mark.asyncio
async def test_executor_gpu_defaults_to_off(tmp_path, monkeypatch):
    monkeypatch.delenv("COALA_GPU", raising=False)
    mgr = _RecordingManager()
    ex = PythonExecutor(container_manager=mgr, output_dir=str(tmp_path))
    await ex.execute(script="print(1)")
    assert mgr.create_kwargs["gpu"] is False


@pytest.mark.asyncio
async def test_executor_gpu_env_sets_default(tmp_path, monkeypatch):
    monkeypatch.setenv("COALA_GPU", "1")
    mgr = _RecordingManager()
    ex = PythonExecutor(container_manager=mgr, output_dir=str(tmp_path))
    await ex.execute(script="print(1)")
    assert mgr.create_kwargs["gpu"] is True


@pytest.mark.asyncio
async def test_executor_gpu_false_overrides_env(tmp_path, monkeypatch):
    monkeypatch.setenv("COALA_GPU", "1")
    mgr = _RecordingManager()
    ex = PythonExecutor(container_manager=mgr, output_dir=str(tmp_path))
    await ex.execute(script="print(1)", gpu=False)
    assert mgr.create_kwargs["gpu"] is False


@pytest.mark.asyncio
async def test_executor_gpu_on_unsupported_backend_fails_clearly(tmp_path):
    mgr = _NoGpuManager()
    ex = PythonExecutor(container_manager=mgr, output_dir=str(tmp_path))
    result = await ex.execute(script="print(1)", gpu=True)
    assert result.success is False
    assert "gpu" in result.stderr.lower()
    assert mgr.called is False


@pytest.mark.asyncio
async def test_executor_no_gpu_on_unsupported_backend_still_runs(tmp_path, monkeypatch):
    monkeypatch.delenv("COALA_GPU", raising=False)
    mgr = _NoGpuManager()
    ex = PythonExecutor(container_manager=mgr, output_dir=str(tmp_path))
    await ex.execute(script="print(1)")
    assert mgr.called is True


# --- Server input models ------------------------------------------------------


def test_server_inputs_accept_gpu_flag():
    from coala_runtime.server import PythonExecutorInput, RExecutorInput

    assert PythonExecutorInput(script="print(1)").gpu is None
    assert PythonExecutorInput(script="print(1)", gpu=True).gpu is True
    assert RExecutorInput(script="cat(1)").gpu is None
    assert RExecutorInput(script="cat(1)", gpu=True).gpu is True
