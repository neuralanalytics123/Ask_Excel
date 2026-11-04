"""Shared usage limits so one visitor (or a burst of visitors) cannot exhaust the Groq quota."""

import threading
import time
from collections import deque

import streamlit as st


class RateLimiter:
    """Sliding-window limiter: N requests per minute and M per day, shared by all sessions."""

    def __init__(self, per_minute: int, per_day: int):
        self.per_minute = per_minute
        self.per_day = per_day
        self._minute: deque[float] = deque()
        self._day: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> tuple[bool, str]:
        """Return (allowed, reason). reason is '', 'busy' (per-minute) or 'daily'."""
        now = time.time()
        with self._lock:
            while self._minute and now - self._minute[0] > 60:
                self._minute.popleft()
            while self._day and now - self._day[0] > 86400:
                self._day.popleft()
            if len(self._day) >= self.per_day:
                return False, "daily"
            if len(self._minute) >= self.per_minute:
                return False, "busy"
            self._minute.append(now)
            self._day.append(now)
            return True, ""


@st.cache_resource
def get_limiter(per_minute: int, per_day: int) -> RateLimiter:
    """One limiter per server process, shared by every visitor."""
    return RateLimiter(per_minute, per_day)
