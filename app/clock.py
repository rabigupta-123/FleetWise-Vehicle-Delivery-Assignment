from collections.abc import Callable
from datetime import UTC, datetime

# Injectable clock provider for deterministic testing
_clock_provider: Callable[[], datetime] | None = None


def get_current_time() -> datetime:
    """
    Returns current server UTC time.
    If a mock/deterministic clock provider is set (e.g. during testing),
    it is queried to ensure 100% reproducible timestamps and rate limiting.
    """
    if _clock_provider is not None:
        return _clock_provider()
    return datetime.now(UTC)


def set_clock_provider(provider: Callable[[], datetime] | None) -> None:
    """Inject a deterministic clock provider or reset to real system clock with None."""
    global _clock_provider
    _clock_provider = provider


def utc_now_iso() -> str:
    """Returns ISO-8601 formatted string of current server UTC time."""
    return get_current_time().isoformat()

