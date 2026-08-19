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


def test_untagged_default_r_image_skips_tidyverse():
    ex = RExecutor(image="coala-runtime-r")
    assert ex._uses_default_coala_image()
    cmd = ex.get_install_command(ex.DEFAULT_PACKAGES)
    assert "No additional" in cmd or "echo" in cmd.lower()


def test_cran_and_bioc_use_single_biocmanager_install():
    ex = RExecutor(image="rocker/r-ver:4.4")
    cmd = ex.get_install_command(["ggplot2", "bioc::limma"])
    assert cmd.count("BiocManager::install") == 1
    assert "ggplot2" in cmd and "limma" in cmd
    assert "install.packages" not in cmd


def test_singularity_like_install_uses_writable_r_library():
    ex = RExecutor(container_manager=_SingularityLikeManager())
    cmd = ex.get_install_command(["ggplot2"])
    assert "/output/.coala-runtime/R/library" in cmd
    assert ".libPaths" in cmd
    assert "BiocManager::install" in cmd
    assert "ask = FALSE" in cmd
    assert "export R_LIBS_USER" not in cmd
    assert ex.exec_environment()["R_LIBS_USER"] == "/output/.coala-runtime/R/library"


def test_writable_lib_execution_is_plain_rscript():
    ex = RExecutor(container_manager=_SingularityLikeManager())
    cmd = ex.get_execution_command("/workspace/script.R")
    assert cmd == "Rscript /workspace/script.R"
    assert "export" not in cmd
    assert ex.exec_environment()["R_LIBS_USER"] == "/output/.coala-runtime/R/library"


def test_root_docker_execution_has_no_r_libs_user_env():
    class _Root:
        system_site_packages_writable = True

    ex = RExecutor(container_manager=_Root())
    assert ex.get_execution_command("/workspace/script.R") == "Rscript /workspace/script.R"
    assert ex.exec_environment() == {}
