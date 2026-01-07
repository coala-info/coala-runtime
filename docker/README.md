# Docker Images for Coala Runtime

This directory contains Dockerfiles for building the Python and R executor images used by the Coala Runtime MCP server.

## Building the Images

### Quick Build (Both Images)

Use the provided build script to build both images:

```bash
./docker/build.sh
```

### Manual Build

#### Python Executor Image

Build the Python image with uv and default packages (numpy, pandas, matplotlib):

```bash
docker build -f docker/Dockerfile.python -t coala-runtime-python:latest .
```

#### R Executor Image

Build the R image with r2u, bioc2u, and tidyverse:

```bash
docker build -f docker/Dockerfile.r -t coala-runtime-r:latest .
```

## Image Details

### Python Image (`coala-runtime-python`)

- **Base**: `python:3.12-slim`
- **Package Manager**: `uv` (installed from official installer)
- **Default Packages**: numpy, pandas, matplotlib
- **Directories**: `/workspace`, `/input`, `/output`

### R Image (`coala-runtime-r`)

- **Base**: `rocker/r2u:latest` (provides CRAN packages as Ubuntu binaries)
- **Package Managers**: 
  - `apt` via r2u for CRAN packages
  - `BiocManager` for Bioconductor packages
  - `bioc2u` repository for Bioconductor binaries
- **Default Package**: tidyverse
- **Directories**: `/workspace`, `/input`, `/output`
- **Configuration**: bspm enabled for automatic apt integration

## Usage

These images are automatically used by the Coala Runtime MCP server when executing Python or R scripts. The images are designed to:

1. Have default packages pre-installed for faster execution
2. Support additional package installation at runtime
3. Provide bind-mount support for input/output files
4. Work seamlessly with the container manager

## Notes

- The Python image uses `uv pip install --system` to install packages system-wide
- The R image uses `bspm` to automatically route `install.packages()` calls to `apt` when binaries are available
- Both images are optimized for containerized script execution with minimal overhead
