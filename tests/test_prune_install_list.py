"""Prune already-installed packages on custom images (container probes)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from coala_runtime.tools.python_executor import PythonExecutor
from coala_runtime.tools.r_executor import RExecutor


@pytest.mark.asyncio
async def test_python_default_image_prunes_present_packages():
    ex = PythonExecutor()
    ex.container_manager = MagicMock()
    ex.container_manager.exec_command = AsyncMock(return_value=(0, b'["seaborn"]', b""))
    c = MagicMock()
    out = await ex.prune_install_list_for_container(c, ["scipy", "seaborn"])
    assert out == ["seaborn"]
    ex.container_manager.exec_command.assert_called_once()


@pytest.mark.asyncio
async def test_python_custom_prune_keeps_missing_pip_only():
    ex = PythonExecutor(image="quay.io/biocontainers/snapatac2:latest")
    ex.container_manager = MagicMock()
    ex.container_manager.exec_command = AsyncMock(
        return_value=(0, b'["seaborn","pandas"]', b"")
    )
    c = MagicMock()
    before = ["snapatac2", "seaborn", "conda::samtools", "pandas"]
    out = await ex.prune_install_list_for_container(c, before)
    assert out == ["seaborn", "conda::samtools", "pandas"]


@pytest.mark.asyncio
async def test_python_custom_probe_failure_falls_back_to_full_list():
    ex = PythonExecutor(image="custom:latest")
    ex.container_manager = MagicMock()
    ex.container_manager.exec_command = AsyncMock(return_value=(1, b"err", b""))
    c = MagicMock()
    before = ["snapatac2"]
    out = await ex.prune_install_list_for_container(c, before)
    assert out == before


@pytest.mark.asyncio
async def test_r_default_image_prunes_present_packages():
    ex = RExecutor()
    sep = chr(31)
    ex.container_manager = MagicMock()
    ex.container_manager.exec_command = AsyncMock(
        return_value=(0, sep.join(["ggplot2"]).encode(), b"")
    )
    c = MagicMock()
    out = await ex.prune_install_list_for_container(c, ["tidyverse", "ggplot2"])
    assert out == ["ggplot2"]
    ex.container_manager.exec_command.assert_called_once()


@pytest.mark.asyncio
async def test_r_custom_prune_keeps_missing_only():
    ex = RExecutor(image="quay.io/biocontainers/r-archr:latest")
    sep = chr(31)
    ex.container_manager = MagicMock()
    # ArchR already in image; ggplot2 missing
    ex.container_manager.exec_command = AsyncMock(
        return_value=(0, sep.join(["ggplot2"]).encode(), b"")
    )
    c = MagicMock()
    before = ["ArchR", "ggplot2"]
    out = await ex.prune_install_list_for_container(c, before)
    assert out == ["ggplot2"]
