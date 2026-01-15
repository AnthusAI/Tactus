"""
Notification channel implementations for omnichannel HITL.

This package contains notification channel plugins for various platforms:
- Slack: Interactive messages with Block Kit
- Discord: Embeds with button components
- Teams: Adaptive Cards via webhooks
- Email: Fire-and-forget email notifications

Install optional dependencies to use specific channels:
    pip install tactus[slack]     # Slack support
    pip install tactus[discord]   # Discord support
    pip install tactus[email]     # Email support
    pip install tactus[notifications]  # All channels
"""

from typing import List, Dict, Any, Optional
import logging

from tactus.protocols.notification import NotificationChannel, NotificationsConfig

logger = logging.getLogger(__name__)

# Channel registry for lazy loading
_CHANNEL_LOADERS = {
    "slack": "tactus.adapters.channels.slack:SlackNotificationChannel",
    "discord": "tactus.adapters.channels.discord:DiscordNotificationChannel",
    "teams": "tactus.adapters.channels.teams:TeamsNotificationChannel",
    "email": "tactus.adapters.channels.email:EmailNotificationChannel",
}


def load_channel(channel_id: str, config: Dict[str, Any]) -> Optional[NotificationChannel]:
    """
    Load a notification channel by ID.

    Args:
        channel_id: Channel identifier (e.g., 'slack', 'discord')
        config: Channel configuration dict

    Returns:
        NotificationChannel instance or None if loading fails
    """
    if channel_id not in _CHANNEL_LOADERS:
        logger.warning(f"Unknown channel: {channel_id}")
        return None

    module_path = _CHANNEL_LOADERS[channel_id]
    module_name, class_name = module_path.rsplit(":", 1)

    try:
        import importlib

        module = importlib.import_module(module_name)
        channel_class = getattr(module, class_name)
        return channel_class(**config)
    except ImportError as e:
        logger.warning(
            f"Failed to load {channel_id} channel. "
            f"Install the required dependency: pip install tactus[{channel_id}]. "
            f"Error: {e}"
        )
        return None
    except Exception as e:
        logger.exception(f"Failed to initialize {channel_id} channel: {e}")
        return None


def load_channels_from_config(config: NotificationsConfig) -> List[NotificationChannel]:
    """
    Load all enabled channels from configuration.

    Args:
        config: NotificationsConfig with channel settings

    Returns:
        List of successfully loaded NotificationChannel instances
    """
    if not config.enabled:
        return []

    channels = []
    for channel_id, channel_config in config.channels.items():
        if not channel_config.get("enabled", False):
            continue

        channel = load_channel(channel_id, channel_config)
        if channel:
            channels.append(channel)
            logger.info(f"Loaded notification channel: {channel_id}")

    return channels


__all__ = [
    "load_channel",
    "load_channels_from_config",
]
