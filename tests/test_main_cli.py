"""CLI argv parsing for coala-runtime."""

import pytest

from coala_runtime.__main__ import parse_coala_runtime_argv


def test_parse_only_prog():
    force_build, pull, engine, rest = parse_coala_runtime_argv(["coala-runtime"])
    assert force_build is False
    assert pull is False
    assert engine is None
    assert rest == ["coala-runtime"]


def test_parse_build():
    force_build, pull, engine, rest = parse_coala_runtime_argv(["coala-runtime", "--build"])
    assert force_build is True
    assert pull is False
    assert engine is None
    assert rest == ["coala-runtime"]


def test_parse_pull():
    force_build, pull, engine, rest = parse_coala_runtime_argv(["coala-runtime", "--pull"])
    assert force_build is False
    assert pull is True
    assert rest == ["coala-runtime"]


@pytest.mark.parametrize(
    "name",
    ["docker", "podman", "singularity", "apptainer"],
)
def test_parse_engine(name):
    force_build, pull, engine, rest = parse_coala_runtime_argv(["coala-runtime", "--engine", name])
    assert force_build is False
    assert pull is False
    assert engine == name
    assert rest == ["coala-runtime"]


def test_parse_build_and_pull():
    force_build, pull, engine, rest = parse_coala_runtime_argv(
        ["coala-runtime", "--build", "--pull"]
    )
    assert force_build is True
    assert pull is True
    assert rest == ["coala-runtime"]


def test_parse_build_and_engine():
    force_build, pull, engine, rest = parse_coala_runtime_argv(
        ["coala-runtime", "--build", "--engine", "podman"]
    )
    assert force_build is True
    assert pull is False
    assert engine == "podman"
    assert rest == ["coala-runtime"]


def test_parse_strips_flags_preserves_unknown():
    force_build, pull, engine, rest = parse_coala_runtime_argv(
        ["coala-runtime", "--engine", "docker", "extra"]
    )
    assert engine == "docker"
    assert rest == ["coala-runtime", "extra"]
