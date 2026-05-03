"""Basic helper utilities for working with the NetherGames API."""

from __future__ import annotations
from typing import Any, Optional
from flask import current_app
import requests

BASE_URL = "https://api.ngmc.co/v1/"
DEFAULT_TIMEOUT = 10 # seconds

# Exception classes for each error code
class NetherGamesAPIError(Exception):
    """Base exception for NetherGames API errors."""
    pass

class GeneralError(NetherGamesAPIError):
    """Code 0: General Error."""
    pass

class UnknownFaction(NetherGamesAPIError):
    """Code 10005: Unknown Faction."""
    pass

class UnknownGuild(NetherGamesAPIError):
    """Code 10006: Unknown Guild."""
    pass

class UnknownPlayer(NetherGamesAPIError):
    """Code 10012: Unknown Player."""
    pass

class UnknownServer(NetherGamesAPIError):
    """Code 10016: Unknown Server."""
    pass

class MissingAccess(NetherGamesAPIError):
    """Code 20001: Missing Access."""
    pass

class FeatureTemporarilyDisabled(NetherGamesAPIError):
    """Code 20009: Feature Temporarily Disabled."""
    pass

class InvalidFormBody(NetherGamesAPIError):
    """Code 30001: Invalid Form Body."""
    pass

class MissingPlayerStats(NetherGamesAPIError):
    """Code 30022: Missing Player Stats."""
    pass

class MissingPlayerStatsByType(NetherGamesAPIError):
    """Code 30024: Missing Player Stats By Type."""
    pass

class MaintenanceMode(NetherGamesAPIError):
    """Code 50001: Maintenance Mode."""
    pass

HTTP_ERROR_MAP = {
    404: UnknownPlayer,
    400: NetherGamesAPIError,
    401: MissingAccess,
    403: MissingAccess,
    500: MaintenanceMode,
}

ERROR_CODE_MAP = {
    0: GeneralError,
    10005: UnknownFaction,
    10006: UnknownGuild,
    10012: UnknownPlayer,
    10016: UnknownServer,
    20001: MissingAccess,
    20009: FeatureTemporarilyDisabled,
    30001: InvalidFormBody,
    30022: MissingPlayerStats,
    30024: MissingPlayerStatsByType,
    50001: MaintenanceMode,
}

def request(path: str, params: Optional[dict[str, Any]] = None) -> Any:
    url = f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    API_KEY = current_app.config.get('NETHERGAMES_API_KEY')
    if not API_KEY:
        raise NetherGamesAPIError("NetherGames API key is not configured.")

    headers = {
        'Authorization': API_KEY,
        'Content-Type': 'application/json'
    }

    response = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT, headers=headers)

    if response.status_code in HTTP_ERROR_MAP:
        exc = HTTP_ERROR_MAP[response.status_code]
        raise exc(f"HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        raise NetherGamesAPIError("NetherGames API returned invalid JSON.") from exc

    if isinstance(data, dict) and "code" in data:
        error_code = data["code"]
        error_message = data.get("message", "Unknown error")
        exc = ERROR_CODE_MAP.get(error_code, NetherGamesAPIError)
        raise exc(error_message)

    return data
