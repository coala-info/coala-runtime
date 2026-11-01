"""Default R image package list."""

from coala_runtime.tools.r_executor import RExecutor


def test_default_r_image_includes_excel_support():
    assert "readxl" in RExecutor.DEFAULT_PACKAGES
    assert "writexl" in RExecutor.DEFAULT_PACKAGES


def test_default_r_image_skips_installing_excel_packages():
    ex = RExecutor()
    assert ex.pip_packages_to_install(["readxl", "writexl", "ggplot2"]) == ["ggplot2"]
