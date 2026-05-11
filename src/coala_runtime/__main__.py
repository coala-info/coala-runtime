"""Entry point for running the MCP server."""

import argparse
import os
import sys

from coala_runtime.runtime.engine import ContainerEngine
from coala_runtime.runtime.docker_images import ensure_images
from coala_runtime.server import mcp

_ENGINE_CHOICES = ", ".join(e.value for e in ContainerEngine)

_HELP = f"""\
usage: coala-runtime [--build] [--engine {{{_ENGINE_CHOICES}}}]

Run the Coala Runtime MCP server over stdio (tools: coala_python_executor, coala_r_executor).

  --build          Build executor Docker images from the repo (requires clone + docker/;
                   skipped for singularity/apptainer — see MCP_CONFIG.md)

  --engine NAME    Container runtime: overrides COALA_CONTAINER_ENGINE for this process.
                   If neither is set, the server auto-detects (Docker if the daemon works,
                   else Podman, else Apptainer/Singularity on PATH — typical on HPC).
                   Explicit values: docker | podman | singularity | apptainer.
                   Same effect as: export COALA_CONTAINER_ENGINE=NAME

Configure an MCP client (e.g. Cursor ~/.cursor/mcp.json), replace cwd with your repo path:

  "mcpServers": {{
    "coala-runtime": {{
      "command": "coala-runtime",
      "args": ["--engine", "podman"],
      "cwd": "/path/to/coala-runtime"
    }}
  }}

With uv (no global install):

  "command": "uv",
  "args": ["run", "--directory", "/path/to/coala-runtime", "coala-runtime", "--engine", "singularity"]

More options: MCP_CONFIG.md in the coala-runtime repository.
"""

# Shown on every start (stderr only; stdout is reserved for MCP JSON-RPC).
_MCP_START_HINT = """\
Coala Runtime MCP (stdio). Client config: use "command": "coala-runtime", "args": [], "cwd": "<repo>".
Optional: --engine or COALA_CONTAINER_ENGINE; if unset, Docker/Podman/Apptainer are auto-detected. Details: MCP_CONFIG.md.
"""


def parse_coala_runtime_argv(argv: list[str]) -> tuple[bool, str | None, list[str]]:
    """Parse ``--build`` / ``--engine``; return ``(build, engine or None, argv for MCP)``."""
    prog = argv[0] if argv else "coala-runtime"
    parser = argparse.ArgumentParser(prog=prog, add_help=False)
    parser.add_argument("--build", action="store_true")
    parser.add_argument(
        "--engine",
        choices=[e.value for e in ContainerEngine],
        metavar="NAME",
        help=argparse.SUPPRESS,
    )
    ns, rest = parser.parse_known_args(argv[1:])
    return ns.build, ns.engine, [prog] + rest


def main() -> None:
    """Run the MCP server (used by the coala-runtime console script)."""
    if "-h" in sys.argv or "--help" in sys.argv:
        print(_HELP, end="", file=sys.stdout)
        raise SystemExit(0)

    build, engine, filtered_argv = parse_coala_runtime_argv(sys.argv)

    sys.argv = filtered_argv

    if engine is not None:
        os.environ["COALA_CONTAINER_ENGINE"] = engine

    print(_MCP_START_HINT, file=sys.stderr, flush=True)
    ensure_images(build=build)
    mcp.run()


if __name__ == "__main__":
    main()
