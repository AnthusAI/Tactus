"""
Control channel implementations for omnichannel control loop.

This package contains control channel plugins:
- CLI: Command-line interface for terminal control (host app pattern)
- IDE/SSE: Server-Sent Events for VSCode extension (Phase 2)
- Tactus Cloud: WebSocket API for companion app (Phase 5)
- Additional channels as needed: Slack, Teams, Email, etc.

The control loop uses a publish-subscribe pattern with namespace-based routing:
- Publishers (Tactus runtimes) emit control requests to namespaces
- Subscribers (controllers) subscribe to namespace patterns
- Subscribers can be observers (read-only) or responders (can provide input)
"""

from typing import Any, Optional
import logging
import sys

from tactus.protocols.control import ControlChannel, ControlLoopConfig

logger = logging.getLogger(__name__)


# Channel registry for lazy loading
_CHANNEL_LOADERS = {
    "cli": "tactus.adapters.channels.cli:CLIControlChannel",
    "ipc": "tactus.adapters.channels.ipc:IPCControlChannel",
    # "ide": "tactus.adapters.channels.ide_sse:SSEControlChannel",  # Phase 2
    # "tactus_cloud": "tactus.adapters.channels.tactus_cloud:TactusCloudChannel",  # Phase 5
}


def load_channel(channel_id: str, config: dict[str, Any]) -> Optional[ControlChannel]:
    """
    Load a control channel by ID.

    Args:
        channel_id: Channel identifier (e.g., 'cli', 'ide', 'tactus_cloud')
        config: Channel configuration dict

    Returns:
        ControlChannel instance or None if loading fails
    """
    if channel_id not in _CHANNEL_LOADERS:
        logger.warning("Unknown or not yet implemented channel: %s", channel_id)
        return None

    module_path = _CHANNEL_LOADERS[channel_id]
    module_name, class_name = module_path.rsplit(":", 1)

    try:
        import importlib

        module = importlib.import_module(module_name)
        channel_class = getattr(module, class_name)
        return channel_class(**config)
    except ImportError as error:
        logger.warning(
            "Failed to load %s channel. Ensure dependencies are installed. Error: %s",
            channel_id,
            error,
        )
        return None
    except Exception as error:
        logger.exception("Failed to initialize %s channel: %s", channel_id, error)
        return None


def load_channels_from_config(
    config: Optional[ControlLoopConfig] = None,
) -> list[ControlChannel]:
    """
    Load control channels based on configuration and context.

    By default:
    - CLI channel is enabled if stdin is a tty (interactive terminal)
    - Other channels are loaded based on configuration

    Args:
        config: Optional control loop configuration

    Returns:
        List of enabled ControlChannel instances
    """
    channels: list[ControlChannel] = []

    if config is None:
        config = ControlLoopConfig()

    # Process each configured channel
    for channel_id, channel_config in config.channels.items():
        enabled = channel_config.get("enabled", False)

        # Special handling for CLI with auto-detection
        if channel_id == "cli":
            if enabled == "auto" or enabled is None:
                enabled = sys.stdin.isatty()
            elif isinstance(enabled, str):
                enabled = enabled.lower() == "true"

        if not enabled:
            continue

        # Remove 'enabled' from config before passing to constructor
        init_config = {key: value for key, value in channel_config.items() if key != "enabled"}
        channel = load_channel(channel_id, init_config)
        if channel:
            channels.append(channel)
            logger.info("Loaded control channel: %s", channel_id)

    # If no channels configured, use defaults
    if not config.channels:
        channels = load_default_channels()

    return channels


def load_default_channels(procedure_id: Optional[str] = None) -> list[ControlChannel]:
    """
    Load default control channels based on context.

    By default:
    - CLI channel is enabled if stdin is a tty (interactive terminal)
    - IPC channel is always enabled (allows control CLI to connect)

    Args:
        procedure_id: Optional procedure ID for IPC socket path

    Returns:
        List of enabled ControlChannel instances
    """
    channels: list[ControlChannel] = []

    # CLI channel - auto-detect based on tty
    if sys.stdin.isatty():
        from tactus.adapters.channels.cli import CLIControlChannel

        channels.append(CLIControlChannel())
        logger.info("Loaded CLI control channel (auto-detected tty)")

    # IPC channel - always enabled for control CLI connectivity
    from tactus.adapters.channels.ipc import IPCControlChannel

    channels.append(IPCControlChannel(procedure_id=procedure_id))
    logger.info("Loaded IPC control channel")

    return channels


__all__ = [
    "load_channel",
    "load_channels_from_config",
    "load_default_channels",
]
