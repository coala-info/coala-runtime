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
    assert singularity_image_uri("coala-runtime-python:latest") == (
        "docker://hubentu/coala-runtime-python:latest"
    )


def test_singularity_image_uri_preserves_explicit_scheme():
    assert singularity_image_uri("docker://quay.io/foo/bar:1") == "docker://quay.io/foo/bar:1"
    assert singularity_image_uri("oras://example.invalid/img:latest") == "oras://example.invalid/img:latest"


def test_singularity_image_uri_local_absolute_path_not_prefixed():
    assert singularity_image_uri("/scratch/coala-python.sif") == "/scratch/coala-python.sif"


def test_singularity_image_uri_relative_path_not_prefixed():
    assert singularity_image_uri("./images/coala-python.sif") == "./images/coala-python.sif"
    assert singularity_image_uri("../share/coala-python.sif") == "../share/coala-python.sif"


def test_singularity_image_uri_empty():
    with pytest.raises(ValueError):
        singularity_image_uri("")


def test_get_engine_from_env_unset_autodetects_apptainer_when_no_docker(monkeypatch):
    monkeypatch.delenv("COALA_CONTAINER_ENGINE", raising=False)

    def fake_which(name: str) -> str | None:
        if name == "apptainer":
            return "/usr/bin/apptainer"
        return None

    monkeypatch.setattr("coala_runtime.runtime.engine.shutil.which", fake_which)
    assert get_engine_from_env() == ContainerEngine.APPTAINER


def test_get_engine_from_env_unset_autodetects_docker_when_daemon_up(monkeypatch):
    monkeypatch.delenv("COALA_CONTAINER_ENGINE", raising=False)

    monkeypatch.setattr(
        "coala_runtime.runtime.engine.shutil.which",
        lambda name: "/bin/docker" if name == "docker" else None,
    )

    class _Ping:
        def ping(self) -> bool:
            return True

    import docker as docker_pkg

    monkeypatch.setattr(docker_pkg, "from_env", lambda: _Ping())
    assert get_engine_from_env() == ContainerEngine.DOCKER


def test_get_engine_from_env_unset_autodetects_singularity_if_no_apptainer(monkeypatch):
    monkeypatch.delenv("COALA_CONTAINER_ENGINE", raising=False)

    def fake_which(name: str) -> str | None:
        if name == "singularity":
            return "/usr/bin/singularity"
        return None

    monkeypatch.setattr("coala_runtime.runtime.engine.shutil.which", fake_which)
    assert get_engine_from_env() == ContainerEngine.SINGULARITY


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
