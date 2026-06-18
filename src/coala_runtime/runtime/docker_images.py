"""Ensure required Docker images exist; build locally or pull from registry."""

import logging
import subprocess
from pathlib import Path

from docker.errors import DockerException, ImageNotFound

from coala_runtime.runtime.engine import (
    ContainerEngine,
    docker_client_for_engine,
    get_engine_from_env,
)

logger = logging.getLogger(__name__)

# Local tags used by executors and produced by ``docker/build.sh``.
EXECUTOR_IMAGES = [
    "coala-runtime-python:latest",
    "coala-runtime-r:latest",
]

# Docker Hub sources for ``coala-runtime --pull`` (retagged to EXECUTOR_IMAGES locally).
REGISTRY_PULL_IMAGES = {
    "coala-runtime-python:latest": "hubentu/coala-runtime-python:latest",
    "coala-runtime-r:latest": "hubentu/coala-runtime-r:latest",
}

# Backwards-compatible alias
PULL_IMAGES = list(REGISTRY_PULL_IMAGES.values())


def _project_root() -> Path | None:
    """Return project root (directory containing docker/ and Dockerfiles), or None."""
    # Prefer cwd so "uv run --directory /path/to/coala-runtime" or running from
    # project dir works when the package is installed (e.g. conda).
    cwd = Path.cwd()
    if cwd.joinpath("docker", "Dockerfile.python").exists():
        return cwd
    # Walk up from this file (works when running from source tree).
    path = Path(__file__).resolve().parent
    for _ in range(5):
        if path.joinpath("docker", "Dockerfile.python").exists():
            return path
        parent = path.parent
        if parent == path:
            break
        path = parent
    return None


def _image_exists(client, image_tag: str) -> bool:
    """Return True if the image exists locally."""
    try:
        client.images.get(image_tag)
        return True
    except ImageNotFound:
        return False


def _executor_images_present(client) -> bool:
    return all(_image_exists(client, tag) for tag in EXECUTOR_IMAGES)


def _pull_image(client, local_tag: str) -> None:
    """Pull from Docker Hub and tag locally (drops ``hubentu/`` namespace)."""
    registry_tag = REGISTRY_PULL_IMAGES.get(local_tag, local_tag)
    logger.info("Pulling %s from %s...", local_tag, registry_tag)
    client.images.pull(registry_tag)
    if registry_tag != local_tag:
        repo, tag = local_tag.rsplit(":", 1) if ":" in local_tag else (local_tag, "latest")
        client.api.tag(registry_tag, repo, tag=tag)
        logger.info("Tagged %s as %s", registry_tag, local_tag)
    else:
        logger.info("Pulled %s", local_tag)


def _run_build_script(project_root: Path) -> None:
    """Run docker/build.sh to build both images locally."""
    script = project_root / "docker" / "build.sh"
    if not script.exists():
        raise FileNotFoundError(f"Build script not found: {script}")
    logger.info("Running %s...", script)
    subprocess.run(
        ["bash", str(script)],
        cwd=str(project_root),
        check=True,
    )


def build_executor_images() -> None:
    """Build executor images via ``docker/build.sh``.

    Requires the coala-runtime repo (``docker/Dockerfile.python``) and Docker/Podman CLI.
    Honors ``COALA_DOCKER_*`` env vars documented in ``docker/README.md``.
    """
    project_root = _project_root()
    if project_root is None:
        raise FileNotFoundError(
            "Could not find coala-runtime project root (missing docker/Dockerfile.python). "
            "Run from the repository directory or use an MCP client cwd that points at the clone."
        )
    _run_build_script(project_root)


def ensure_images(*, pull: bool = False, force_build: bool = False) -> None:
    """Ensure executor images exist before starting the MCP server.

    Default (Docker/Podman): build locally via ``docker/build.sh`` when either image is
    missing. Use ``pull=True`` (``coala-runtime --pull``) to fetch from Docker Hub instead.
    Use ``force_build=True`` (``coala-runtime --build``) to rebuild even when images exist.

    Singularity/Apptainer: images resolve on first execution; this function is a no-op.
    """
    engine = get_engine_from_env()
    if engine in (ContainerEngine.SINGULARITY, ContainerEngine.APPTAINER):
        if force_build or pull:
            logger.warning(
                "COALA_CONTAINER_ENGINE=%s: --build/--pull apply to Docker/Podman only; "
                "use registry images or build SIFs separately.",
                engine.value,
            )
        else:
            logger.debug(
                "Engine %s: executor images %s resolve on first execution.",
                engine.value,
                EXECUTOR_IMAGES,
            )
        return

    try:
        client = docker_client_for_engine(engine)
    except (DockerException, RuntimeError, OSError) as e:
        logger.warning(
            "Could not connect to container API (%s); skipping image check/build: %s",
            engine.value,
            e,
        )
        return

    if pull and not force_build:
        for image in EXECUTOR_IMAGES:
            if _image_exists(client, image):
                logger.debug("Container image %s already present", image)
                continue
            try:
                _pull_image(client, image)
            except DockerException as e:
                logger.error("Failed to pull %s: %s", image, e)
                raise
        return

    if force_build or not _executor_images_present(client):
        if force_build:
            logger.info("Building executor images (--build)")
        else:
            logger.info(
                "Executor image(s) missing locally; building via docker/build.sh "
                "(use --pull to fetch pre-built images from Docker Hub instead)"
            )
        try:
            build_executor_images()
        except FileNotFoundError as e:
            logger.warning("%s", e)
            if not _executor_images_present(client):
                logger.warning(
                    "Executor images still missing (%s); script execution may fail.",
                    ", ".join(EXECUTOR_IMAGES),
                )
        except subprocess.CalledProcessError as e:
            logger.error("Executor image build failed (exit %s)", e.returncode)
            raise
