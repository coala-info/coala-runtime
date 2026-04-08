"""Entry point for running the MCP server."""

import sys

from coala_runtime.server import mcp
from coala_runtime.runtime.docker_images import ensure_images

_HELP = """\
usage: coala-runtime [--build]

Run the Coala Runtime MCP server over stdio (tools: coala_python_executor, coala_r_executor).

  --build    Build executor Docker images from the repo (requires clone + docker/)

Configure an MCP client (e.g. Cursor ~/.cursor/mcp.json), replace cwd with your repo path:

  "mcpServers": {
    "coala-runtime": {
      "command": "coala-runtime",
      "args": [],
      "cwd": "/path/to/coala-runtime"
    }
  }

With uv (no global install):

  "command": "uv",
  "args": ["run", "--directory", "/path/to/coala-runtime", "coala-runtime"]

More options: MCP_CONFIG.md in the coala-runtime repository.
"""

# Shown on every start (stderr only; stdout is reserved for MCP JSON-RPC).
_MCP_START_HINT = """\
Coala Runtime MCP (stdio). Client config: use "command": "coala-runtime", "args": [], "cwd": "<repo>".
Alternatives: python -m coala_runtime, or uv run --directory <repo> coala-runtime. Details: MCP_CONFIG.md.
"""


def main() -> None:
    """Run the MCP server (used by the coala-runtime console script)."""
    if "-h" in sys.argv or "--help" in sys.argv:
        print(_HELP, end="", file=sys.stdout)
        raise SystemExit(0)

    build = "--build" in sys.argv
    if build:
        sys.argv = [a for a in sys.argv if a != "--build"]

    print(_MCP_START_HINT, file=sys.stderr, flush=True)
    ensure_images(build=build)
    mcp.run()


if __name__ == "__main__":
    main()
