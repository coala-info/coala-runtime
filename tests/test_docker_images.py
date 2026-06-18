"""Tests for ensure_images build-vs-pull behavior."""

from unittest.mock import MagicMock, patch

from coala_runtime.runtime.docker_images import EXECUTOR_IMAGES, REGISTRY_PULL_IMAGES, ensure_images
from coala_runtime.runtime.engine import ContainerEngine


def _docker_patches(client):
    return (
        patch(
            "coala_runtime.runtime.docker_images.get_engine_from_env",
            return_value=ContainerEngine.DOCKER,
        ),
        patch(
            "coala_runtime.runtime.docker_images.docker_client_for_engine",
            return_value=client,
        ),
    )


def test_default_builds_when_images_missing():
    from docker.errors import ImageNotFound

    client = MagicMock()
    client.images.get.side_effect = ImageNotFound("missing")

    p_engine, p_client = _docker_patches(client)
    with p_engine, p_client, patch(
        "coala_runtime.runtime.docker_images.build_executor_images"
    ) as mock_build:
        ensure_images()
        mock_build.assert_called_once()


def test_default_skips_build_when_images_present():
    client = MagicMock()

    p_engine, p_client = _docker_patches(client)
    with p_engine, p_client, patch(
        "coala_runtime.runtime.docker_images.build_executor_images"
    ) as mock_build:
        ensure_images()
        mock_build.assert_not_called()


def test_pull_fetches_missing_images():
    from docker.errors import ImageNotFound

    client = MagicMock()

    def get_side_effect(tag):
        if tag == EXECUTOR_IMAGES[0]:
            raise ImageNotFound("missing")
        return MagicMock()

    client.images.get.side_effect = get_side_effect

    p_engine, p_client = _docker_patches(client)
    with p_engine, p_client, patch(
        "coala_runtime.runtime.docker_images.build_executor_images"
    ) as mock_build:
        ensure_images(pull=True)
        mock_build.assert_not_called()
        registry_tag = REGISTRY_PULL_IMAGES[EXECUTOR_IMAGES[0]]
        client.images.pull.assert_called_once_with(registry_tag)
        client.api.tag.assert_called_once_with(
            registry_tag, "coala-runtime-python", tag="latest"
        )


def test_force_build_always_builds():
    client = MagicMock()

    p_engine, p_client = _docker_patches(client)
    with p_engine, p_client, patch(
        "coala_runtime.runtime.docker_images.build_executor_images"
    ) as mock_build:
        ensure_images(force_build=True)
        mock_build.assert_called_once()


def test_pull_with_force_build_still_builds():
    """--build takes precedence over --pull for acquisition."""
    client = MagicMock()

    p_engine, p_client = _docker_patches(client)
    with p_engine, p_client, patch(
        "coala_runtime.runtime.docker_images.build_executor_images"
    ) as mock_build:
        ensure_images(pull=True, force_build=True)
        mock_build.assert_called_once()
        client.images.pull.assert_not_called()
