"""Tests for coala-runtime build subcommand."""

from pathlib import Path
from unittest.mock import patch

import pytest

from coala_runtime.__main__ import cmd_build


def test_cmd_build_runs_build_script(tmp_path: Path):
    docker_dir = tmp_path / "docker"
    docker_dir.mkdir()
    (docker_dir / "Dockerfile.python").write_text("FROM python:3.12-slim\n")
    script = docker_dir / "build.sh"
    script.write_text("#!/bin/bash\nexit 0\n")
    script.chmod(0o755)

    with patch("coala_runtime.runtime.docker_images._project_root", return_value=tmp_path):
        with patch("coala_runtime.runtime.docker_images.subprocess.run") as mock_run:
            cmd_build()
            mock_run.assert_called_once()
            assert mock_run.call_args[0][0] == ["bash", str(script)]


def test_cmd_build_missing_repo_exits():
    with patch("coala_runtime.runtime.docker_images._project_root", return_value=None):
        with pytest.raises(SystemExit) as exc:
            cmd_build()
        assert exc.value.code == 1
