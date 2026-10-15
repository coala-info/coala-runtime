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


def test_describe_engine_uses_the_managers_own_description():
    """The execution log names the engine; xcrunner's manager says which one and where."""
    from coala_runtime.runtime.executor_base import _describe_engine

    class Described:
        def describe_container(self, container):
            return "xcrunner 0.1.6 · engine ns · container dir /tmp/x"

    class Plain:
        pass

    class Broken:
        def describe_container(self, container):
            raise RuntimeError("no")

    assert _describe_engine(Described(), object()) == "xcrunner 0.1.6 · engine ns · container dir /tmp/x"
    assert _describe_engine(Plain(), object()) == "Plain"
    assert _describe_engine(Broken(), object()) == "Broken"
