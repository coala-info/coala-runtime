"""Base executor class for script execution."""

import asyncio
import base64
import logging
import tempfile
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from coala_runtime.runtime.container_manager import ContainerManager
from coala_runtime.runtime.file_handler import FileHandler
from coala_runtime.utils.output_parser import OutputParser

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Result of script execution."""

    def __init__(
        self,
        success: bool,
        exit_code: int,
        stdout: str,
        stderr: str,
        output_files: List[str],
        output_data: str,
        container_logs: str,
        execution_time: float,
    ):
        """Initialize execution result.

        Args:
            success: Whether execution succeeded
            exit_code: Process exit code
            stdout: Standard output
            stderr: Standard error
            output_files: List of output file paths
            output_data: Echoed string/number output
            container_logs: Full container logs
            execution_time: Execution time in seconds
        """
        self.success = success
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.output_files = output_files
        self.output_data = output_data
        self.container_logs = container_logs
        self.execution_time = execution_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "output_files": self.output_files,
            "output_data": self.output_data,
            "container_logs": self.container_logs,
            "execution_time": self.execution_time,
        }


class BaseExecutor(ABC):
    """Base class for script executors."""

    def __init__(
        self,
        image: str,
        container_manager: Optional[ContainerManager] = None,
        output_dir: Optional[str] = None,
    ):
        """Initialize executor.

        Args:
            image: Docker image to use
            container_manager: Optional container manager instance
            output_dir: Output directory path (host path)
        """
        self.image = image
        self.container_manager = container_manager or ContainerManager()
        self.output_dir = output_dir or tempfile.mkdtemp(prefix="coala_output_")
        FileHandler.ensure_output_dir(self.output_dir)

    @abstractmethod
    def get_install_command(self, packages: List[str]) -> str:
        """Get command to install packages.

        Args:
            packages: List of package names to install

        Returns:
            Installation command string
        """
        pass

    @abstractmethod
    def get_execution_command(self, script_path: str) -> str:
        """Get command to execute script.

        Args:
            script_path: Path to script file in container

        Returns:
            Execution command string
        """
        pass

    @abstractmethod
    def get_default_packages(self) -> List[str]:
        """Get default packages to install.

        Returns:
            List of default package names
        """
        pass

    async def execute(
        self,
        script: Optional[str] = None,
        script_file: Optional[str] = None,
        packages: Optional[List[str]] = None,
        input_files: Optional[Dict[str, str]] = None,
        timeout: int = 300,
    ) -> ExecutionResult:
        """Execute a script in a container.

        Args:
            script: Script code to execute (either script or script_file must be provided)
            script_file: Path to script file to execute (either script or script_file must be provided)
            packages: Additional packages to install
            input_files: Map of container paths to host paths
            timeout: Execution timeout in seconds (0 = no timeout)

        Returns:
            Execution result
        """
        # Validate that either script or script_file is provided
        if not script and not script_file:
            raise ValueError("Either 'script' or 'script_file' must be provided")
        if script and script_file:
            raise ValueError("Cannot provide both 'script' and 'script_file'")

        start_time = time.time()
        container = None
        temp_script_file = None

        try:
            # Prepare volumes (includes output directory)
            volumes = FileHandler.prepare_volumes(input_files or {}, output_dir=self.output_dir)

            # Use script_file if provided, otherwise create temp file from script
            if script_file:
                script_path = script_file
                # Verify file exists
                if not Path(script_file).exists():
                    raise FileNotFoundError(f"Script file not found: {script_file}")
            else:
                # Create temporary script file from script string
                temp_script_file = tempfile.NamedTemporaryFile(
                    mode="w", suffix=self.get_script_suffix(), delete=False
                )
                temp_script_file.write(script)
                temp_script_file.close()
                script_path = temp_script_file.name

            # Add script to volumes
            container_script_path = f"/workspace/script{self.get_script_suffix()}"
            volumes[script_path] = {"bind": container_script_path, "mode": "ro"}

            # Create container with a command that keeps it running
            container = await self.container_manager.create_container(
                image=self.image,
                command=["tail", "-f", "/dev/null"],  # Keep container running
                volumes=volumes,
                working_dir="/workspace",
            )

            # Start container
            await self.container_manager.start_container(container)

            # Wait a moment for container to be fully ready and verify it's running
            await asyncio.sleep(1.0)
            container.reload()
            if container.status != "running":
                raise RuntimeError(
                    f"Container {container.id[:12]} is not running after start (status: {container.status})"
                )

            # Collect all execution logs
            execution_logs = []
            execution_logs.append("=" * 60)
            execution_logs.append("Starting script execution")
            execution_logs.append("=" * 60)

            # Install packages
            all_packages = self.get_default_packages() + (packages or [])
            install_stdout = ""
            install_stderr = ""

            if all_packages:
                install_cmd = self.get_install_command(all_packages)
                logger.info(f"Installing packages: {all_packages}")
                execution_logs.append("\n[PACKAGE INSTALLATION]")
                execution_logs.append(f"Command: {install_cmd}")
                execution_logs.append(f"Requested packages: {all_packages}")
                execution_logs.append("-" * 60)

                exit_code, stdout, stderr = await self.container_manager.exec_command(
                    container, install_cmd
                )
                install_stdout = stdout.decode("utf-8", errors="replace")
                install_stderr = stderr.decode("utf-8", errors="replace")

                execution_logs.append(install_stdout)
                if install_stderr:
                    execution_logs.append(f"\n[STDERR]\n{install_stderr}")
                execution_logs.append(f"\n[EXIT CODE: {exit_code}]")

                if exit_code != 0:
                    logs = "\n".join(execution_logs)
                    return ExecutionResult(
                        success=False,
                        exit_code=exit_code,
                        stdout=install_stdout,
                        stderr=install_stderr,
                        output_files=[],
                        output_data="",
                        container_logs=logs,
                        execution_time=time.time() - start_time,
                    )
            else:
                execution_logs.append("\n[PACKAGE INSTALLATION]")
                execution_logs.append("No packages to install")
                execution_logs.append("-" * 60)

            # Execute script
            exec_cmd = self.get_execution_command(container_script_path)
            logger.info(f"Executing script: {exec_cmd}")
            execution_logs.append("\n[SCRIPT EXECUTION]")
            execution_logs.append(f"Command: {exec_cmd}")
            execution_logs.append("-" * 60)

            if timeout > 0:
                exit_code, stdout, stderr = await asyncio.wait_for(
                    self.container_manager.exec_command(container, exec_cmd),
                    timeout=timeout,
                )
            else:
                exit_code, stdout, stderr = await self.container_manager.exec_command(
                    container, exec_cmd
                )

            script_stdout = stdout.decode("utf-8", errors="replace")
            script_stderr = stderr.decode("utf-8", errors="replace")

            execution_logs.append(script_stdout)
            if script_stderr:
                execution_logs.append(f"\n[STDERR]\n{script_stderr}")
            execution_logs.append(f"\n[EXIT CODE: {exit_code}]")
            execution_logs.append("=" * 60)

            # Scan workspace directory for output files and copy them to /output
            # This handles cases where scripts save files to current directory instead of /output
            # Use Python file operations (cross-platform compatible) instead of shell commands
            script_filename = f"script{self.get_script_suffix()}"
            workspace_output_files = []

            try:
                # Use Python to scan and copy files (cross-platform compatible)
                # Write Python script to a temporary file and execute it (avoids shell escaping issues)
                scan_and_copy_script = f"""import os
