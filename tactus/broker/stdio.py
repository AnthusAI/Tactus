"""
Shared constants for broker-over-stdio transport.

Docker Desktop (macOS/Windows) containers cannot connect to a host AF_UNIX socket
bind-mounted from the host OS. For sandboxed runs we therefore use a broker RPC
channel over the container process stdio.
"""

STDIO_TRANSPORT_VALUE = "stdio"

# Container → host requests are written to stderr with this prefix, followed by a JSON object.
STDIO_REQUEST_PREFIX = "<<<TACTUS_BROKER>>>"
