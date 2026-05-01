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

# Map error codes to exception classes
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
    headers = {
        'Authorization': current_app.config.get('NETHERGAMES_API_KEY'),
        'Content-Type': 'application/json'
    }
    response = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT, headers=headers)

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise NetherGamesAPIError(
            f"NetherGames API request failed: {response.status_code}"
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise NetherGamesAPIError("NetherGames API returned invalid JSON.") from exc

    # Check for error codes in response
    if isinstance(data, dict) and 'code' in data:
        error_code = data.get('code')
        error_message = data.get('message', 'Unknown error')

        exception_class = ERROR_CODE_MAP.get(error_code, NetherGamesAPIError) # type: ignore
        raise exception_class(error_message)

    return data
