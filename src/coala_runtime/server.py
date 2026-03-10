"""MCP server for Coala Runtime.

This server provides tools to execute Python and R scripts in containerized
Docker environments with support for dynamic package installation and file mounting.
"""

import ast
import json
import logging
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from mcp.server.fastmcp import FastMCP

from coala_runtime.tools.python_executor import PythonExecutor
from coala_runtime.tools.r_executor import RExecutor

# Configure logging to stderr for stdio transport (best practice)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,  # Use stderr for stdio servers
)
logger = logging.getLogger(__name__)

# Create MCP server using FastMCP
mcp = FastMCP("coala_runtime_mcp")


# Pydantic Models for Input Validation


class PythonExecutorInput(BaseModel):
    """Input model for Python executor tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    script: Optional[str] = Field(
        default=None,
        description="Python script code to execute (either script or script_file must be provided). If script parameter fails due to encoding/serialization issues, use script_file instead.",
    )
    script_file: Optional[str] = Field(
        default=None,
        description="Path to Python script file to execute (either script or script_file must be provided). Prefer using script_file when possible, especially if script parameter fails.",
    )
    packages: Optional[List[str]] = Field(
        default_factory=list,
        description="Additional Python packages to install via uv. The default image already includes numpy, pandas, matplotlib. Examples: ['scikit-learn', 'seaborn', 'requests>=2.31.0']",
    )
    input_files: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Map of container paths to host paths for bind-mounting files. Example: {'/input/data.csv': '/host/path/data.csv', '/input/config.json': '/host/path/config.json'}",
    )
    timeout: int = Field(
        default=300,
        description="Execution timeout in seconds. Use 0 for no timeout. Default: 300 seconds (5 minutes)",
        ge=0,
        le=3600,
    )

    @field_validator("script")
    @classmethod
    def validate_script(cls, v: Optional[str]) -> Optional[str]:
        """Validate script is not empty if provided."""
        if v is not None and not v.strip():
            raise ValueError("Script cannot be empty or whitespace only")
        return v.strip() if v else None

    @model_validator(mode="after")
    def validate_script_or_file(self):
        """Ensure either script or script_file is provided."""
        if not self.script and not self.script_file:
            raise ValueError("Either 'script' or 'script_file' must be provided")
        if self.script and self.script_file:
            raise ValueError("Cannot provide both 'script' and 'script_file'")
        return self


class RExecutorInput(BaseModel):
    """Input model for R executor tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    script: Optional[str] = Field(
        default=None,
        description="R script code to execute (either script or script_file must be provided). If script parameter fails due to encoding/serialization issues, use script_file instead.",
    )
    script_file: Optional[str] = Field(
        default=None,
        description="Path to R script file to execute (either script or script_file must be provided). Prefer using script_file when possible, especially if script parameter fails.",
    )
    packages: Optional[List[str]] = Field(
        default_factory=list,
        description="Additional R packages to install. Use 'bioc::package_name' format for Bioconductor packages. Default package 'tidyverse' is always included. Examples: ['ggplot2', 'dplyr', 'bioc::Biobase', 'bioc::limma']",
    )
    input_files: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Map of container paths to host paths for bind-mounting files. Example: {'/input/data.csv': '/host/path/data.csv', '/input/config.R': '/host/path/config.R'}",
    )
    timeout: int = Field(
        default=300,
        description="Execution timeout in seconds. Use 0 for no timeout. Default: 300 seconds (5 minutes)",
        ge=0,
        le=3600,
    )

    @field_validator("script")
    @classmethod
    def validate_script(cls, v: Optional[str]) -> Optional[str]:
        """Validate script is not empty if provided."""
        if v is not None and not v.strip():
            raise ValueError("Script cannot be empty or whitespace only")
        return v.strip() if v else None

    @model_validator(mode="after")
    def validate_script_or_file(self):
        """Ensure either script or script_file is provided."""
        if not self.script and not self.script_file:
            raise ValueError("Either 'script' or 'script_file' must be provided")
        if self.script and self.script_file:
            raise ValueError("Cannot provide both 'script' and 'script_file'")
        return self


