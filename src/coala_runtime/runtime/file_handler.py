"""File handler for bind-mounting files and directories."""

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class FileHandler:
    """Handles file operations for container execution."""

    @staticmethod
    def prepare_volumes(
        input_files: Dict[str, str], output_dir: Optional[str] = None
    ) -> Dict[str, Dict[str, str]]:
        """Prepare volume bind mounts for Docker.

        Args:
            input_files: Map of container paths to host paths
                       e.g., {'/input/data.csv': '/host/path/data.csv'}
            output_dir: Output directory on host (will be mounted to /output)

        Returns:
            Docker volume configuration dict (host_path: {bind: container_path, mode: mode})

        Raises:
            ValueError: If host path doesn't exist
        """
        volumes = {}

        # Add output directory bind mount if provided
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            volumes[str(output_path.absolute())] = {"bind": "/output", "mode": "rw"}

        # Add input file bind mounts
        for container_path, host_path in input_files.items():
            host_path_obj = Path(host_path)
            if not host_path_obj.exists():
                raise ValueError(f"Host path does not exist: {host_path}")

            # Ensure container path is absolute
            if not container_path.startswith("/"):
                container_path = f"/{container_path}"

            volumes[str(host_path_obj.absolute())] = {"bind": container_path, "mode": "rw"}
            logger.debug(f"Prepared bind mount: {host_path} -> {container_path}")

        return volumes

    @staticmethod
    def list_output_files(output_dir: str = "/output") -> list[str]:
        """List files in the output directory.

        Args:
            output_dir: Output directory path (host path)

        Returns:
            List of file paths
        """
        output_path = Path(output_dir)
        if not output_path.exists():
            return []

        files = []
        for item in output_path.rglob("*"):
            if item.is_file():
                # Return relative path from output_dir
                rel_path = item.relative_to(output_path)
                files.append(str(rel_path))

        return sorted(files)

    @staticmethod
    def ensure_output_dir(output_dir: str = "/output") -> None:
        """Ensure output directory exists.

        Args:
            output_dir: Output directory path (host path)
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
