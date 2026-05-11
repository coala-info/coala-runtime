"""PythonExecutor install command: uv vs pip, conda."""

from coala_runtime.tools.python_executor import PythonExecutor


class _SingularityLikeManager:
    """Minimal stub: Singularity/Apptainer marks system site-packages read-only."""

    system_site_packages_writable = False


def test_default_image_uses_uv_for_packages():
    ex = PythonExecutor()
    cmd = ex.get_install_command(ex.DEFAULT_PACKAGES + ["seaborn"])
    assert "uv pip install --system" in cmd
    assert "seaborn" in cmd


def test_custom_image_uses_pip_for_packages():
    ex = PythonExecutor(image="quay.io/biocontainers/snapatac2:2.9.0--py312h91a5aaa_0")
    cmd = ex.get_install_command(["seaborn"])
    assert "python -m pip install" in cmd
    assert "seaborn" in cmd
    assert "uv pip" not in cmd


def test_conda_packages_field_before_pip():
    ex = PythonExecutor(
        image="quay.io/foo/bar:latest",
        conda_packages=["samtools"],
    )
    cmd = ex.get_install_command(["seaborn"])
    assert "conda install" in cmd or "mamba install" in cmd
    assert "samtools" in cmd
    assert "python -m pip install" in cmd
    assert "seaborn" in cmd
    assert " && " in cmd


def test_conda_prefix_in_packages():
    ex = PythonExecutor(image="quay.io/foo/bar:latest")
    cmd = ex.get_install_command(["conda::samtools", "seaborn"])
    assert "samtools" in cmd
    assert "conda::" not in cmd
    assert "seaborn" in cmd


def test_conda_only_no_pip_extras():
    ex = PythonExecutor(
        image="quay.io/foo/bar:latest",
        conda_packages=["samtools"],
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
    assert '--prefix "$COALA_PIP_PREFIX"' in cmd or "--prefix \"$COALA_PIP_PREFIX\"" in cmd
    assert "--system" not in cmd
    assert "requests" in cmd
    assert "UV_CACHE_DIR=" in cmd
    assert "/output/.coala-runtime" in cmd


def test_singularity_like_execution_sets_pythonpath():
    ex = PythonExecutor(container_manager=_SingularityLikeManager())
    cmd = ex.get_execution_command("/workspace/script.py")
    assert "PYTHONPATH=" in cmd
    assert "/output/.coala-runtime/pythonpath" in cmd
    assert "python /workspace/script.py" in cmd


def test_singularity_like_custom_image_uses_pip_prefix():
    ex = PythonExecutor(
        image="quay.io/biocontainers/snapatac2:2.9.0--py312h91a5aaa_0",
        container_manager=_SingularityLikeManager(),
    )
    cmd = ex.get_install_command(["seaborn"])
    assert "python -m pip install" in cmd
    assert '--prefix "$COALA_PIP_PREFIX"' in cmd
    assert "seaborn" in cmd
