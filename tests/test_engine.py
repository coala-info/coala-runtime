"""Tests for container engine helpers."""

import logging

import pytest

from coala_runtime.runtime.engine import (
    ContainerEngine,
    get_engine_from_env,
    singularity_image_uri,
)


def test_singularity_image_uri_adds_docker_scheme():
    assert singularity_image_uri("ubuntu:22.04") == "docker://ubuntu:22.04"
    assert singularity_image_uri("hubentu/coala-runtime-python:latest") == (
        "docker://hubentu/coala-runtime-python:latest"
    )


def test_singularity_image_uri_preserves_explicit_scheme():
    assert singularity_image_uri("docker://quay.io/foo/bar:1") == "docker://quay.io/foo/bar:1"
    assert singularity_image_uri("oras://example.invalid/img:latest") == "oras://example.invalid/img:latest"


def test_singularity_image_uri_empty():
    with pytest.raises(ValueError):
        singularity_image_uri("")


def test_get_engine_from_env_default(monkeypatch):
    monkeypatch.delenv("COALA_CONTAINER_ENGINE", raising=False)
    assert get_engine_from_env() == ContainerEngine.DOCKER


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("podman", ContainerEngine.PODMAN),
        ("DOCKER", ContainerEngine.DOCKER),
        ("Singularity", ContainerEngine.SINGULARITY),
        ("apptainer", ContainerEngine.APPTAINER),
    ],
)
def test_get_engine_from_env_values(monkeypatch, raw, expected):
    monkeypatch.setenv("COALA_CONTAINER_ENGINE", raw)
    assert get_engine_from_env() == expected


def test_get_engine_from_env_unknown_warns(monkeypatch, caplog):
    monkeypatch.setenv("COALA_CONTAINER_ENGINE", "rocketship")
    caplog.set_level(logging.WARNING)
    assert get_engine_from_env() == ContainerEngine.DOCKER
    assert any("Unknown COALA_CONTAINER_ENGINE" in r.message for r in caplog.records)
