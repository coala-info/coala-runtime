"""Entry point for running the MCP server."""

import argparse
import os
import subprocess
import sys

from coala_runtime.runtime.engine import ContainerEngine
from coala_runtime.runtime.docker_images import build_executor_images, ensure_images
from coala_runtime.server import mcp

_ENGINE_CHOICES = ", ".join(e.value for e in ContainerEngine)

_HELP = f"""\
usage: coala-runtime [build] [--build] [--pull] [--engine {{{_ENGINE_CHOICES}}}]

Run the Coala Runtime MCP server over stdio (tools: coala_python_executor, coala_r_executor).

  build            Build coala-runtime-python:latest and coala-runtime-r:latest locally
                   locally (runs docker/build.sh; requires repo clone + Docker/Podman CLI)

  (default)        On start, build missing executor images locally; use --pull to fetch from
                   Docker Hub instead

  --build          Rebuild executor images, then start the MCP server (even if already present)

  --pull           Pull missing images from Docker Hub (hubentu/*), retagged locally

  --engine NAME    Container runtime: overrides COALA_CONTAINER_ENGINE for this process.
                   If neither is set, the server auto-detects (Docker if the daemon works,
                   else Podman, else Apptainer/Singularity on PATH — typical on HPC).
                   Explicit values: docker | podman | singularity | apptainer.
                   Same effect as: export COALA_CONTAINER_ENGINE=NAME

Configure an MCP client (e.g. Cursor ~/.cursor/mcp.json), replace cwd with your repo path:

  "mcpServers": {{
    "coala-runtime": {{
      "command": "coala-runtime",
      "args": [],
      "cwd": "/path/to/coala-runtime"
    }}
  }}

With uv (no global install):

  "command": "uv",
  "args": ["run", "--directory", "/path/to/coala-runtime", "coala-runtime"]

More options: MCP_CONFIG.md in the coala-runtime repository.
"""

_BUILD_HELP = """\
usage: coala-runtime build

Build coala-runtime-python:latest and coala-runtime-r:latest using docker/build.sh.

Requires:
  - coala-runtime repository (docker/Dockerfile.python) — run from repo root or set MCP cwd
  - Docker or Podman CLI (buildx for multi-arch publish)

Optional environment variables (see docker/README.md):
  COALA_DOCKER_PLATFORM, COALA_DOCKER_PLATFORMS, COALA_DOCKER_PUSH,
  COALA_DOCKER_PYTHON_IMAGE, COALA_DOCKER_R_IMAGE
"""

# Shown on every start (stderr only; stdout is reserved for MCP JSON-RPC).
_MCP_START_HINT = """\
Coala Runtime MCP (stdio). Client config: use "command": "coala-runtime", "args": [], "cwd": "<repo>".
Missing executor images are built locally on start (use --pull to fetch from Docker Hub). Details: MCP_CONFIG.md.
"""


def parse_coala_runtime_argv(
    argv: list[str],
) -> tuple[bool, bool, str | None, list[str]]:
    """Parse CLI flags; return ``(force_build, pull, engine or None, argv for MCP)``."""
    prog = argv[0] if argv else "coala-runtime"
    parser = argparse.ArgumentParser(prog=prog, add_help=False)
    parser.add_argument(
        "--build",
        action="store_true",
        help="Rebuild executor images before starting the MCP server",
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Pull missing images from Docker Hub (retagged as coala-runtime-*:latest)",
    )
    parser.add_argument(
        "--engine",
        choices=[e.value for e in ContainerEngine],
        metavar="NAME",
        help=argparse.SUPPRESS,
    )
    ns, rest = parser.parse_known_args(argv[1:])
    return ns.build, ns.pull, ns.engine, [prog] + rest


def cmd_build() -> None:
    """Build executor Docker images and exit."""
    try:
        build_executor_images()
    except FileNotFoundError as e:
        print(f"coala-runtime build: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except subprocess.CalledProcessError as e:
        raise SystemExit(e.returncode) from e


def main() -> None:
    """Run the MCP server or ``build`` subcommand (used by the coala-runtime console script)."""
    if "-h" in sys.argv or "--help" in sys.argv:
        if len(sys.argv) > 1 and sys.argv[1] == "build":
            print(_BUILD_HELP, end="", file=sys.stdout)
        else:
            print(_HELP, end="", file=sys.stdout)
        raise SystemExit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "build":
        cmd_build()
        raise SystemExit(0)

    force_build, pull, engine, filtered_argv = parse_coala_runtime_argv(sys.argv)

    sys.argv = filtered_argv

    if engine is not None:
        os.environ["COALA_CONTAINER_ENGINE"] = engine

    print(_MCP_START_HINT, file=sys.stderr, flush=True)
    ensure_images(pull=pull, force_build=force_build)
    mcp.run()


if __name__ == "__main__":
    main()
