# Docker Images for Coala Runtime

This directory contains Dockerfiles for building the Python and R executor images used by the Coala Runtime MCP server.

## Building the Images

### Quick Build (Both Images)

Use the provided build script. It auto-detects your CPU (`linux/arm64` on Apple Silicon, `linux/amd64` on Intel/AMD):

```bash
./docker/build.sh
```

**macOS (Apple Silicon):** builds a native `linux/arm64` image by default — no Rosetta emulation when running containers locally.

**Publish multi-arch images** (amd64 + arm64) to Docker Hub:

```bash
export COALA_DOCKER_PLATFORMS=linux/amd64,linux/arm64
export COALA_DOCKER_PUSH=1
export COALA_DOCKER_PYTHON_IMAGE=coala-runtime-python:latest
export COALA_DOCKER_R_IMAGE=coala-runtime-r:latest
docker login
./docker/build.sh
```

Environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `COALA_DOCKER_PLATFORM` | auto (`linux/arm64` or `linux/amd64`) | Single platform for local build |
| `COALA_DOCKER_PLATFORMS` | same as platform | Comma-separated list for multi-arch |
| `COALA_DOCKER_PUSH` | `0` | Set to `1` with multi-platform buildx to `--push` |
| `COALA_DOCKER_PYTHON_IMAGE` | `coala-runtime-python:latest` | Tag for Python image |
| `COALA_DOCKER_R_IMAGE` | `coala-runtime-r:latest` | Tag for R image |
| `COALA_DOCKER_BUILDX_BUILDER` | `coala-runtime-builder` | buildx builder name |

### Manual Build

#### Python Executor Image

Build the Python image with uv and default packages (add `--platform linux/arm64` on Apple Silicon if not using `build.sh`):

```bash
docker build --platform linux/arm64 -f docker/Dockerfile.python -t coala-runtime-python:latest .
```

#### R Executor Image

Build the R image on [bioconductor/bioconductor_docker](https://hub.docker.com/r/bioconductor/bioconductor_docker/tags) (default tag `RELEASE_3_23`):

```bash
docker build -f docker/Dockerfile.r -t coala-runtime-r:latest .
```

Other Bioconductor releases:

```bash
docker build --build-arg BIOC_DOCKER_TAG=RELEASE_3_22 -f docker/Dockerfile.r -t coala-runtime-r:3.22 .
```

## Image Details

### Python Image (`coala-runtime-python`)

- **Base**: `python:3.12-slim` (multi-arch: amd64, arm64)
- **Package Manager**: `uv` (installed from official installer)
- **Default Packages**: numpy, pandas, matplotlib
- **Directories**: `/workspace`, `/input`, `/output`

### R Image (`coala-runtime-r`)

- **Base**: `bioconductor/bioconductor_docker:RELEASE_3_23` (multi-arch: amd64, arm64)
- **Package Manager**: `BiocManager::install()` for CRAN and Bioconductor packages at runtime (binary installs)
- **Default Package**: tidyverse (installed in Dockerfile)
- **Directories**: `/workspace`, `/input`, `/output`

## Usage

These images are automatically used by the Coala Runtime MCP server when executing Python or R scripts. The images are designed to:

1. Have default packages pre-installed for faster execution
2. Support additional package installation at runtime
3. Provide bind-mount support for input/output files
4. Work seamlessly with the container manager

## Notes

- The Python image uses `uv pip install --system` to install packages system-wide
- The R image uses the Bioconductor project's Docker stack; extra packages install via R at runtime
- Both images are optimized for containerized script execution with minimal overhead