# Pydantic Models for Structured Output


class ExecutionResultOutput(BaseModel):
    """Structured output model for execution results."""

    success: bool = Field(..., description="Whether execution succeeded")
    exit_code: int = Field(..., description="Process exit code (0 = success, non-zero = failure)")
    stdout: str = Field(..., description="Standard output from script execution")
    stderr: str = Field(..., description="Standard error output from script execution")
    output_files: List[str] = Field(
        default_factory=list,
        description="List of output file paths (for files/images generated by the script)",
    )
    output_data: str = Field(
        default="",
        description="Echoed output for strings/numbers (captured via print/echo statements)",
    )
    container_logs: str = Field(
        ...,
        description="Full container execution logs including package installation and script execution",
    )
    execution_time: float = Field(..., description="Execution time in seconds")


# Shared Error Handling


def _handle_execution_error(e: Exception, operation: str) -> ExecutionResultOutput:
    """Handle execution errors with actionable error messages.

    Args:
        e: Exception that occurred
        operation: Description of the operation (e.g., "Python script execution")

    Returns:
        ExecutionResultOutput with error details
    """
    error_msg = str(e)
    error_type = type(e).__name__

    # Provide actionable error messages based on error type
    if "Docker" in error_type or "docker" in error_msg.lower():
        stderr_msg = (
            f"Error: Docker operation failed during {operation}. "
            "Please ensure Docker is running and accessible. "
            "Try running 'docker ps' to verify Docker is working."
        )
    elif "timeout" in error_msg.lower() or "Timeout" in error_type:
        stderr_msg = (
            f"Error: {operation} timed out. "
            "Consider increasing the timeout parameter or optimizing your script for faster execution."
        )
    elif "image" in error_msg.lower() or "Image" in error_type:
        stderr_msg = (
            f"Error: Docker image not found during {operation}. "
            "Please ensure Docker images are built by running './docker/build.sh'."
        )
    elif "permission" in error_msg.lower() or "Permission" in error_type:
        stderr_msg = (
            f"Error: Permission denied during {operation}. "
            "Please check file permissions and Docker socket access."
        )
    else:
        stderr_msg = f"Error during {operation}: {error_msg}"

    logger.error(f"{operation} failed: {e}", exc_info=True)

    return ExecutionResultOutput(
        success=False,
        exit_code=-1,
        stdout="",
        stderr=stderr_msg,
        output_files=[],
        output_data="",
        container_logs=f"Error: {error_type}: {error_msg}",
        execution_time=0.0,
    )


# Tool Definitions


