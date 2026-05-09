"""CLI argv parsing for coala-runtime."""

import pytest

from coala_runtime.__main__ import parse_coala_runtime_argv


def test_parse_only_prog():
    build, engine, rest = parse_coala_runtime_argv(["coala-runtime"])
    assert build is False
    assert engine is None
    assert rest == ["coala-runtime"]


def test_parse_build():
    build, engine, rest = parse_coala_runtime_argv(["coala-runtime", "--build"])
    assert build is True
    assert engine is None
    assert rest == ["coala-runtime"]


@pytest.mark.parametrize(
    "name",
    ["docker", "podman", "singularity", "apptainer"],
)
def test_parse_engine(name):
    build, engine, rest = parse_coala_runtime_argv(["coala-runtime", "--engine", name])
    assert build is False
    assert engine == name
    assert rest == ["coala-runtime"]


def test_parse_build_and_engine():
    build, engine, rest = parse_coala_runtime_argv(
        ["coala-runtime", "--build", "--engine", "podman"]
    )
    assert build is True
    assert engine == "podman"
    assert rest == ["coala-runtime"]


def test_parse_strips_flags_preserves_unknown():
    build, engine, rest = parse_coala_runtime_argv(
        ["coala-runtime", "--engine", "docker", "extra"]
    )
    assert engine == "docker"
    assert rest == ["coala-runtime", "extra"]
