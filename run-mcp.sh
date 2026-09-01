#!/bin/sh
# OpenOSINT MCP server launcher.
# Prepends the venv bin dir to PATH so the wrapped binaries (holehe, sherlock,
# sublist3r) are resolvable by the subprocess-based tools, then execs the server.
DIR=$(cd "$(dirname "$0")" && pwd)
PATH="$DIR/.venv/bin:$PATH"
export PATH
cd "$DIR" || exit 1
exec "$DIR/.venv/bin/python" -m openosint.mcp_server
