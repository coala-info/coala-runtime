"""Entry point for running the MCP server."""

import sys

from coala_runtime.server import mcp
from coala_runtime.runtime.docker_images import ensure_images


def main() -> None:
    """Run the MCP server (used by the coala-runtime console script)."""
    build = "--build" in sys.argv
    if build:
        sys.argv = [a for a in sys.argv if a != "--build"]
    ensure_images(build=build)
    mcp.run()


if __name__ == "__main__":
    main()
