"""Tests for MCP execution error hints."""

from coala_runtime.server import _handle_execution_error


def test_registry_auth_failure_includes_docker_logout_hint():
    err = Exception(
        "singularity instance start failed for docker://hubentu/coala-runtime-python:latest: "
        "unable to retrieve auth token: invalid username/password: unauthorized"
    )
    out = _handle_execution_error(err, "Python script execution")
    assert out.success is False
    assert "docker logout" in out.stderr.lower() or "registry logout" in out.stderr.lower()
    assert ".sif" in out.stderr


def test_generic_singularity_error_still_helpful():
    err = Exception("apptainer exec failed: no such instance")
    out = _handle_execution_error(err, "run")
    assert "singularity" in out.stderr.lower() or "apptainer" in out.stderr.lower()
