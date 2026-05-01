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
            raise TypeError("Webhook URL Type does not exist.")

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
    except TypeError as exc:
        flash("An error occurred while sending the message to Discord. Please try again later.", "error")
        current_app.logger.error("Invalid webhook URL type provided: %s", exc)
        return False
    except Exception as exc:
        flash("An error occurred while sending the message to Discord. Please try again later.", "error")
        current_app.logger.exception("error sending message to Discord webhook: %s", exc)
        return False
