"""RExecutor: default vs custom image install list."""

from coala_runtime.tools.r_executor import RExecutor


class _SingularityLikeManager:
    system_site_packages_writable = False


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


def test_singularity_like_install_uses_writable_r_library():
    ex = RExecutor(container_manager=_SingularityLikeManager())
    cmd = ex.get_install_command(["ggplot2"])
    assert "R_LIBS_USER=" in cmd
    assert "/output/.coala-runtime/R/library" in cmd
    assert ".libPaths" in cmd
    assert "install.packages" in cmd


def test_singularity_like_execution_exports_r_libs_user():
    ex = RExecutor(container_manager=_SingularityLikeManager())
    cmd = ex.get_execution_command("/workspace/script.R")
    assert "R_LIBS_USER=" in cmd
    assert "/output/.coala-runtime/R/library" in cmd
    assert "Rscript /workspace/script.R" in cmd
