# MCP Server Configuration

This document explains how to configure the Coala Runtime MCP server in various MCP client applications.

## Prerequisites

1. Build the Docker images:
   ```bash
   ./docker/build.sh
   ```

2. Install the Python package:
   ```bash
   uv pip install -e .
   # or
   pip install -e .
   ```

## Configuration Examples

### Cursor IDE

Add the following to your Cursor settings (usually in `~/.cursor/mcp.json` or via Settings → MCP):

```json
{
  "mcpServers": {
    "coala-runtime": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "-m",
        "coala_runtime"
      ],
      "cwd": "/home/qhu/Workspace/coala_runtime"
    }
  }
}
```

Or if using `python` directly:

```json
{
  "mcpServers": {
    "coala-runtime": {
      "command": "python",
      "args": [
        "-m",
        "coala_runtime"
      ],
      "cwd": "/home/qhu/Workspace/coala_runtime"
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
      "command": "python",
      "args": [
        "-m",
        "coala_runtime"
      ],
      "cwd": "/home/qhu/Workspace/coala_runtime"
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
      "command": "python",
      "args": ["-m", "coala_runtime"],
      "env": {
        "PYTHONPATH": "/home/qhu/Workspace/coala_runtime/src"
      }
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
        "/home/qhu/Workspace/coala_runtime",
        "python",
        "-m",
        "coala_runtime"
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
      "command": "python",
      "args": ["-m", "coala_runtime"],
      "env": {
        "DOCKER_HOST": "unix:///var/run/docker.sock",
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

### Docker not found
Ensure Docker is running and accessible:
```bash
docker ps
```

### Module not found
Make sure the package is installed:
```bash
cd /home/qhu/Workspace/coala_runtime
uv pip install -e .
```

### Permission issues
Ensure the user running the MCP client has permission to:
- Access Docker socket
- Read/write to the workspace directory

## Testing the Server

You can test the server directly:

```bash
cd /home/qhu/Workspace/coala_runtime
python -m coala_runtime
```

The server will communicate via stdio, so you won't see output unless you send MCP protocol messages.