@mcp.tool(
    name="coala_python_executor",
    annotations={
        "title": "Execute Python Script",
        "readOnlyHint": False,  # Creates containers and executes code
        "destructiveHint": False,  # Runs in isolated containers, not destructive
        "idempotentHint": False,  # Each execution is independent
        "openWorldHint": True,  # Interacts with Docker and file system
    },
)
async def coala_python_executor(
    params: Union[PythonExecutorInput, dict, str],
) -> ExecutionResultOutput:
    """Execute Python scripts in a containerized environment with uv package management.

    This tool executes Python scripts in isolated Docker containers with support for:
    - Dynamic package installation using uv (faster than pip)
    - File mounting for input/output data
    - Automatic output parsing (files, images, text output)
    - Default image includes numpy, pandas, matplotlib

    Args:
        params (PythonExecutorInput): Validated input parameters containing:
            - script (str): Python script code to execute (either script or script_file must be provided).
              If script parameter fails due to encoding/serialization issues, use script_file instead.
            - script_file (str): Path to Python script file to execute (either script or script_file must be provided).
              Prefer using script_file when possible, especially if script parameter fails.
            - packages (Optional[List[str]]): Additional packages to install via uv.
              The default image already includes numpy, pandas, matplotlib.
              Can include version specifiers (e.g., 'requests>=2.31.0').
            - input_files (Optional[Dict[str, str]]): Map of container paths to host paths
              for bind-mounting files into the container.
            - timeout (int): Execution timeout in seconds (0 = no timeout, default: 300,
              max: 3600)

    Returns:
        ExecutionResultOutput: Structured result containing:
            - success (bool): Whether execution succeeded
            - exit_code (int): Process exit code (0 = success)
            - stdout (str): Standard output from script
            - stderr (str): Standard error output
            - output_files (List[str]): List of generated file paths (images, data files)
            - output_data (str): Echoed text/number output from print statements
            - container_logs (str): Full execution logs including package installation
            - execution_time (float): Execution time in seconds

    Examples:
        - Use when: "Run this Python script to analyze data" -> params with script code
        - Use when: "Create a plot with matplotlib" -> params with script and packages=['seaborn']
        - Use when: "Process this CSV file" -> params with script and input_files mapping
        - Don't use when: You need to execute R code (use coala_r_executor instead)

    Error Handling:
        - Returns ExecutionResultOutput with success=False and actionable error messages
        - Docker errors suggest checking Docker is running
        - Timeout errors suggest increasing timeout or optimizing script
        - Image errors suggest building Docker images
        - If script parameter fails (e.g., encoding issues, syntax errors in script string),
          try using script_file parameter instead by saving the script to a file first
    """
    try:
        # Handle different input formats from MCP clients
        # Handle string input (JSON or Python dict string)
        if isinstance(params, str):
            logger.debug(
                f"Received params as string, length: {len(params)}, first 200 chars: {params[:200]}"
            )
            try:
                params_dict = json.loads(params)
            except json.JSONDecodeError as json_err:
                logger.debug(f"JSON parsing failed: {json_err}, trying ast.literal_eval")
                try:
                    params_dict = ast.literal_eval(params)
                except (ValueError, SyntaxError) as ast_err:
                    logger.error(
                        f"Failed to parse params string. JSON error: {json_err}, AST error: {ast_err}"
                    )
                    logger.error(f"Params string (first 500 chars): {params[:500]}")
                    return _handle_execution_error(
                        ValueError(
                            f"Invalid parameters format. JSON error: {json_err}, AST error: {ast_err}"
                        ),
                        "Python script execution",
                    )
            if not isinstance(params_dict, dict):
                logger.error(f"Parsed params is not a dict: {type(params_dict)}")
                return _handle_execution_error(
                    ValueError(f"Parameters must be a dictionary, got {type(params_dict)}"),
                    "Python script execution",
                )
            params = PythonExecutorInput(**params_dict)
        elif isinstance(params, dict):
            # Convert dict to Pydantic model
            params = PythonExecutorInput(**params)
        elif not isinstance(params, PythonExecutorInput):
            # If params is still not a Pydantic model, it's invalid
            return _handle_execution_error(
                ValueError(f"Invalid parameters type: {type(params)}"), "Python script execution"
            )

        # Now params is a PythonExecutorInput instance
        # Always convert script string to temp file first (more reliable than passing script directly)
        temp_script_file = None
        result = None
        try:
            # If script is provided, always write it to a temp file first
            # This avoids issues with script string serialization/encoding
            if params.script:
                try:
                    # Write script to temporary file
                    temp_script_file = tempfile.NamedTemporaryFile(
                        mode="w", suffix=".py", delete=False, encoding="utf-8"
                    )
                    temp_script_file.write(params.script)
                    temp_script_file.flush()
                    temp_script_file.close()
                    script_file_path = temp_script_file.name
                    logger.info(f"Converted script string to temporary file: {script_file_path}")
                except Exception as e:
                    logger.error(f"Failed to write script to temporary file: {e}")
                    return _handle_execution_error(
                        ValueError(f"Failed to write script to temporary file: {e}"),
                        "Python script execution",
                    )
            elif params.script_file:
                script_file_path = params.script_file
                # Verify file exists
                if not Path(script_file_path).exists():
                    return _handle_execution_error(
                        ValueError(f"Script file not found: {script_file_path}"),
                        "Python script execution",
                    )
            else:
                return _handle_execution_error(
                    ValueError("Either 'script' or 'script_file' must be provided"),
                    "Python script execution",
                )

            packages = params.packages or []
            input_files = params.input_files or {}
            timeout = params.timeout

            executor = PythonExecutor()
            logger.info(
                f"Executing Python script from file: {script_file_path} (packages: {packages}, timeout: {timeout})"
            )

            # Always use script_file parameter (never pass script string directly)
            result = await executor.execute(
                script_file=script_file_path,
                packages=packages,
                input_files=input_files,
                timeout=timeout,
            )
        except Exception as e:
            # If execution fails and we have a script string, log that we tried file-based approach
            if params.script:
                logger.warning(f"Execution failed even after converting script to file: {e}")
            raise
        finally:
            # Clean up temporary script file if we created it
            # Note: executor will also clean up its own temp file if it creates one,
            # but we created this one, so we clean it up here
            if temp_script_file:
                try:
                    Path(temp_script_file.name).unlink()
                    logger.debug(f"Cleaned up temporary script file: {temp_script_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to remove temporary script file: {e}")

        # Ensure output_files is always a list
        output_files = result.output_files if isinstance(result.output_files, list) else []

        return ExecutionResultOutput(
            success=result.success,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            output_files=output_files,  # Always a list of file paths (may be empty)
            output_data=result.output_data,
            container_logs=result.container_logs,
            execution_time=result.execution_time,
        )

    except Exception as e:
        return _handle_execution_error(e, "Python script execution")


