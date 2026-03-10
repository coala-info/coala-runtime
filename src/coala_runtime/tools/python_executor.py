"""Python executor tool implementation."""

import logging
from typing import List, Optional

from coala_runtime.runtime.executor_base import BaseExecutor

logger = logging.getLogger(__name__)


class PythonExecutor(BaseExecutor):
    """Executor for Python scripts using uv."""

    DEFAULT_IMAGE = "hubentu/coala-runtime-python:latest"
    # Pre-installed in the default image; skip installing when user requests them
    DEFAULT_PACKAGES: List[str] = ["numpy", "pandas", "matplotlib"]

    def __init__(
        self,
        image: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """Initialize Python executor.

        Args:
            image: Docker image to use (default: hubentu/coala-runtime-python:latest)
            output_dir: Output directory path
        """
        super().__init__(image or self.DEFAULT_IMAGE, output_dir=output_dir)

    def get_install_command(self, packages: List[str]) -> str:
        """Get uv pip install command.

        Args:
            packages: List of package names (can include version specifiers)

        Returns:
            Installation command
        """
        # Only install packages not already in the default image
        packages_to_install = [pkg for pkg in packages if pkg not in self.DEFAULT_PACKAGES]
        if not packages_to_install:
            return "echo 'No additional packages to install'"

        # Build package list with version specifiers
        package_list = " ".join(packages_to_install)
        return f"uv pip install --system {package_list}"

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
