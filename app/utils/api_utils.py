"""Basic helper utilities for working with the NetherGames API."""

from __future__ import annotations
from typing import Any, Optional
from flask import current_app
import requests
import time

BASE_URL = "https://api.ngmc.co/v1/"
DEFAULT_TIMEOUT = 30 # seconds
# Retry configuration for 'transient' errors
MAX_RETRIES = 3
# Cooldown that (pauses) 'backs off' from the request to give the program time to 'breathe' and verify the connection before retrying.
BACKOFF_FACTOR = 1 # seconds (exponential factor with base 2: `sleep_for = BACKOFF_FACTOR * (2 ** (attempt - 1))`)

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
    """ Send a request to the NetherGames API """
    url = f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    API_KEY = current_app.config.get('NETHERGAMES_API_KEY')
    if not API_KEY:
        raise NetherGamesAPIError("NetherGames API key is not configured.")

    headers = {
        'Authorization': API_KEY,
        'Content-Type': 'application/json'
    }

    current_app.logger.debug(
        "NetherGames API request starting: path=%s params=%s timeout=%s max_retries=%s",
        path,
        params,
        DEFAULT_TIMEOUT,
        MAX_RETRIES,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        # Disclaimer: Reattempt logic given by AI.
        # Reattempt X times
        try:
            current_app.logger.debug(
                "NetherGames API attempt %s/%s for path=%s params=%s",
                attempt,
                MAX_RETRIES,
                path,
                params,
            )
            response = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT, headers=headers)
            current_app.logger.debug(
                "NetherGames API response received: path=%s status_code=%s attempt=%s",
                path,
                response.status_code,
                attempt,
            )
            break # Break on success
        except requests.Timeout as exc:
            current_app.logger.warning(
                "NetherGames API attempt %s timed out: path=%s params=%s timeout=%s",
                attempt,
                path,
                params,
                DEFAULT_TIMEOUT,
            )
            if attempt < MAX_RETRIES:
                sleep_for = BACKOFF_FACTOR * (2 ** (attempt - 1))
                current_app.logger.debug(
                    "Sleeping %s seconds before next attempt", sleep_for
                )
                time.sleep(sleep_for)
                continue
            raise NetherGamesAPIError(f"NetherGames API request timed out after {DEFAULT_TIMEOUT} seconds on attempt {attempt}.") from exc
        except requests.RequestException as exc:
            current_app.logger.error(
                "NetherGames API request error on attempt %s: path=%s params=%s error=%s",
                attempt,
                path,
                params,
                exc,
            )

            if attempt < MAX_RETRIES:
                sleep_for = BACKOFF_FACTOR * (2 ** (attempt - 1))
                time.sleep(sleep_for)
                continue

            # If MAX retries exhausted, raise error
            raise NetherGamesAPIError(f"NetherGames API request failed after {MAX_RETRIES} attempts: {exc}") from exc

    if response.status_code in HTTP_ERROR_MAP:
        # Status an error?
        exc = HTTP_ERROR_MAP[response.status_code]
        # Return detailed log
        current_app.logger.error(
            "NetherGames API HTTP error: path=%s status_code=%s params=%s",
            path,
            response.status_code,
            params,
        )
        raise exc(f"HTTP {response.status_code}")

    try: data = response.json() # Attempt to extract json from response
    except ValueError as exc:
        raise NetherGamesAPIError("NetherGames API returned invalid JSON.") from exc

    if isinstance(data, dict) and "code" in data:
        # "code" only returns in the case of an error (May 2026)
        # Raise exception in this case
        error_code = data["code"]
        error_message = data.get("message", "Unknown error")
        exc = ERROR_CODE_MAP.get(error_code, NetherGamesAPIError)
        current_app.logger.error(
            "NetherGames API returned application error: path=%s code=%s message=%s params=%s",
            path,
            error_code,
            error_message,
            params,
        )
        raise exc(error_message)

    # Return dict of response
    return data
