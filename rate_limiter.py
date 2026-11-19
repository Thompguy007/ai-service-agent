import time
from collections import defaultdict, deque
from threading import Lock


class RateLimiter:
    def __init__(self, max_requests=10, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        self.requests = defaultdict(deque)
        self.lock = Lock()

    def allow_request(self, customer_id: int) -> bool:
        now = time.monotonic()

        with self.lock:
            timestamps = self.requests[customer_id]

            # Remove requests outside the time window
            while timestamps and now - timestamps[0] >= self.window_seconds:
                timestamps.popleft()

            # Reject if the customer has reached the limit
            if len(timestamps) >= self.max_requests:
                return False

            # Record the new request
            timestamps.append(now)
            return True

    def get_retry_after(self, customer_id: int) -> int:
        import math

        now = time.monotonic()

        with self.lock:
            timestamps = self.requests.get(customer_id)

            if not timestamps:
                return 0

            # Remove expired requests
            while timestamps and now - timestamps[0] >= self.window_seconds:
                timestamps.popleft()

            if len(timestamps) < self.max_requests:
                return 0

            # Calculate how long until the oldest request expires
            remaining = self.window_seconds - (now - timestamps[0])

            return max(0, math.ceil(remaining))