"""R executor tool implementation."""

import logging
import shlex
from typing import Any, List, Optional

from coala_runtime.runtime.executor_base import BaseExecutor

logger = logging.getLogger(__name__)

# Writable R library on Singularity/Apptainer (host-backed /output; avoid tiny tmpfs /tmp).
_SINGULARITY_R_LIB = "/output/.coala-runtime/R/library"


class RExecutor(BaseExecutor):
    """Executor for R scripts using Bioconductor Docker (CRAN + BiocManager installs)."""

    DEFAULT_IMAGE = "coala-runtime-r:latest"
    # Pre-installed in the default image; skip installing when user requests them
    DEFAULT_PACKAGES: List[str] = ["tidyverse"]

    def __init__(
        self,
        image: Optional[str] = None,
        output_dir: Optional[str] = None,
        container_manager: Optional[Any] = None,
    ):
        """Initialize R executor.

        Args:
            image: Docker image to use (default: coala-runtime-r:latest)
            output_dir: Output directory path
            container_manager: Optional backend from ``make_container_manager()`` (tests may inject a stub)
        """
        super().__init__(
            image or self.DEFAULT_IMAGE,
            output_dir=output_dir,
            container_manager=container_manager,
        )

    def _uses_default_coala_image(self) -> bool:
        return self.image == self.DEFAULT_IMAGE

    def _use_writable_r_library(self) -> bool:
        """Singularity/Apptainer: install CRAN/Bioc packages under /tmp, not read-only site-library."""
        return not getattr(self.container_manager, "system_site_packages_writable", True)

    def compose_install_package_list(self, user_packages: List[str]) -> List[str]:
        """Custom images: only user-listed packages (no assumed tidyverse)."""
        if self._uses_default_coala_image():
            return self.get_default_packages() + user_packages
        return list(user_packages)

    def pip_packages_to_install(self, all_packages: List[str]) -> List[str]:
        if not self._uses_default_coala_image():
            return list(all_packages)
        default_set = set(self.DEFAULT_PACKAGES)
        return [p for p in all_packages if p not in default_set]

    async def _missing_r_packages(self, container: Any, package_names: List[str]) -> List[str]:
        """Return R package names whose namespaces are not available (``requireNamespace``)."""
        if not package_names:
            return []
        sep = chr(31)
        env = {"COALA_R_PROBE_PKGS": sep.join(package_names)}
        r_code = (
            f'pkgs <- strsplit(Sys.getenv("COALA_R_PROBE_PKGS"), "{sep}", fixed=TRUE)[[1]]; '
            "pkgs <- pkgs[nchar(pkgs) > 0]; "
            "miss <- character(0); "
            "for (p in pkgs) { "
            "if (!suppressWarnings(requireNamespace(p, quietly=TRUE))) "
            "miss <- c(miss, p) }; "
            f"if (length(miss)) cat(paste(miss, collapse='{sep}'))"
        )
        cmd = ["Rscript", "-e", r_code]
        exit_code, stdout, _ = await self.container_manager.exec_command(
            container, cmd, environment=env
        )
        if exit_code != 0:
            raise RuntimeError(
                f"R preinstall probe failed (exit {exit_code}): "
                f"{stdout.decode('utf-8', errors='replace')!r}"
            )
        text = stdout.decode("utf-8", errors="replace").strip()
        if not text:
            return []
        return [p.strip() for p in text.split(sep) if p.strip()]

    async def prune_install_list_for_container(
        self, container: Any, install_list: List[str]
    ) -> List[str]:
        """Drop CRAN/Bioc packages already installed in a custom image."""
        if self._uses_default_coala_image():
            return list(install_list)
        if not install_list:
            return list(install_list)
        names_ordered: List[str] = []
        for item in install_list:
            if item.startswith("bioc::"):
                names_ordered.append(item[6:])
            else:
                names_ordered.append(item)
        try:
            ordered_unique = list(dict.fromkeys(names_ordered))
            missing = await self._missing_r_packages(container, ordered_unique)
        except Exception as e:
            logger.warning("Skipping R install prune (probe failed): %s", e)
            return list(install_list)
        missing_set = set(missing)
        pruned: List[str] = []
        for item in install_list:
            nm = item[6:] if item.startswith("bioc::") else item
            if nm in missing_set:
                pruned.append(item)
        return pruned

    @staticmethod
    def _r_package_names(packages: List[str]) -> List[str]:
        """Map install specs to R package names (``bioc::Pkg`` → ``Pkg``)."""
        return [p[6:] if p.startswith("bioc::") else p for p in packages]

    def _packages_for_biocmanager_install(self, packages: List[str]) -> List[str]:
        """Package names to pass to ``BiocManager::install`` (deduped, defaults skipped)."""
        names = self._r_package_names(packages)
        if self._uses_default_coala_image():
            default_set = set(self.DEFAULT_PACKAGES)
            names = [n for n in names if n not in default_set]
        return list(dict.fromkeys(names))

    @staticmethod
    def _biocmanager_install_expr(package_names: List[str]) -> str:
        """R expression: BiocManager install (preferred binaries on Bioconductor Docker)."""
        pkg_list = ", ".join(f"'{pkg}'" for pkg in package_names)
        return f"BiocManager::install(c({pkg_list}), ask = FALSE, update = FALSE)"

    def get_install_command(self, packages: List[str]) -> str:
        """Get R package installation command.

        Args:
            packages: List of package names
                     - CRAN: plain names (e.g. ``ggplot2``)
                     - Bioconductor: ``bioc::package_name`` (optional; same installer)

        Returns:
            Installation command as R script
        """
        if not packages:
            return "echo 'No packages to install'"

        packages_to_install = self._packages_for_biocmanager_install(packages)
        if not packages_to_install:
            return "echo 'No additional packages to install'"

        r_command = self._biocmanager_install_expr(packages_to_install)
        if self._use_writable_r_library():
            lib_esc = _SINGULARITY_R_LIB.replace("\\", "\\\\").replace("'", "\\'")
            r_command = (
                "{ lib <- '"
                + lib_esc
                + "'; dir.create(lib, recursive=TRUE, showWarnings=FALSE); "
                ".libPaths(c(lib, .libPaths())); "
                + r_command
                + " }"
            )

        # Use double quotes for outer command and escape inner double quotes
        escaped_command = r_command.replace('"', '\\"')
        lib_sh = shlex.quote(_SINGULARITY_R_LIB)
        inner = f'Rscript -e "{escaped_command}"'
        if self._use_writable_r_library():
            return (
                f"export R_LIBS_USER={lib_sh} && mkdir -p {lib_sh} && {inner}"
            )
        return inner

    def get_execution_command(self, script_path: str) -> str:
        """Get R execution command.

        Args:
            script_path: Path to R script

        Returns:
            Execution command
        """
        base = f"Rscript {script_path}"
        if self._use_writable_r_library():
            lib_sh = shlex.quote(_SINGULARITY_R_LIB)
            return f"export R_LIBS_USER={lib_sh} && mkdir -p {lib_sh} && {base}"
        return base

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