@mcp.tool(
    name="coala_r_executor",
    annotations={
        "title": "Execute R Script",
        "readOnlyHint": False,  # Creates containers and executes code
        "destructiveHint": False,  # Runs in isolated containers, not destructive
        "idempotentHint": False,  # Each execution is independent
        "openWorldHint": True,  # Interacts with Docker and file system
    },
)
async def coala_r_executor(params: Union[RExecutorInput, dict, str]) -> ExecutionResultOutput:
    """Execute R scripts in a containerized environment with r2u and BiocManager.

    This tool executes R scripts in isolated Docker containers with support for:
    - Dynamic package installation from CRAN (via r2u) and Bioconductor (via BiocManager)
    - File mounting for input/output data
    - Automatic output parsing (files, images, text output)
    - Default package: tidyverse

    Args:
        params (RExecutorInput): Validated input parameters containing:
            - script (str): R script code to execute (either script or script_file must be provided).
              If script parameter fails due to encoding/serialization issues, use script_file instead.
            - script_file (str): Path to R script file to execute (either script or script_file must be provided).
              Prefer using script_file when possible, especially if script parameter fails.
            - packages (Optional[List[str]]): Additional R packages to install.
              Use 'bioc::package_name' format for Bioconductor packages.
              Default package 'tidyverse' is always included.
              Examples: ['ggplot2', 'dplyr', 'bioc::Biobase', 'bioc::limma']
            - input_files (Optional[Dict[str, str]]): Map of container paths to host paths
              for bind-mounting files into the container.
            - timeout (int): Execution timeout in seconds (0 = no timeout, default: 300,
              max: 3600)

    Returns:
        ExecutionResultOutput: Structured result containing:
            - success (bool): Whether execution succeeded
            - exit_code (int): Process exit code (0 = success)
            - stdout (str): Standard output from script
            - stderr (str): Standard error output
            - output_files (List[str]): List of generated file paths (images, data files)
            - output_data (str): Echoed text/number output from print/cat statements
            - container_logs (str): Full execution logs including package installation
            - execution_time (float): Execution time in seconds

    Examples:
        - Use when: "Run this R script to create a visualization" -> params with script code
        - Use when: "Analyze data with ggplot2" -> params with script and packages=['ggplot2']
        - Use when: "Use Bioconductor package" -> params with script and packages=['bioc::Biobase']
        - Don't use when: You need to execute Python code (use coala_python_executor instead)

    Error Handling:
        - Returns ExecutionResultOutput with success=False and actionable error messages
        - Docker errors suggest checking Docker is running
        - Timeout errors suggest increasing timeout or optimizing script
        - Image errors suggest building Docker images
        - Package installation errors include package names and installation logs
        - If script parameter fails (e.g., encoding issues, syntax errors in script string),
          try using script_file parameter instead by saving the script to a file first
    """
    try:
        # Handle different input formats from MCP clients
        # Handle string input (JSON or Python dict string)
        if isinstance(params, str):
            try:
                params_dict = json.loads(params)
            except json.JSONDecodeError:
                try:
                    params_dict = ast.literal_eval(params)
                except (ValueError, SyntaxError) as e:
                    logger.error(f"Failed to parse params string: {e}")
                    return _handle_execution_error(
                        ValueError(f"Invalid parameters format: {e}"), "R script execution"
                    )
            params = RExecutorInput(**params_dict)
        elif isinstance(params, dict):
            # Convert dict to Pydantic model
            params = RExecutorInput(**params)
        elif not isinstance(params, RExecutorInput):
            # If params is still not a Pydantic model, it's invalid
            return _handle_execution_error(
                ValueError(f"Invalid parameters type: {type(params)}"), "R script execution"
            )

        # Now params is a RExecutorInput instance
        # Always convert script string to temp file first (more reliable than passing script directly)
        temp_script_file = None
        result = None
        try:
            # If script is provided, always write it to a temp file first
            # This avoids issues with script string serialization/encoding
            if params.script:
                try:
                    # Write script to temporary file
                    temp_script_file = tempfile.NamedTemporaryFile(
                        mode="w", suffix=".R", delete=False, encoding="utf-8"
                    )
                    temp_script_file.write(params.script)
                    temp_script_file.flush()
                    temp_script_file.close()
                    script_file_path = temp_script_file.name
                    logger.info(f"Converted script string to temporary file: {script_file_path}")
                except Exception as e:
                    logger.error(f"Failed to write script to temporary file: {e}")
                    return _handle_execution_error(
                        ValueError(f"Failed to write script to temporary file: {e}"),
                        "R script execution",
                    )
            elif params.script_file:
                script_file_path = params.script_file
                # Verify file exists
                if not Path(script_file_path).exists():
                    return _handle_execution_error(
                        ValueError(f"Script file not found: {script_file_path}"),
                        "R script execution",
                    )
            else:
                return _handle_execution_error(
                    ValueError("Either 'script' or 'script_file' must be provided"),
                    "R script execution",
                )

            packages = params.packages or []
            input_files = params.input_files or {}
            timeout = params.timeout

            executor = RExecutor()
            logger.info(
                f"Executing R script from file: {script_file_path} (packages: {packages}, timeout: {timeout})"
            )

            # Always use script_file parameter (never pass script string directly)
            result = await executor.execute(
                script_file=script_file_path,
                packages=packages,
                input_files=input_files,
                timeout=timeout,
            )
        except Exception as e:
            # If execution fails and we have a script string, log that we tried file-based approach
            if params.script:
                logger.warning(f"Execution failed even after converting script to file: {e}")
            raise
        finally:
            # Clean up temporary script file if we created it
            # Note: executor will also clean up its own temp file if it creates one,
            # but we created this one, so we clean it up here
            if temp_script_file:
                try:
                    Path(temp_script_file.name).unlink()
                    logger.debug(f"Cleaned up temporary script file: {temp_script_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to remove temporary script file: {e}")

        # Ensure output_files is always a list
        output_files = result.output_files if isinstance(result.output_files, list) else []

        return ExecutionResultOutput(
            success=result.success,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            output_files=output_files,  # Always a list of file paths (may be empty)
            output_data=result.output_data,
            container_logs=result.container_logs,
            execution_time=result.execution_time,
        )

    except Exception as e:
        return _handle_execution_error(e, "R script execution")


# Server Entry Point


if __name__ == "__main__":
    mcp.run()
