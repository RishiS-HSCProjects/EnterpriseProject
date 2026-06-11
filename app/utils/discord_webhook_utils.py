import os
from enum import Enum, auto
from discord_webhook import DiscordWebhook
from flask import current_app
import requests

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
    content: str = "",
    username: str = "NetherGames Tournament Bot",
    header: str | None = None,
    timeout: int = 10,
    **kwargs
) -> tuple["requests.Response", bool]:
    """Send a message to a Discord webhook channel.

    Returns:
    - requests.Response: The response object from the webhook execution.
    - bool: True if the message was sent successfully (status code 200 or 204), False otherwise.
    """

    if header:
        content = f"{header}\n{content}"

    try:
        webhook = DiscordWebhook(
            url=location.url, # type: ignore
            content=content,
            username=username,
            timeout=timeout,
            rate_limit_retry=True,
            **kwargs
        )

        response = webhook.execute()
        return response, response.status_code in [200, 204] # Discord returns 204 No Content for successful webhook executions without embeds
    except WebhookUrlNotFound as exc:
        current_app.logger.error("Webhook URL not found: %s", exc)
        raise
    except Exception as exc:
        current_app.logger.exception("error sending message to Discord webhook: %s", exc)
        raise

def format_placement_lines(entries, label: str = 'kills') -> str:
    """Format leaderboard entries as markdown lines.

    Args:
        entries: List of leaderboard entry objects with .player and .score attributes
        label: Label for the score (default: 'kills')

    Returns:
        Formatted markdown string with numbered placement lines
    """
    lines = []
    for index, entry in enumerate(entries, start=1):
        lines.append(f"- **{index}. {entry.player}: {entry.score} {label}**")
    return "\n".join(lines) if lines else "- No data available."

def format_prize_lines(prizes: dict[str, str]) -> str:
    """Format prize dictionary as markdown lines.

    Args:
        prizes: Dict with keys 'first', 'second', 'third'

    Returns:
        Formatted markdown string with prize placements
    """
    return (
        f":first_place: 1st — {prizes.get('first', 'TBA')}\n"
        f":second_place: 2nd — {prizes.get('second', 'TBA')}\n"
        f":third_place: 3rd — {prizes.get('third', 'TBA')}"
    )

class WebhookError(Exception):
    """Custom exception for webhook-related errors."""

class WebhookUrlNotFound(WebhookError):
    """Raised when a required webhook URL is not found in environment variables."""

class WebhookSendError(WebhookError):
    """Raised when sending a message to the webhook fails."""

class InvalidWebhookUrlType(WebhookError):
    """Raised when an invalid webhook URL type is provided."""
