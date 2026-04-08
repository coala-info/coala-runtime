"""Python executor tool implementation."""

import json
import logging
import shlex
from typing import Any, List, Optional, Tuple

from coala_runtime.runtime.executor_base import BaseExecutor

logger = logging.getLogger(__name__)


class PythonExecutor(BaseExecutor):
    """Executor for Python scripts; default Coala image uses uv for installs."""

    DEFAULT_IMAGE = "hubentu/coala-runtime-python:latest"
    # Pre-installed in the default image; skip installing when user requests them
    DEFAULT_PACKAGES: List[str] = ["numpy", "pandas", "matplotlib"]

    def __init__(
        self,
        image: Optional[str] = None,
        output_dir: Optional[str] = None,
        conda_packages: Optional[List[str]] = None,
    ):
        """Initialize Python executor.

        Args:
            image: Docker image to use (default: hubentu/coala-runtime-python:latest)
            output_dir: Output directory path
            conda_packages: Conda package specs (non-Python / conda-only deps), installed before pip/uv
        """
        super().__init__(image or self.DEFAULT_IMAGE, output_dir=output_dir)
        self.conda_packages: List[str] = []
        if conda_packages:
            for p in conda_packages:
                s = (p or "").strip()
                if s:
                    self.conda_packages.append(s)

    def _uses_default_coala_image(self) -> bool:
        return self.image == self.DEFAULT_IMAGE

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
        env = {"COALA_PIP_PROBE_JSON": json.dumps(pip_names)}
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
        """Drop pip packages already present in a custom image (conda:: lines unchanged)."""
        if self._uses_default_coala_image():
            return list(install_list)
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
            if self._install_uses_uv():
                pip_cmd = f"uv pip install --system {package_list}"
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
