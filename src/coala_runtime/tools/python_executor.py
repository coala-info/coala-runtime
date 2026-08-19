"""Python executor tool implementation."""

import json
import logging
import re
import shlex
from typing import Any, Dict, List, Optional, Tuple

from coala_runtime.runtime.executor_base import BaseExecutor, uses_default_coala_image

logger = logging.getLogger(__name__)

# Writable prefix when the image site-packages are not writable (Singularity, or
# Docker/Podman running as the host uid). Cache dirs live on host-backed /output.
_SINGULARITY_RUNTIME_ROOT = "/output/.coala-runtime"
_SINGULARITY_PIP_PREFIX = f"{_SINGULARITY_RUNTIME_ROOT}/pip-prefix"
_PYTHON_SITE_PACKAGES = [
    f"{_SINGULARITY_PIP_PREFIX}/lib/python3.{minor}/site-packages"
    for minor in range(10, 15)
]

# Import name → PyPI dist when they differ (agent often omits ``packages``).
_IMPORT_TO_PIP = {
    "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn",
    "PIL": "pillow",
    "cv2": "opencv-python-headless",
    "yaml": "pyyaml",
    "dateutil": "python-dateutil",
}
_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][\w]*)", re.M)


class PythonExecutor(BaseExecutor):
    """Executor for Python scripts; default Coala image uses uv for installs."""

    DEFAULT_IMAGE = "coala-runtime-python:latest"
    # Pre-installed in the default image; skip installing when user requests them
    DEFAULT_PACKAGES: List[str] = ["numpy", "pandas", "matplotlib"]

    def __init__(
        self,
        image: Optional[str] = None,
        output_dir: Optional[str] = None,
        conda_packages: Optional[List[str]] = None,
        container_manager: Optional[Any] = None,
    ):
        """Initialize Python executor.

        Args:
            image: Docker image to use (default: coala-runtime-python:latest)
            output_dir: Output directory path
            conda_packages: Conda package specs (non-Python / conda-only deps), installed before pip/uv
            container_manager: Optional backend from ``make_container_manager()`` (tests may inject a stub)
        """
        super().__init__(
            image or self.DEFAULT_IMAGE,
            output_dir=output_dir,
            container_manager=container_manager,
        )
        self.conda_packages: List[str] = []
        if conda_packages:
            for p in conda_packages:
                s = (p or "").strip()
                if s:
                    self.conda_packages.append(s)

    def _uses_default_coala_image(self) -> bool:
        return uses_default_coala_image(self.image, self.DEFAULT_IMAGE)

    def compose_install_package_list(self, user_packages: List[str]) -> List[str]:
        """Custom images: only user-listed packages (no assumed numpy/pandas/matplotlib)."""
        if self._uses_default_coala_image():
            return self.get_default_packages() + user_packages
        return list(user_packages)

    def should_run_package_install(self, install_list: List[str]) -> bool:
        return bool(install_list) or bool(self.conda_packages)

    def _install_uses_uv(self) -> bool:
        """Coala default image ships ``uv``; custom images typically only have pip."""
        return self._uses_default_coala_image()

    def _use_workspace_pip_prefix(self) -> bool:
        """Install to /output when system site-packages are not writable."""
        return not getattr(self.container_manager, "system_site_packages_writable", True)

    def exec_environment(self) -> Dict[str, str]:
        if not self._use_workspace_pip_prefix():
            return {}
        root = _SINGULARITY_RUNTIME_ROOT
        return {
            "COALA_PIP_PREFIX": _SINGULARITY_PIP_PREFIX,
            "UV_CACHE_DIR": f"{root}/uv-cache",
            "PIP_CACHE_DIR": f"{root}/pip-cache",
            "XDG_CACHE_HOME": f"{root}/xdg-cache",
            "XDG_CONFIG_HOME": f"{root}/xdg-config",
            "HOME": f"{root}/home",
            "MPLCONFIGDIR": f"{root}/mplconfig",
            "TMPDIR": f"{root}/tmp",
            "PYTHONPATH": ":".join(_PYTHON_SITE_PACKAGES),
        }

    def prepare_runtime_dirs(self) -> list[str]:
        if not self._use_workspace_pip_prefix():
            return []
        env = self.exec_environment()
        return [
            env["UV_CACHE_DIR"],
            env["PIP_CACHE_DIR"],
            env["XDG_CACHE_HOME"],
            env["XDG_CONFIG_HOME"],
            env["HOME"],
            env["MPLCONFIGDIR"],
            env["TMPDIR"],
            _SINGULARITY_PIP_PREFIX,
        ]

    def packages_implied_by_script(self, script: str) -> List[str]:
        found: List[str] = []
        seen: set[str] = set()
        for name in _IMPORT_RE.findall(script or ""):
            pip_name = _IMPORT_TO_PIP.get(name)
            if pip_name and pip_name not in seen:
                seen.add(pip_name)
                found.append(pip_name)
        return found

    @staticmethod
    def _split_pip_and_conda_specs(packages: List[str]) -> Tuple[List[str], List[str]]:
        """Split ``packages`` into pip-style names vs ``conda::spec`` entries."""
        pip_like: List[str] = []
        conda_from_prefix: List[str] = []
        for raw in packages:
            if raw.startswith("conda::"):
                spec = raw[7:].strip()
                if spec:
                    conda_from_prefix.append(spec)
            else:
                pip_like.append(raw)
        return pip_like, conda_from_prefix

    def _conda_targets(self, all_packages: List[str]) -> List[str]:
        _, from_prefix = self._split_pip_and_conda_specs(all_packages)
        merged: List[str] = []
        seen = set()
        for p in self.conda_packages + from_prefix:
            if p not in seen:
                seen.add(p)
                merged.append(p)
        return merged

    def pip_packages_to_install(self, all_packages: List[str]) -> List[str]:
        pip_like, _ = self._split_pip_and_conda_specs(all_packages)
        if not self._uses_default_coala_image():
            return list(pip_like)
        default_set = set(self.DEFAULT_PACKAGES)
        return [p for p in pip_like if p not in default_set]

    def install_plan_log_details(self, all_packages: List[str], pip_targets: List[str]) -> str:
        conda_targets = self._conda_targets(all_packages)
        parts: List[str] = []
        if conda_targets:
            parts.append(f"conda={conda_targets}")
        parts.append(f"pip={pip_targets}")
        return "Install plan: " + ", ".join(parts)

    async def _missing_pip_distribution_names(self, container: Any, pip_names: List[str]) -> List[str]:
        """Return pip distribution names that are not already installed (``pip show``)."""
        if not pip_names:
            return []
        env = dict(self.exec_environment())
        env["COALA_PIP_PROBE_JSON"] = json.dumps(pip_names)
        cmd = [
            "python",
            "-c",
            "import json,os,subprocess,sys;"
            "pkgs=json.loads(os.environ['COALA_PIP_PROBE_JSON']);"
            "missing=[p for p in pkgs if subprocess.run([sys.executable,'-m','pip','show',p],"
            "capture_output=True).returncode!=0];"
            "print(json.dumps(missing))",
        ]
        exit_code, stdout, _ = await self.container_manager.exec_command(
            container, cmd, environment=env
        )
        if exit_code != 0:
            raise RuntimeError(
                f"pip preinstall probe failed (exit {exit_code}): "
                f"{stdout.decode('utf-8', errors='replace')!r}"
            )
        raw = stdout.decode("utf-8", errors="replace").strip() or "[]"
        return json.loads(raw)

    async def prune_install_list_for_container(
        self, container: Any, install_list: List[str]
    ) -> List[str]:
        """Drop pip packages already present in the image (``pip show``)."""
        pip_like, _ = self._split_pip_and_conda_specs(install_list)
        if not pip_like:
            return list(install_list)
        try:
            ordered_unique = list(dict.fromkeys(pip_like))
            missing = await self._missing_pip_distribution_names(container, ordered_unique)
        except Exception as e:
            logger.warning("Skipping pip install prune (probe failed): %s", e)
            return list(install_list)
        missing_set = set(missing)
        return [item for item in install_list if item.startswith("conda::") or item in missing_set]

    @staticmethod
    def _conda_install_shell_fragment(conda_targets: List[str]) -> str:
        """Shell snippet: mamba or conda install with common science channels."""
        quoted = " ".join(shlex.quote(p) for p in conda_targets)
        return (
            "if command -v mamba >/dev/null 2>&1; then "
            f"mamba install -y -c conda-forge -c bioconda {quoted}; "
            f"else conda install -y -c conda-forge -c bioconda {quoted}; fi"
        )

    def get_install_command(self, packages: List[str]) -> str:
        """Install conda targets first (if any), then pip/uv for Python packages.

        Use ``conda_packages`` or entries like ``conda::samtools`` in ``packages`` for
        non-Python / conda-only dependencies.
        """
        conda_targets = self._conda_targets(packages)
        packages_to_install = self.pip_packages_to_install(packages)

        conda_cmd = ""
        if conda_targets:
            conda_cmd = self._conda_install_shell_fragment(conda_targets)

        if packages_to_install:
            package_list = " ".join(shlex.quote(p) for p in packages_to_install)
            prefix_arg = shlex.quote(_SINGULARITY_PIP_PREFIX)
            if self._install_uses_uv():
                if self._use_workspace_pip_prefix():
                    pip_cmd = f"uv pip install --prefix {prefix_arg} {package_list}"
                else:
                    pip_cmd = f"uv pip install --system {package_list}"
            else:
                if self._use_workspace_pip_prefix():
                    pip_cmd = (
                        "python -m pip install --no-cache-dir --root-user-action=ignore "
                        f"--prefix {prefix_arg} {package_list}"
                    )
                else:
                    pip_cmd = (
                        "python -m pip install --no-cache-dir --root-user-action=ignore "
                        f"{package_list}"
                    )
        else:
            pip_cmd = ""

        if conda_cmd and pip_cmd:
            return f"{conda_cmd} && {pip_cmd}"
        if conda_cmd:
            return conda_cmd
        if pip_cmd:
            return pip_cmd
        return "echo 'No additional packages to install'"

    def get_execution_command(self, script_path: str) -> str:
        """Get Python execution command.

        Args:
            script_path: Path to Python script

        Returns:
            Execution command
        """
        return f"python {script_path}"

    def get_default_packages(self) -> List[str]:
        """Get default packages.

        Returns:
            List of default package names
        """
        return self.DEFAULT_PACKAGES.copy()

    def get_script_suffix(self) -> str:
        """Get Python script suffix.

        Returns:
            '.py'
        """
        return ".py"
