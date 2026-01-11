# Tactus Sandbox Container
#
# This Dockerfile creates an isolated environment for running Tactus procedures
# securely. The container includes all necessary runtimes for Tactus and MCP servers.
#
# Build: docker build -t tactus-sandbox:local -f tactus/docker/Dockerfile .
# Run: docker run -i --rm tactus-sandbox:local

FROM python:3.11-slim

# Labels for image management
ARG TACTUS_VERSION=dev
LABEL tactus.version="${TACTUS_VERSION}"
LABEL maintainer="Anthus <info@anthus.ai>"
LABEL description="Tactus sandbox container for secure procedure execution"

# Install system dependencies
# - Node.js for JavaScript/TypeScript MCP servers
# - git for any git operations
# - build-essential for native Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -s /bin/bash tactus
WORKDIR /app

# Copy package files first (for better caching)
COPY pyproject.toml ./
COPY README.md ./
COPY tactus/ ./tactus/

# Ensure the non-root runtime user can read the codebase even if the host
# working tree has restrictive permissions (e.g., umask 077).
RUN chmod -R a+rX /app/tactus

# Install Tactus and its dependencies
RUN pip install --no-cache-dir -e .

# Create workspace and mcp-servers directories
RUN mkdir -p /workspace /mcp-servers && \
    chown -R tactus:tactus /workspace /mcp-servers

# Copy entrypoint script
COPY tactus/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch to non-root user
USER tactus

# Set working directory for procedure execution
WORKDIR /workspace

# Default entrypoint runs the sandbox entrypoint module
ENTRYPOINT ["/entrypoint.sh"]
