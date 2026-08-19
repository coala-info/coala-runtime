"""PythonExecutor install command: uv vs pip, conda."""

from coala_runtime.tools.python_executor import PythonExecutor


class _SingularityLikeManager:
    """Minimal stub: Singularity/Apptainer marks system site-packages read-only."""

    system_site_packages_writable = False


class _RootLikeManager:
    """Docker/Podman running as root — system site-packages are writable."""

    system_site_packages_writable = True


def test_default_image_uses_uv_for_packages():
    ex = PythonExecutor(container_manager=_RootLikeManager())
    cmd = ex.get_install_command(ex.DEFAULT_PACKAGES + ["seaborn"])
    assert "uv pip install --system" in cmd
    assert "seaborn" in cmd


def test_custom_image_uses_pip_for_packages():
    ex = PythonExecutor(
        image="quay.io/biocontainers/snapatac2:2.9.0--py312h91a5aaa_0",
        container_manager=_RootLikeManager(),
    )
    cmd = ex.get_install_command(["seaborn"])
    assert "python -m pip install" in cmd
    assert "seaborn" in cmd
    assert "uv pip" not in cmd


def test_conda_packages_field_before_pip():
    ex = PythonExecutor(
        image="quay.io/foo/bar:latest",
        conda_packages=["samtools"],
        container_manager=_RootLikeManager(),
    )
    cmd = ex.get_install_command(["seaborn"])
    assert "conda install" in cmd or "mamba install" in cmd
    assert "samtools" in cmd
    assert "python -m pip install" in cmd
    assert "seaborn" in cmd
    assert " && " in cmd


def test_conda_prefix_in_packages():
    ex = PythonExecutor(
        image="quay.io/foo/bar:latest",
        container_manager=_RootLikeManager(),
    )
    cmd = ex.get_install_command(["conda::samtools", "seaborn"])
    assert "samtools" in cmd
    assert "conda::" not in cmd
    assert "seaborn" in cmd


def test_conda_only_no_pip_extras():
    ex = PythonExecutor(
        image="quay.io/foo/bar:latest",
        conda_packages=["samtools"],
        container_manager=_RootLikeManager(),
    )
    cmd = ex.get_install_command([])
    assert "conda install" in cmd or "mamba install" in cmd
    assert "samtools" in cmd
    assert "pip install" not in cmd


def test_pip_packages_to_install_excludes_conda_prefix():
    ex = PythonExecutor(conda_packages=["x"])
    all_p = ex.DEFAULT_PACKAGES + ["conda::samtools", "seaborn"]
    assert ex.pip_packages_to_install(all_p) == ["seaborn"]


def test_install_plan_log_details_includes_conda():
    ex = PythonExecutor(conda_packages=["samtools"])
    all_p = ex.DEFAULT_PACKAGES + ["seaborn"]
    pip_t = ex.pip_packages_to_install(all_p)
    line = ex.install_plan_log_details(all_p, pip_t)
    assert "conda=" in line
    assert "samtools" in line
    assert "seaborn" in line


def test_no_packages_echo():
    ex = PythonExecutor()
    cmd = ex.get_install_command(ex.DEFAULT_PACKAGES)
    assert "No additional packages" in cmd


def test_custom_image_does_not_merge_default_python_packages():
    ex = PythonExecutor(image="custom:latest")
    assert ex.compose_install_package_list(["seaborn"]) == ["seaborn"]
    assert ex.compose_install_package_list([]) == []


def test_custom_image_pip_targets_include_numpy_if_requested():
    ex = PythonExecutor(image="custom:latest")
    assert ex.pip_packages_to_install(["numpy", "pandas"]) == ["numpy", "pandas"]


def test_default_image_still_prepends_defaults_for_compose():
    ex = PythonExecutor()
    merged = ex.compose_install_package_list(["seaborn"])
    assert set(ex.DEFAULT_PACKAGES).issubset(set(merged))
    assert "seaborn" in merged


def test_singularity_like_uses_prefix_instead_of_system_uv():
    ex = PythonExecutor(container_manager=_SingularityLikeManager())
    cmd = ex.get_install_command(ex.DEFAULT_PACKAGES + ["requests"])
    assert "uv pip install" in cmd
    assert "--prefix /output/.coala-runtime/pip-prefix" in cmd
    assert "--system" not in cmd
    assert "requests" in cmd
    assert "export" not in cmd
    assert "&&" not in cmd
    env = ex.exec_environment()
    assert env["UV_CACHE_DIR"] == "/output/.coala-runtime/uv-cache"
    assert "/output/.coala-runtime/pip-prefix" in env["PYTHONPATH"]
    assert env["MPLCONFIGDIR"] == "/output/.coala-runtime/mplconfig"
    assert env["HOME"] == "/output/.coala-runtime/home"
    assert env["XDG_CONFIG_HOME"] == "/output/.coala-runtime/xdg-config"
    dirs = ex.prepare_runtime_dirs()
    assert env["MPLCONFIGDIR"] in dirs
    assert env["HOME"] in dirs


def test_untagged_default_image_uses_uv_like_latest():
    ex = PythonExecutor(
        image="coala-runtime-python",
        container_manager=_RootLikeManager(),
    )
    assert ex._uses_default_coala_image()
    cmd = ex.get_install_command(ex.DEFAULT_PACKAGES + ["seaborn"])
    assert "uv pip install --system" in cmd
    assert "seaborn" in cmd


def test_hub_default_image_is_still_default():
    ex = PythonExecutor(image="hubentu/coala-runtime-python:latest")
    assert ex._uses_default_coala_image()
    assert ex.pip_packages_to_install(["numpy", "seaborn"]) == ["seaborn"]


def test_packages_implied_by_script_maps_bs4():
    ex = PythonExecutor()
    assert ex.packages_implied_by_script("from bs4 import BeautifulSoup\n") == [
        "beautifulsoup4"
    ]
    assert ex.packages_implied_by_script("import os\nimport json\n") == []
    assert "scikit-learn" in ex.packages_implied_by_script("import sklearn\n")


def test_singularity_like_execution_sets_pythonpath():
    ex = PythonExecutor(container_manager=_SingularityLikeManager())
    cmd = ex.get_execution_command("/workspace/script.py")
    assert cmd == "python /workspace/script.py"
    assert "export" not in cmd
    env = ex.exec_environment()
    assert "python3.12/site-packages" in env["PYTHONPATH"]


def test_singularity_like_custom_image_uses_pip_prefix():
    ex = PythonExecutor(
        image="quay.io/biocontainers/snapatac2:2.9.0--py312h91a5aaa_0",
        container_manager=_SingularityLikeManager(),
    )
    cmd = ex.get_install_command(["seaborn"])
    assert "python -m pip install" in cmd
    assert "--prefix /output/.coala-runtime/pip-prefix" in cmd
    assert "seaborn" in cmd
    assert "export" not in cmd
