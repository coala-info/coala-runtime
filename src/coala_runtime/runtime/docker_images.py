"""Ensure required Docker images exist; pull from registry or build locally."""

import logging
import subprocess
from pathlib import Path

import docker
from docker.errors import DockerException, ImageNotFound

logger = logging.getLogger(__name__)

# Default images used by executors; pulled if missing
PULL_IMAGES = [
    "hubentu/coala-runtime-python:latest",
    "hubentu/coala-runtime-r:latest",
]


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


def _pull_image(client, image: str) -> None:
    """Pull image from registry."""
    logger.info("Pulling %s...", image)
    client.images.pull(image)
    logger.info("Pulled %s", image)


def _build_image(client, project_root: Path, dockerfile_rel: str, tag: str) -> None:
    """Build a single image. dockerfile_rel is relative to project_root."""
    logger.info("Building Docker image %s from %s...", tag, dockerfile_rel)
    build_path = str(project_root)
    try:
        image, gen = client.images.build(
            path=build_path,
            dockerfile=dockerfile_rel,
            tag=tag,
        )
        for chunk in gen:
            if "stream" in chunk:
                logger.debug(chunk["stream"].rstrip())
    except ImageNotFound:
        # docker-py may raise after build when resolving image by ID; image can
        # still be present by tag (e.g. with buildx or some Docker versions).
        try:
            client.images.get(tag)
        except ImageNotFound:
            raise
    logger.info("Built image %s", tag)


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


def ensure_images(*, build: bool = False) -> None:
    """Ensure required executor images exist.

    By default, pulls hubentu/coala-runtime-python:latest and hubentu/coala-runtime-r:latest
    from Docker Hub if not present. With build=True, runs docker/build.sh to build both
    images locally (tagged as coala-runtime-python:latest and coala-runtime-r:latest).
    """
    try:
        client = docker.from_env()
    except DockerException as e:
        logger.warning(
            "Could not connect to Docker; skipping image check/build: %s", e
        )
        return

    if build:
        project_root = _project_root()
        if project_root is None or not project_root.joinpath("docker", "Dockerfile.python").exists():
            logger.warning(
                "Could not find project root (run from coala-runtime repo or set cwd); skipping Docker image build"
            )
            return
        _run_build_script(project_root)
        return

    for image in PULL_IMAGES:
        if _image_exists(client, image):
            logger.debug("Docker image %s already present", image)
            continue
        try:
            _pull_image(client, image)
        except DockerException as e:
            logger.error("Failed to pull %s: %s", image, e)
            raise
