"""RExecutor: default vs custom image install list."""

from coala_runtime.tools.r_executor import RExecutor


def test_custom_image_does_not_merge_tidyverse():
    ex = RExecutor(image="rocker/r-ver:4.4")
    assert ex.compose_install_package_list([]) == []
    assert ex.compose_install_package_list(["ggplot2"]) == ["ggplot2"]


def test_custom_image_can_install_tidyverse_if_listed():
    ex = RExecutor(image="rocker/r-ver:4.4")
    cmd = ex.get_install_command(["tidyverse"])
    assert "tidyverse" in cmd.lower()


def test_default_image_skips_redundant_tidyverse_in_command():
    ex = RExecutor()
    cmd = ex.get_install_command(ex.DEFAULT_PACKAGES)
    assert "No additional" in cmd or "echo" in cmd.lower()
