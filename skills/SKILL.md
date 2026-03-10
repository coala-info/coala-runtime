---
name: coala-runtime
description: How to run Python and R scripts via the Coala Runtime MCP server. Use when the user or the agent needs to execute Python or R code in containerized environments—e.g. "run this Python script", "execute R to plot data", "run analysis with pandas", "use Bioconductor in R". Covers the coala_python_executor and coala_r_executor MCP tools, package installation, file mounting, and output handling.
---

# Coala Runtime – Python and R Script Execution

This skill describes how to use the Coala Runtime MCP server to execute Python and R scripts in isolated Docker containers.

## Prerequisites

- **Coala Runtime** MCP server configured and running (see project `MCP_CONFIG.md`).
- **Docker** installed and running. Images are pulled from Docker Hub by default (`hubentu/coala-runtime-python:latest`, `hubentu/coala-runtime-r:latest`) or built locally with `coala-runtime --build` or `./docker/build.sh`.

## Configuring the MCP server

Install from project root: `uv pip install -e .` and `./docker/build.sh`. Add to your MCP config (e.g. Cursor: `~/.cursor/mcp.json`):

```json
"mcpServers": {
  "coala-runtime": {
    "command": "coala-runtime",
    "args": [],
    "cwd": "/path/to/coala-runtime"
  }
}
```

Replace `/path/to/coala-runtime` with the real path. Restart the client; tools `coala_python_executor` and `coala_r_executor` should appear. More options: `MCP_CONFIG.md`.

## Tools

| Tool | Use for |
|------|--------|
| `coala_python_executor` | Python scripts (uv for packages; image includes numpy, pandas, matplotlib). |
| `coala_r_executor` | R scripts (CRAN + Bioconductor via `bioc::package_name`; image includes tidyverse). |

Use **one** of `script` (code string) or `script_file` (host path to script). Prefer `script_file` when the script is long or has encoding/special characters to avoid serialization issues.

## Parameters (both tools)

- **script** (optional): Script source as string. Omit if using `script_file`.
- **script_file** (optional): Absolute or relative path to script on host. Omit if using `script`.
- **packages** (optional): Extra packages to install before running. See language-specific rules below.
- **input_files** (optional): Map **container path → host path** for bind-mounting. Example: `{"/input/data.csv": "/path/on/host/data.csv"}`. Scripts read from the container path (e.g. `/input/data.csv`).
- **timeout** (optional): Seconds (default 300, max 3600, 0 = no limit).

## Python: `coala_python_executor`

- **Pre-installed:** numpy, pandas, matplotlib (do not reinstall).
- **packages:** List of names; version specifiers allowed, e.g. `["scikit-learn", "requests>=2.31.0"]`. Installed with `uv pip install --system`.
- **Execution:** Script runs in container as `python /workspace/script.py`; working directory is `/workspace`.

Example (conceptual):

```json
{
  "script": "import pandas as pd; df = pd.read_csv('/input/data.csv'); print(df.head())",
  "packages": ["scikit-learn"],
  "input_files": { "/input/data.csv": "/absolute/host/path/data.csv" },
  "timeout": 120
}
```

## R: `coala_r_executor`

- **Pre-installed:** tidyverse (do not reinstall).
- **packages:** CRAN packages as names; Bioconductor as `"bioc::PackageName"`, e.g. `["ggplot2", "dplyr", "bioc::Biobase", "bioc::limma"]`.
- **Execution:** Script runs as `Rscript /workspace/script.R`; working directory is `/workspace`.

Example (conceptual):

```json
{
  "script": "library(ggplot2); data(mpg); print(head(mpg))",
  "packages": ["ggplot2", "bioc::Biobase"],
  "input_files": { "/input/data.csv": "/absolute/host/path/data.csv" },
  "timeout": 120
}
```

## Paths inside the container

| Path | Purpose |
|------|--------|
| `/workspace` | Working directory; script runs here. Script file is e.g. `/workspace/script.py` or `/workspace/script.R`. |
| `/input/<name>` | Use for input data: mount via `input_files` so the script reads from these paths. |
| `/output` | Output directory. Files written here (or to the current directory; workspace outputs are copied to `/output`) are returned as `output_files` on the host. |

- **Input:** Always use the **container** path in the script (e.g. `pd.read_csv('/input/data.csv')` or `read.csv('/input/data.csv')`). The host path is only used in `input_files`.
- **Output:** Prefer writing plots/data to `/output/` or the current directory so they are collected. Supported formats (e.g. png, pdf, csv, json) are detected and listed in the result.

## Result shape (both tools)

- **success**: boolean
- **exit_code**: 0 = success
- **stdout**, **stderr**: script output
- **output_files**: list of host paths of generated files (images, CSVs, etc.)
- **output_data**: echoed text/numeric output when no output files are found
- **container_logs**: full log (package install + script run)
- **execution_time**: seconds

## Error handling

- **Docker errors:** Ensure Docker is running (`docker ps`).
- **Image missing:** Build images with `coala-runtime --build` or `./docker/build.sh`.
- **Missing package:** Add the required package(s) to the `packages` parameter (e.g. `ModuleNotFoundError` in Python or "there is no package called 'X'" in R).
- **Timeout:** Increase `timeout` or simplify the script.
- **Script/encoding issues:** Prefer `script_file` with a path to a saved script instead of passing long or complex `script` strings.
