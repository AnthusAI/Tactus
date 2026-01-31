"""
Sandbox configuration model for Docker-based isolation.

Defines the SandboxConfig Pydantic model for controlling container execution.
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class SandboxLimits(BaseModel):
    """Resource limits for the sandbox container."""

    memory: str = Field(default="2g", description="Memory limit (e.g., '2g', '512m')")
    cpus: str = Field(default="2", description="CPU limit (e.g., '2', '0.5')")


class SandboxConfig(BaseModel):
    """
    Configuration for Docker sandbox execution.

    Controls whether and how procedures run in isolated Docker containers.
    """

    # Core settings
    # Security model:
    # - enabled=None (default): Sandbox AUTO (use if available; otherwise run without isolation)
    # - enabled=True: Sandbox REQUIRED, error if Docker unavailable
    # - enabled=False: Sandbox explicitly disabled (security risk acknowledged)
    enabled: Optional[bool] = Field(
        default=None,
        description="Enable sandbox mode. None=auto, True=required, False=disabled",
    )

    # Docker image settings
    image: str = Field(
        default="tactus-sandbox:local",
        description="Docker image to use for sandbox execution",
    )

    # MCP server settings
    mcp_servers_path: str = Field(
        default="~/.tactus/mcp-servers",
        description="Path to directory containing MCP server code and dependencies",
    )

    # Additional environment variables to pass to container
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Additional environment variables to pass to the container",
    )

    # Volume mount settings
    mount_current_dir: bool = Field(
        default=True,
        description="Mount current directory to /workspace:rw by default. Set false to disable.",
    )

    # Additional volume mounts
    volumes: list[str] = Field(
        default_factory=list,
        description="Additional volume mounts in 'host:container:mode' format",
    )

    # Network mode
    network: str = Field(
        default="bridge",
        description="Docker network mode (bridge for broker access, none blocks all network)",
    )

    # Broker transport (how the secretless runtime reaches the host broker)
    # - tcp: Standard mode using TCP sockets (works locally and in K8s/cloud)
    # - tls: TCP with TLS encryption (for production deployments)
    # - stdio: Legacy mode using stdin/stdout (deprecated due to buffering issues)
    broker_transport: str = Field(
        default="tcp",
        description="Broker transport for the runtime container: tcp, tls, or stdio (deprecated)",
    )
    broker_host: str = Field(
        default="host.docker.internal",
        description="Broker hostname for tcp/tls (as seen from inside the container)",
    )
    broker_bind_host: str = Field(
        default="0.0.0.0",
        description="Bind address for the host-side broker server in tcp/tls modes",
    )
    broker_port: int = Field(
        default=0,
        description="Port for the host-side broker server in tcp/tls modes (0=auto)",
    )
    broker_tls_cert_file: Optional[str] = Field(
        default=None,
        description="TLS certificate file for broker (PEM). Required when broker_transport='tls'",
    )
    broker_tls_key_file: Optional[str] = Field(
        default=None,
        description="TLS private key file for broker (PEM). Required when broker_transport='tls'",
    )

    # Resource limits
    limits: SandboxLimits = Field(
        default_factory=SandboxLimits,
        description="Resource limits for the container",
    )

    # Timeout for container execution (seconds)
    timeout: int = Field(
        default=3600,
        description="Maximum execution time in seconds before container is killed",
    )

    # Development mode: mount live Tactus source code
    dev_mode: bool = Field(
        default=False,
        description="Enable development mode: mount live Tactus source code instead of using baked-in version",
    )

    def get_mcp_servers_path(self) -> Path:
        """Get the expanded MCP servers path."""
        return Path(self.mcp_servers_path).expanduser()

    def is_explicitly_disabled(self) -> bool:
        """
        Check if sandbox has been explicitly disabled by the user.

        Returns:
            True if user set enabled=False (acknowledging security risk).
        """
        return self.enabled is False

    def should_use_sandbox(self, docker_available: bool) -> bool:
        """
        Determine if sandbox should be used for execution.

        Args:
            docker_available: Whether Docker is available and running.

        Returns:
            True if sandbox should be used.
        """
        if self.is_explicitly_disabled():
            return False
        return docker_available

    def should_error_if_unavailable(self) -> bool:
        """
        Determine if we should error when Docker is unavailable.

        Returns:
            True if Docker unavailability should be a fatal error.
            This is True only when the user explicitly requires the sandbox (enabled=True).
        """
        return self.enabled is True

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def add_default_volumes(self) -> "SandboxConfig":
        """Add default volume mounts based on config flags."""
        if self.mount_current_dir:
            # Insert at beginning so user volumes can override
            if ".:/workspace:rw" not in self.volumes:
                self.volumes.insert(0, ".:/workspace:rw")
        return self


def get_default_sandbox_config() -> SandboxConfig:
    """Get the default sandbox configuration."""
    return SandboxConfig()
