"""R executor tool implementation."""

import logging
from typing import List, Optional

from coala_runtime.runtime.executor_base import BaseExecutor

logger = logging.getLogger(__name__)


class RExecutor(BaseExecutor):
    """Executor for R scripts using r2u and BiocManager."""

    DEFAULT_IMAGE = "coala-runtime-r:latest"
    DEFAULT_PACKAGES = ["tidyverse"]

    def __init__(
        self,
        image: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """Initialize R executor.

        Args:
            image: Docker image to use (default: coala-runtime-r:latest)
            output_dir: Output directory path
        """
        super().__init__(image or self.DEFAULT_IMAGE, output_dir=output_dir)

    def get_install_command(self, packages: List[str]) -> str:
        """Get R package installation command.

        Args:
            packages: List of package names
                     - Regular packages: installed via install.packages()
                     - Bioconductor: format 'bioc::package_name'

        Returns:
            Installation command as R script
        """
        if not packages:
            return "echo 'No packages to install'"

        # Separate CRAN and Bioconductor packages
        cran_packages = []
        bioc_packages = []

        for pkg in packages:
            if pkg.startswith("bioc::"):
                bioc_packages.append(pkg[6:])  # Remove 'bioc::' prefix
            else:
                cran_packages.append(pkg)

        # Build R installation script
        r_script_parts = []

        # Install CRAN packages
        if cran_packages:
            # Filter out default packages
            packages_to_install = [pkg for pkg in cran_packages if pkg not in self.DEFAULT_PACKAGES]
            if packages_to_install:
                # Use single quotes for package names in R
                pkg_list = ", ".join([f"'{pkg}'" for pkg in packages_to_install])
                r_script_parts.append(
                    f"install.packages(c({pkg_list}), repos='https://cloud.r-project.org')"
                )

        # Install Bioconductor packages
        if bioc_packages:
            pkg_list = ", ".join([f"'{pkg}'" for pkg in bioc_packages])
            r_script_parts.append(f"BiocManager::install(c({pkg_list}))")

        if not r_script_parts:
            return "echo 'No additional packages to install'"

        # Combine into single R command
        # Use double quotes for outer command and escape inner double quotes
        r_command = "; ".join(r_script_parts)
        # Escape double quotes in the R command for shell
        escaped_command = r_command.replace('"', '\\"')
        return f'Rscript -e "{escaped_command}"'

    def get_execution_command(self, script_path: str) -> str:
        """Get R execution command.

        Args:
            script_path: Path to R script

        Returns:
            Execution command
        """
        return f"Rscript {script_path}"

    def get_default_packages(self) -> List[str]:
        """Get default packages.

        Returns:
            List of default package names
        """
        return self.DEFAULT_PACKAGES.copy()

    def get_script_suffix(self) -> str:
        """Get R script suffix.

        Returns:
            '.R'
        """
        return ".R"
