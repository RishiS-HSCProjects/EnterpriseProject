import os
from enum import Enum, auto
from discord_webhook import DiscordWebhook
from flask import current_app

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
    embeds: list[dict] | None = None,
    timeout: int = 10,
) -> bool:
    """Send a message to a Discord webhook channel.

    Returns True on success, otherwise False.
    """
    if not location.url:
        current_app.logger.error(f"{location.name.upper} is not set. Cannot send message to webhook.")
        return False

    if content is None:
        current_app.logger.warning("No content provided to Discord webhook send()")
        return False

    message_content = content
    if header:
        message_content = f"{header}\n{message_content}"

    try:
        webhook = DiscordWebhook(
            url=location.url,
            username=username,
            content=message_content,
            timeout=timeout,
        )

        if embeds:
            for embed in embeds:
                webhook.add_embed(embed)

        response = webhook.execute()
        return response.status_code in (200, 204)
    except Exception as exc:
        current_app.logger.exception("error sending message to Discord webhook: %s", exc)
        return False
