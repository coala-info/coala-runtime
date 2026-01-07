"""Output parser for extracting files and data from script execution."""

import re
from pathlib import Path
from typing import List, Tuple


class OutputParser:
    """Parses script output to extract files and data."""

    # Patterns for detecting file paths in output
    FILE_PATH_PATTERNS = [
        r"Saved to:?\s+(.+\.(png|jpg|jpeg|pdf|svg|csv|json|txt|html))",
        r"Output file:?\s+(.+)",
        r"File saved:?\s+(.+)",
        r"Writing to:?\s+(.+)",
        r"/output/(.+)",  # Direct output directory references
    ]

    @staticmethod
    def parse_output(
        stdout: str, stderr: str, output_dir: str = "/output"
    ) -> Tuple[List[str], str]:
        """Parse script output to extract file paths and data.

        This method ensures all files generated in the output directory are detected
        and returned, regardless of whether they're mentioned in stdout/stderr.

        Args:
            stdout: Standard output from script
            stderr: Standard error from script
            output_dir: Output directory path (host path)

        Returns:
            Tuple of (output_files with full absolute paths, output_data)
        """
        import logging

        logger = logging.getLogger(__name__)

        output_path = Path(output_dir).resolve()
        output_files = []

        # Primary method: Scan the output directory for all files
        # This is the most reliable way to detect generated files
        if output_path.exists() and output_path.is_dir():
            logger.debug(f"Scanning output directory: {output_path}")

            # Use rglob to find all files recursively
            for item in output_path.rglob("*"):
                if item.is_file():
                    # Get absolute path
                    full_path = item.resolve()
                    full_path_str = str(full_path)

                    # Skip hidden files and common non-output files
                    if not item.name.startswith(".") and item.name not in [
                        ".gitkeep",
                        ".gitignore",
                    ]:
                        if full_path_str not in output_files:
                            output_files.append(full_path_str)
                            logger.debug(f"Found output file: {full_path_str}")
        else:
            logger.warning(f"Output directory does not exist: {output_path}")

        # Secondary method: Parse stdout/stderr for file path references
        # This helps catch files that might be in subdirectories or have unusual names
        combined_output = stdout + "\n" + stderr
        for pattern in OutputParser.FILE_PATH_PATTERNS:
            matches = re.findall(pattern, combined_output, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle tuple matches (from regex groups)
                    file_path = match[0] if match[0] else (match[1] if len(match) > 1 else None)
                else:
                    file_path = match

                if not file_path:
                    continue

                # Normalize path - handle /output/ prefix
                if file_path.startswith("/output/"):
                    file_path = file_path[8:]  # Remove /output/ prefix
                elif file_path.startswith("output/"):
                    file_path = file_path[7:]  # Remove output/ prefix
                elif file_path.startswith("/"):
                    # Absolute path, try to resolve relative to output_dir
                    file_path = file_path.lstrip("/")

                # Check if file exists in output directory
                if output_path.exists():
                    full_path = (output_path / file_path).resolve()
                    # Ensure the resolved path is within output_dir (security check)
                    try:
                        full_path.relative_to(output_path)
                        if full_path.exists() and full_path.is_file():
                            full_path_str = str(full_path)
                            if full_path_str not in output_files:
                                output_files.append(full_path_str)
                                logger.debug(f"Found file from stdout/stderr: {full_path_str}")
                    except ValueError:
                        # Path is outside output_dir, skip it
                        logger.debug(f"Skipping path outside output_dir: {file_path}")
                        pass

        # Remove duplicates and sort
        output_files = sorted(list(set(output_files)))

        logger.info(f"Found {len(output_files)} output file(s): {output_files}")

        # Extract data (non-file output)
        # If output looks like simple text/numbers and no files were found,
        # treat it as data output
        output_data = ""
        if not output_files:
            # Clean up stdout for data extraction
            cleaned_stdout = stdout.strip()
            # Remove common logging/debug messages
            cleaned_stdout = re.sub(r"^\[.*?\]\s*", "", cleaned_stdout, flags=re.MULTILINE)
            if cleaned_stdout:
                output_data = cleaned_stdout

        return output_files, output_data