import shutil
from pathlib import Path

workspace_dir = Path('/workspace')
output_dir = Path('/output')
script_filename = '{script_filename}'

# Ensure output directory exists
output_dir.mkdir(parents=True, exist_ok=True)

# Scan workspace for all files (excluding script file and hidden files)
workspace_files = []
if workspace_dir.exists():
    for item in workspace_dir.iterdir():
        if item.is_file() and item.name != script_filename and not item.name.startswith('.'):
            workspace_files.append(str(item))

# Copy files to output directory
copied_files = []
for workspace_file in workspace_files:
    try:
        src = Path(workspace_file)
        dst = output_dir / src.name
        shutil.copy2(src, dst)
        copied_files.append(src.name)
        print('Copied: ' + src.name)
    except Exception as e:
        print('Error copying ' + src.name + ': ' + str(e))

# Print results for parsing
print('FOUND_FILES:' + str(len(workspace_files)))
print('COPIED_FILES:' + str(len(copied_files)))
for f in copied_files:
    print('FILE:' + f)
"""

                # Encode script as base64 and execute it (avoids all shell escaping issues)
                script_bytes = scan_and_copy_script.encode("utf-8")
                script_b64 = base64.b64encode(script_bytes).decode("ascii")
                scan_cmd = f"python3 -c \"import base64; exec(base64.b64decode('{script_b64}').decode('utf-8'))\""
                scan_exit_code, scan_stdout, scan_stderr = (
                    await self.container_manager.exec_command(container, scan_cmd)
                )

                execution_logs.append("\n[WORKSPACE SCAN & COPY]")
                execution_logs.append(f"Python scan/copy exit_code: {scan_exit_code}")

                workspace_files = []
                if scan_stdout:
                    scan_output = scan_stdout.decode("utf-8", errors="replace")
                    execution_logs.append(f"Scan output:\n{scan_output}")

                    # Parse output to get copied files
                    for line in scan_output.split("\n"):
                        line = line.strip()
                        if line.startswith("FILE:"):
                            filename = line.replace("FILE:", "").strip()
                            if filename:
                                workspace_output_files.append(filename)
                        elif line.startswith("Copied:"):
                            # Also capture from "Copied: filename" lines
                            parts = line.split(":", 1)
                            if len(parts) > 1:
                                filename = parts[1].strip()
                                if filename and filename not in workspace_output_files:
                                    workspace_output_files.append(filename)

                if scan_stderr:
                    stderr_str = scan_stderr.decode("utf-8", errors="replace").strip()
                    if stderr_str:
                        execution_logs.append(f"Scan stderr: {stderr_str}")

                logger.info(
                    f"Found and copied {len(workspace_output_files)} file(s) from workspace: {workspace_output_files}"
                )
                if workspace_output_files:
                    execution_logs.append(
                        f"✓ Successfully processed {len(workspace_output_files)} file(s): {workspace_output_files}"
                    )
                else:
                    execution_logs.append(
                        "No additional files found in workspace (script file excluded)"
                    )

                if workspace_output_files:
                    logger.info(
                        f"Found and copied {len(workspace_output_files)} output file(s) from workspace: {workspace_output_files}"
                    )
                    execution_logs.append(
                        f"Total workspace files processed: {len(workspace_output_files)}"
                    )
                else:
                    execution_logs.append(
                        "No additional files found in workspace (script file excluded)"
                    )
            except Exception as e:
                logger.warning(f"Failed to scan/copy workspace files: {e}")

            # Combine all logs
            container_logs = "\n".join(execution_logs)

            # Parse output to extract files and data
            stdout_str = script_stdout
            stderr_str = script_stderr
            output_files, output_data = OutputParser.parse_output(
                stdout_str, stderr_str, self.output_dir
            )

            # Ensure output_files is always a list (safety check)
            if not isinstance(output_files, list):
                logger.warning(f"output_files is not a list: {type(output_files)}, converting")
                output_files = list(output_files) if output_files else []

            # Log file detection results
            if output_files:
                logger.info(f"Detected {len(output_files)} output file(s): {output_files}")
            else:
                logger.debug(f"No output files detected in {self.output_dir}")

            execution_time = time.time() - start_time

            return ExecutionResult(
                success=exit_code == 0,
                exit_code=exit_code,
                stdout=stdout_str,
                stderr=stderr_str,
                output_files=output_files,  # Always a list, may be empty
                output_data=output_data,
                container_logs=container_logs,
                execution_time=execution_time,
            )

        except asyncio.TimeoutError:
            logger.error(f"Execution timed out after {timeout} seconds")
            if container:
                container_logs = await self.container_manager.get_logs(container)
            else:
                container_logs = "Container not created"
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Execution timed out after {timeout} seconds",
                output_files=[],
                output_data="",
                container_logs=container_logs,
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            if container:
                container_logs = await self.container_manager.get_logs(container)
            else:
                container_logs = f"Error: {e}"
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                output_files=[],
                output_data="",
                container_logs=container_logs,
                execution_time=time.time() - start_time,
            )
        finally:
            # Cleanup
            if container:
                await self.container_manager.remove_container(container)
            # Only clean up temp file if we created it (not if script_file was provided)
            if temp_script_file and "script_path" in locals():
                try:
                    Path(script_path).unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove temporary script file: {e}")

    @abstractmethod
    def get_script_suffix(self) -> str:
        """Get script file suffix.

        Returns:
            File suffix (e.g., '.py', '.R')
        """
        pass
