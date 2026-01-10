"""
Docker sandbox module for Tactus.

Provides container-based isolation for procedure execution, protecting
the host system from potentially unsafe agent tool operations.

Usage:
    from tactus.sandbox import (
        is_docker_available,
        SandboxConfig,
        ContainerRunner,
        SandboxError,
        SandboxUnavailableError,
    )

    # Check if Docker is available
    available, reason = is_docker_available()

    # Configure sandbox
    config = SandboxConfig(enabled=True)

    # Run procedure in sandbox
    runner = ContainerRunner(config)
    result = await runner.run(source, params)
"""

from .config import SandboxConfig, SandboxLimits, get_default_sandbox_config
from .docker_manager import (
    DockerManager,
    is_docker_available,
    DEFAULT_IMAGE_NAME,
    DEFAULT_IMAGE_TAG,
)
from .container_runner import (
    ContainerRunner,
    SandboxError,
    SandboxUnavailableError,
)
from .protocol import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)

__all__ = [
    # Config
    "SandboxConfig",
    "SandboxLimits",
    "get_default_sandbox_config",
    # Docker management
    "DockerManager",
    "is_docker_available",
    "DEFAULT_IMAGE_NAME",
    "DEFAULT_IMAGE_TAG",
    # Container execution
    "ContainerRunner",
    "SandboxError",
    "SandboxUnavailableError",
    # Protocol
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionStatus",
]
