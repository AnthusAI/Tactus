"""
Sandbox configuration model for Docker-based isolation.

Defines the SandboxConfig Pydantic model for controlling container execution.
"""

from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


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
    # - enabled=None (default): Sandbox REQUIRED, error if Docker unavailable
    # - enabled=True: Sandbox REQUIRED, error if Docker unavailable
    # - enabled=False: Sandbox explicitly disabled (security risk acknowledged)
    enabled: Optional[bool] = Field(
        default=None,
        description="Enable sandbox mode. None/True=required (error if unavailable), False=disabled",
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
    env: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional environment variables to pass to the container",
    )

    # Additional volume mounts
    volumes: List[str] = Field(
        default_factory=list,
        description="Additional volume mounts in 'host:container:mode' format",
    )

    # Network mode
    network: str = Field(
        default="bridge",
        description="Docker network mode (bridge allows outbound, none blocks all)",
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
            This is True unless the user explicitly disabled sandbox.
        """
        return not self.is_explicitly_disabled()

    model_config = {"arbitrary_types_allowed": True}


def get_default_sandbox_config() -> SandboxConfig:
    """Get the default sandbox configuration."""
    return SandboxConfig()
