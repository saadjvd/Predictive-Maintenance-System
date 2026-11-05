from datetime import datetime, timedelta, timezone
from collections import defaultdict
import threading

# Thread-safe in-memory rate limiter for authentication endpoints
_lock = threading.Lock()
_attempts = defaultdict(list)


def check_rate_limit(key: str, max_attempts: int = 5, window_seconds: int = 900) -> tuple[bool, int]:
    """
    Check if an action is rate-limited.
    Returns: (is_allowed: bool, remaining_attempts_or_retry_after: int)
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window_seconds)

    with _lock:
        # Filter attempts older than the window
        valid_attempts = [ts for ts in _attempts[key] if ts > cutoff]
        _attempts[key] = valid_attempts

        if len(valid_attempts) >= max_attempts:
            oldest = valid_attempts[0]
            retry_after = int((oldest + timedelta(seconds=window_seconds) - now).total_seconds())
            return False, max(1, retry_after)

        return True, max_attempts - len(valid_attempts)


def record_failed_attempt(key: str):
    """Record a failed login attempt for rate limiting."""
    now = datetime.now(timezone.utc)
    with _lock:
        _attempts[key].append(now)


def clear_rate_limit(key: str):
    """Clear recorded attempts on successful authentication."""
    with _lock:
        if key in _attempts:
            del _attempts[key]

