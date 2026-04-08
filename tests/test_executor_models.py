"""Tests for MCP executor input models."""

import pytest
from pydantic import ValidationError

from coala_runtime.server import PythonExecutorInput, RExecutorInput


def test_python_executor_input_container_stripped():
    m = PythonExecutorInput(script="print(1)", container="  python:3.12-slim  ")
    assert m.container == "python:3.12-slim"


def test_python_executor_input_container_none_ok():
    m = PythonExecutorInput(script="print(1)")
    assert m.container is None


def test_python_executor_input_container_empty_rejected():
    with pytest.raises(ValidationError):
        PythonExecutorInput(script="print(1)", container="")
    with pytest.raises(ValidationError):
        PythonExecutorInput(script="print(1)", container="   ")


def test_r_executor_input_container_stripped():
    m = RExecutorInput(script="print(1)", container="  rocker/r-ver:4.4  ")
    assert m.container == "rocker/r-ver:4.4"


def test_r_executor_input_container_empty_rejected():
    with pytest.raises(ValidationError):
        RExecutorInput(script="x<-1", container="")


def test_skip_package_install_defaults_false():
    py = PythonExecutorInput(script="print(1)")
    r = RExecutorInput(script="x<-1")
    assert py.skip_package_install is False
    assert r.skip_package_install is False


def test_skip_package_install_true_accepted():
    py = PythonExecutorInput(
        script="print(1)",
        container="python:3.12-slim",
        skip_package_install=True,
    )
    assert py.skip_package_install is True


def test_conda_packages_stripped():
    py = PythonExecutorInput(script="print(1)", conda_packages=["  samtools  "])
    assert py.conda_packages == ["samtools"]


def test_conda_packages_rejects_empty_entry():
    with pytest.raises(ValidationError):
        PythonExecutorInput(script="print(1)", conda_packages=[""])
