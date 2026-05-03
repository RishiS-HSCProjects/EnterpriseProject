import os
from enum import Enum, auto
from discord_webhook import DiscordEmbed, DiscordWebhook
from flask import current_app
from .utils import flash

class ChannelWebhookUrl(Enum):
    SECURE_WEBHOOK_URL = auto()
    ANNOUNCEMENT_WEBHOOK_URL = auto()
    
    @property
    def url(self) -> str | None:
        mapping = {
            self.SECURE_WEBHOOK_URL: "SECURE_DISCORD_WEBHOOK_URL",
            self.ANNOUNCEMENT_WEBHOOK_URL: "ANNOUNCEMENT_DISCORD_WEBHOOK_URL",
        }

        value = os.getenv(mapping[self])

        if value is None:
            raise WebhookUrlNotFound(f"Webhook URL for {self.name} not found.")

        return value

def send(
    location: ChannelWebhookUrl,
    content: str,
    username: str = "Enterprise Project Bot",
    header: str | None = None,
    embeds: list[DiscordEmbed] | None = None,
    timeout: int = 10,
) -> bool:
    """Send a message to a Discord webhook channel.

    Returns True on success, otherwise False.
    """

    if content is None:
        current_app.logger.warning("No content provided to Discord webhook send()")
        return False

    message_content = content
    if header:
        message_content = f"{header}\n{message_content}"

    try:
        webhook = DiscordWebhook(
            url=location.url, # type: ignore
            username=username,
            content=message_content,
            timeout=timeout,
        )

        if embeds:
            for embed in embeds:
                webhook.add_embed(embed)

        response = webhook.execute()
        return response.status_code in (200, 204)
    except WebhookUrlNotFound as exc:
        current_app.logger.error("Webhook URL not found: %s", exc)
        raise
    except InvalidWebhookUrlType as exc:
        current_app.logger.error("Invalid webhook URL type provided: %s", exc)
        raise
    except WebhookSendError as exc:
        current_app.logger.error("Failed to send message to Discord webhook: %s", exc)
        raise
    except Exception as exc:
        current_app.logger.exception("error sending message to Discord webhook: %s", exc)
        raise

class WebhookError(Exception):
    """Custom exception for webhook-related errors."""

class WebhookUrlNotFound(WebhookError):
    """Raised when a required webhook URL is not found in environment variables."""

class WebhookSendError(WebhookError):
    """Raised when sending a message to the webhook fails."""

class InvalidWebhookUrlType(WebhookError):
    """Raised when an invalid webhook URL type is provided."""
