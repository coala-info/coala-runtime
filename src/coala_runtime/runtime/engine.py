"""Container engine selection (Docker, Podman, Singularity / Apptainer)."""

from __future__ import annotations

import logging
import os
import shutil
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ContainerEngine(str, Enum):
    """Supported container runtimes."""

    DOCKER = "docker"
    PODMAN = "podman"
    SINGULARITY = "singularity"
    APPTAINER = "apptainer"


def singularity_image_uri(image: str) -> str:
    """Normalize an image reference for Singularity/Apptainer (``docker://`` default).

    Absolute paths (e.g. ``/scratch/coala-python.sif``) and relative ``./`` / ``../`` paths are left
    unchanged so pre-pulled SIFs or sandboxes work without Docker Hub auth.
    """
    s = (image or "").strip()
    if not s:
        raise ValueError("container image cannot be empty")
    if "://" in s:
        return s
    if s.startswith("/"):
        return s
    if s.startswith("./") or s.startswith("../"):
        return s
    return f"docker://{s}"


def _autodetect_container_engine() -> ContainerEngine:
    """Choose a runtime when ``COALA_CONTAINER_ENGINE`` is unset.

    Order: Docker daemon if reachable, else Podman socket, else Apptainer, else Singularity,
    else Docker as last resort (may fail later). This matches typical **HPC** clusters where only
    Apptainer/Singularity is installed.
    """
    docker_exe = shutil.which("docker")
    if docker_exe:
        try:
            import docker as docker_mod

            docker_mod.from_env().ping()
            logger.info(
                "COALA_CONTAINER_ENGINE unset; using docker (daemon reachable)."
            )
            return ContainerEngine.DOCKER
        except Exception:
            logger.debug(
                "Docker CLI on PATH but daemon not reachable; trying podman / apptainer / singularity.",
            )

    try:
        import docker as docker_mod

        docker_mod.DockerClient(base_url=podman_socket_url()).ping()
        logger.info("COALA_CONTAINER_ENGINE unset; using podman.")
        return ContainerEngine.PODMAN
    except Exception:
        pass

    if shutil.which("apptainer"):
        logger.info(
            "COALA_CONTAINER_ENGINE unset; using apptainer (no usable Docker/Podman on this host)."
        )
        return ContainerEngine.APPTAINER
    if shutil.which("singularity"):
        logger.info(
            "COALA_CONTAINER_ENGINE unset; using singularity (no usable Docker/Podman on this host)."
        )
        return ContainerEngine.SINGULARITY

    if docker_exe:
        logger.warning(
            "COALA_CONTAINER_ENGINE unset; Docker CLI present but daemon unreachable and "
            "no apptainer/singularity on PATH; defaulting to docker (operations may fail)."
        )
        return ContainerEngine.DOCKER

    logger.warning(
        "COALA_CONTAINER_ENGINE unset and no container runtime detected on PATH "
        "(docker, podman socket, apptainer, singularity); defaulting to docker."
    )
    return ContainerEngine.DOCKER


def get_engine_from_env() -> ContainerEngine:
    """Resolve engine from ``COALA_CONTAINER_ENGINE``, or autodetect if unset.

    When the variable is unset or empty, picks Docker (if the daemon responds), else Podman,
    else Apptainer or Singularity if on ``PATH`` — suitable for HPC without Docker.
    """
    raw = (os.environ.get("COALA_CONTAINER_ENGINE") or "").strip().lower()
    if not raw:
        return _autodetect_container_engine()
    aliases = {
        "singularity": ContainerEngine.SINGULARITY,
        "apptainer": ContainerEngine.APPTAINER,
        "podman": ContainerEngine.PODMAN,
        "docker": ContainerEngine.DOCKER,
    }
    if raw not in aliases:
        logger.warning(
            "Unknown COALA_CONTAINER_ENGINE=%r; using docker. "
            "Valid values: docker, podman, singularity, apptainer.",
            raw,
        )
        return ContainerEngine.DOCKER
    return aliases[raw]


def podman_socket_url() -> str:
    """Return a Podman-compatible Docker API socket URL (``unix://...``)."""
    env_host = (os.environ.get("DOCKER_HOST") or "").strip()
    if env_host:
        return env_host
    uid = os.getuid()
    user_sock = Path(f"/run/user/{uid}/podman/podman.sock")
    if user_sock.is_socket():
        return f"unix://{user_sock}"
    root_sock = Path("/run/podman/podman.sock")
    if root_sock.is_socket():
        return f"unix://{root_sock}"
    raise RuntimeError(
        "Podman socket not found. Start Podman (e.g. `podman machine start` on macOS), "
        "or set DOCKER_HOST to your Podman API socket (e.g. unix:///run/user/$UID/podman/podman.sock)."
    )


def docker_client_for_engine(engine: ContainerEngine):
    """Build a docker-py client for Docker or Podman."""
    import docker

    if engine == ContainerEngine.PODMAN:
        return docker.DockerClient(base_url=podman_socket_url())
    return docker.from_env()


def make_container_manager():
    """Construct the container manager for the configured engine."""
    engine = get_engine_from_env()
    if engine in (ContainerEngine.DOCKER, ContainerEngine.PODMAN):
        from coala_runtime.runtime.container_manager import ContainerManager

        return ContainerManager(docker_client=docker_client_for_engine(engine))

    from coala_runtime.runtime.singularity_container_manager import SingularityContainerManager

    cli = "apptainer" if engine == ContainerEngine.APPTAINER else "singularity"
    return SingularityContainerManager(cli_binary=cli)
