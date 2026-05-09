# MCP Server Configuration

This document explains how to configure the Coala Runtime MCP server in various MCP client applications.

## Prerequisites

1. **Container runtime**: Docker (default), **Podman** (Docker-compatible API), or **Singularity / Apptainer** for `docker://` images.

   Select at startup with environment variable or CLI flag:

   ```bash
   export COALA_CONTAINER_ENGINE=podman      # or docker | singularity | apptainer
   ```

   Or pass **`--engine NAME`** on `coala-runtime` (overrides the env var for that process), e.g. `"args": ["--engine", "podman"]` in MCP config.

   - **Podman**: docker-py talks to the Podman socket. Set `DOCKER_HOST` if needed (e.g. `unix:///run/user/$UID/podman/podman.sock`).
   - **Singularity / Apptainer**: uses the CLI (`singularity` or `apptainer`). Images such as `hubentu/coala-runtime-python:latest` are run as `docker://...`. Proactive image pull at server start is skipped; the first execution pulls/caches the image.

2. Build the Docker images (Docker/Podman only; skip if using Singularity with registry images only):
   ```bash
   ./docker/build.sh
   ```

3. Install the Python package:
   ```bash
   uv pip install -e .
   # or
   pip install -e .
   ```

## Configuration Examples

### Cursor IDE

Add the following to your Cursor settings (usually in `~/.cursor/mcp.json` or via Settings → MCP).

With the package installed, you can run the `coala-runtime` command:

```json
{
  "mcpServers": {
    "coala-runtime": {
      "command": "coala-runtime",
      "args": [],
      "cwd": "/path/to/coala-runtime"
    }
  }
}
```

Or with `uv run` from the project directory:

```json
{
  "mcpServers": {
    "coala-runtime": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/coala-runtime",
        "coala-runtime"
      ]
    }
  }
}
```

Or with `python -m`:

```json
{
  "mcpServers": {
    "coala-runtime": {
      "command": "python",
      "args": ["-m", "coala_runtime"],
      "cwd": "/path/to/coala-runtime"
    }
  }
}
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/.config/Claude/claude_desktop_config.json` (Linux):

```json
{
  "mcpServers": {
    "coala-runtime": {
      "command": "coala-runtime",
      "args": []
    }
  }
}
```

### Generic MCP Client (via stdio)

The server uses stdio transport, so it can be configured in any MCP client that supports stdio servers:

```json
{
  "mcpServers": {
    "coala-runtime": {
      "command": "coala-runtime",
      "args": []
    }
  }
}
```

## Using with uv

If you're using `uv` for Python management, you can use:

```json
{
  "mcpServers": {
    "coala-runtime": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/coala-runtime",
        "coala-runtime"
      ]
    }
  }
}
```

## Environment Variables

You can optionally set environment variables for the server:

```json
{
  "mcpServers": {
    "coala-runtime": {
      "command": "coala-runtime",
      "args": [],
      "env": {
        "COALA_CONTAINER_ENGINE": "podman",
        "DOCKER_HOST": "unix:///run/user/1000/podman/podman.sock",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## Verification

After configuring, restart your MCP client. The server should appear in the available tools list. You can verify by:

1. Checking the MCP server logs in your client
2. Listing available tools - you should see:
   - `coala_python_executor`
   - `coala_r_executor`

## Troubleshooting

### Docker / Podman socket or daemon errors

Ensure the container API is reachable (`docker ps`, or Podman's Docker-compatible socket if using `COALA_CONTAINER_ENGINE=podman`).

### Singularity / Apptainer

Use `COALA_CONTAINER_ENGINE=singularity` or `apptainer`. The CLI must be on `PATH`. Images pull or cache on first execution (`docker://` URIs).

### Docker not found (remote Docker hosts only)

If Docker runs elsewhere, set `DOCKER_HOST` accordingly. Locally:
```bash
docker ps
```

### Module not found
Make sure the package is installed:
```bash
cd /path/to/coala-runtime
uv pip install -e .
```

### Permission issues
Ensure the user running the MCP client has permission to:
- Access the container socket (Docker or Podman)
- Read/write to the workspace directory

## Testing the Server

You can test the server directly:

```bash
cd /path/to/coala-runtime
coala-runtime
```

The server will communicate via stdio, so you won't see output unless you send MCP protocol messages.
