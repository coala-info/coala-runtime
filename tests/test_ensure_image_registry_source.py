"""An executor tag is a local name; fetching it on demand must use its published source.

``coala-runtime-python:latest`` is produced by ``docker/build.sh`` and retagged onto by
``coala-runtime pull``. No registry serves it, so an on-demand pull resolved it to
``docker.io/library/coala-runtime-python`` and 404s on a host where neither command ran:
"not found on Docker Hub, or it needs a login". ``singularity_image_uri`` always consulted
``REGISTRY_PULL_IMAGES``; this path did not.
"""

import asyncio
from unittest.mock import MagicMock

from docker.errors import ImageNotFound

from coala_runtime.runtime.container_manager import ContainerManager
from coala_runtime.runtime.docker_images import REGISTRY_PULL_IMAGES, registry_source_for


def _manager_missing_image():
    client = MagicMock()
    client.images.get.side_effect = ImageNotFound("missing")
    return ContainerManager(docker_client=client), client


def test_registry_source_maps_only_executor_tags():
    assert registry_source_for("coala-runtime-python") == REGISTRY_PULL_IMAGES[
        "coala-runtime-python:latest"]
    assert registry_source_for("coala-runtime-r:latest") == REGISTRY_PULL_IMAGES[
        "coala-runtime-r:latest"]
    # Already qualified, third-party, and empty references are left alone.
    assert registry_source_for("hubentu/coala-runtime-python:latest") is None
    assert registry_source_for("quay.io/biocontainers/samtools:1.19") is None
    assert registry_source_for("python:3.12-slim") is None
    assert registry_source_for("") is None


def test_a_missing_executor_tag_pulls_its_source_and_retags():
    manager, client = _manager_missing_image()
    asyncio.run(manager.ensure_image("coala-runtime-python:latest"))
    client.images.pull.assert_called_once_with("hubentu/coala-runtime-python:latest")
    client.api.tag.assert_called_once_with(
        "hubentu/coala-runtime-python:latest", "coala-runtime-python", tag="latest")


def test_a_missing_third_party_image_is_pulled_verbatim():
    manager, client = _manager_missing_image()
    asyncio.run(manager.ensure_image("quay.io/biocontainers/samtools:1.19"))
    client.images.pull.assert_called_once_with("quay.io/biocontainers/samtools:1.19")
    client.api.tag.assert_not_called()


def test_an_image_already_present_is_not_fetched():
    client = MagicMock()
    manager = ContainerManager(docker_client=client)
    asyncio.run(manager.ensure_image("coala-runtime-python:latest"))
    client.images.pull.assert_not_called()
    client.api.tag.assert_not_called()
