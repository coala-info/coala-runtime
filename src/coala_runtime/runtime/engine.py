"""Container engine selection (Docker, Podman, Singularity / Apptainer)."""

from __future__ import annotations

import logging
import os
import shutil
from enum import Enum
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_PROXY_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "FTP_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "ftp_proxy",
)
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


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
    from coala_runtime.runtime.docker_images import REGISTRY_PULL_IMAGES

    ref = REGISTRY_PULL_IMAGES.get(s, s)
    return f"docker://{ref}"


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


def _proxy_host_is_loopback(value: str) -> bool:
    raw = (value or "").strip()
    if not raw:
        return False
    parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    host = (parsed.hostname or "").lower()
    return host in _LOOPBACK_HOSTS or host.startswith("127.")


def container_proxy_env() -> dict[str, str]:
    """Proxy env for the container so pip/CRAN are not stuck on a host loopback proxy.

    ``HTTP_PROXY=http://127.0.0.1:…`` is reachable on the host and by the Docker
    daemon, but not from the container netns (Connection refused). Docker may also
    inject ``~/.docker/config.json`` proxies; blanking overrides that.

    Set ``COALA_KEEP_PROXY=1`` to leave proxy env alone (and pass host proxies into
    Docker, which does not inherit them). A non-loopback host proxy is forwarded.
    Does not read docker config.json — use ``COALA_KEEP_PROXY`` if that is the only
    working path to PyPI.
    """
    if os.environ.get("COALA_KEEP_PROXY", "").strip().lower() in {"1", "true", "yes"}:
        return {k: os.environ[k] for k in _PROXY_KEYS if k in os.environ}
    host_vals = {k: os.environ[k] for k in _PROXY_KEYS if os.environ.get(k, "").strip()}
    if host_vals and not any(_proxy_host_is_loopback(v) for v in host_vals.values()):
        return dict(host_vals)
    out = {k: "" for k in _PROXY_KEYS}
    out["NO_PROXY"] = "*"
    out["no_proxy"] = "*"
    return out


def merge_container_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Merge caller env with ``container_proxy_env()`` (proxy keys win)."""
    merged = dict(environment or {})
    merged.update(container_proxy_env())
    return merged


def host_container_user() -> str | None:
    """``uid:gid`` so bind-mount writes match the host user (not root).

    Set ``COALA_CONTAINER_USER`` to override (``1001:27``), or empty to keep the
    image USER (typically root — needed only for system-wide conda installs).
    """
    if "COALA_CONTAINER_USER" in os.environ:
        raw = os.environ["COALA_CONTAINER_USER"].strip()
        return raw or None
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    if getuid is None or getgid is None:
        return None
    return f"{getuid()}:{getgid()}"


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
