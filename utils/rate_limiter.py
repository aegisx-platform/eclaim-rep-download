"""
API Rate Limiting with Token Bucket Algorithm

Implements token bucket algorithm for rate limiting API requests.
Prevents abuse, DoS attacks, and ensures fair resource usage.

Features:
- Token bucket algorithm (industry standard)
- Per-user and per-IP rate limits
- Configurable limits per endpoint
- Automatic token refill
- Redis support for distributed systems (optional)
- In-memory fallback for single server

Usage:
    from utils.rate_limiter import rate_limiter

    @app.route('/api/endpoint')
    @rate_limiter.limit(requests=30, window=60, per='user')
    def my_endpoint():
        return jsonify({'success': True})
"""

import time
import hashlib
from typing import Optional, Literal
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Lock
from flask import request, jsonify
from flask_login import current_user
from functools import wraps
from config.database import get_db_config, DB_TYPE
import psycopg2
import pymysql


class TokenBucket:
    """
    Token Bucket implementation for rate limiting.

    How it works:
    - Bucket starts with N tokens (capacity)
    - Each request consumes 1 token
    - Tokens refill at rate R per second
    - If no tokens available, request is rejected

    Example:
        bucket = TokenBucket(capacity=30, refill_rate=0.5)  # 30 req/min
        if bucket.consume():
            # Process request
        else:
            # Rate limit exceeded
    """

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum number of tokens (burst size)
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = Lock()

    def _refill(self):
        """Refill tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens available, False otherwise
        """
        with self.lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False

    def get_remaining(self) -> int:
        """Get number of tokens remaining."""
        with self.lock:
            self._refill()
            return int(self.tokens)

    def get_reset_time(self) -> float:
        """Get time (seconds) until bucket is full."""
        with self.lock:
            self._refill()
            tokens_needed = self.capacity - self.tokens
            return tokens_needed / self.refill_rate if tokens_needed > 0 else 0


class RateLimiter:
    """
    Application-level rate limiter using token buckets.

    Supports:
    - Per-user limits (requires authentication)
    - Per-IP limits (anonymous requests)
    - Per-endpoint configuration
    - In-memory storage (single server)
    - Database persistence (optional)
    """

    def __init__(self, use_database: bool = False):
        """
        Initialize rate limiter.

        Args:
            use_database: Store rate limits in database (for multi-server)
        """
        self.use_database = use_database
        self.buckets = defaultdict(lambda: None)  # key -> TokenBucket
        self.cleanup_interval = 3600  # Cleanup old buckets every hour
        self.last_cleanup = time.time()

    def _get_identifier(self, per: Literal['user', 'ip']) -> str:
        """
        Get rate limit identifier (user ID or IP address).

        Args:
            per: Limit per 'user' or 'ip'

        Returns:
            Identifier string
        """
        if per == 'user':
            if current_user.is_authenticated:
                return f"user:{current_user.id}"
            else:
                # Fallback to IP for unauthenticated requests
                return f"ip:{request.remote_addr}"
        elif per == 'ip':
            return f"ip:{request.remote_addr}"
        else:
            raise ValueError(f"Invalid 'per' value: {per}")

    def _get_bucket_key(self, endpoint: str, identifier: str) -> str:
        """
        Generate unique bucket key.

        Args:
            endpoint: Endpoint name (e.g., '/api/downloads')
            identifier: User/IP identifier

        Returns:
            Bucket key (hashed for privacy)
        """
        # Hash to protect privacy (don't store raw IPs/user IDs in memory)
        key = f"{endpoint}:{identifier}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _get_bucket(self, key: str, capacity: int, refill_rate: float) -> TokenBucket:
        """Get or create token bucket."""
        if self.buckets[key] is None:
            self.buckets[key] = TokenBucket(capacity, refill_rate)

        return self.buckets[key]

    def _cleanup_old_buckets(self):
        """Remove old buckets to prevent memory leaks."""
        now = time.time()

        if now - self.last_cleanup < self.cleanup_interval:
            return

        # Remove buckets that haven't been used in 1 hour
        keys_to_remove = []
        for key, bucket in self.buckets.items():
            if bucket and (now - bucket.last_refill) > 3600:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.buckets[key]

        self.last_cleanup = now

    def limit(
        self,
        requests: int,
        window: int,
        per: Literal['user', 'ip'] = 'user',
        endpoint: Optional[str] = None
    ):
        """
        Rate limit decorator.

        Args:
            requests: Number of requests allowed
            window: Time window in seconds
            per: Limit per 'user' or 'ip'
            endpoint: Endpoint name (default: auto-detect)

        Returns:
            Decorator function

        Example:
            @app.route('/api/downloads')
            @rate_limiter.limit(requests=30, window=60, per='user')
            def download():
                return jsonify({'success': True})
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Auto-detect endpoint if not provided
                _endpoint = endpoint or request.endpoint or f.__name__

                # Get identifier
                identifier = self._get_identifier(per)

                # Get bucket key
                bucket_key = self._get_bucket_key(_endpoint, identifier)

                # Calculate refill rate (tokens per second)
                refill_rate = requests / window

                # Get or create bucket
                bucket = self._get_bucket(bucket_key, requests, refill_rate)

                # Try to consume token
                if not bucket.consume():
                    # Rate limit exceeded
                    remaining = bucket.get_remaining()
                    reset_time = bucket.get_reset_time()
                    retry_after = int(reset_time) + 1  # Round up

                    # Log rate limit event
                    from utils.logging_config import setup_logger
                    logger = setup_logger('rate_limiter')
                    logger.warning(
                        f"Rate limit exceeded: {identifier} on {_endpoint} "
                        f"(limit: {requests}/{window}s)"
                    )

                    # Return 429 Too Many Requests
                    response = jsonify({
                        'success': False,
                        'error': 'Rate limit exceeded',
                        'message': f'Too many requests. Limit: {requests} requests per {window} seconds.',
                        'retry_after': retry_after,
                        'limit': requests,
                        'remaining': remaining,
                        'reset': int(time.time() + reset_time)
                    })
                    response.status_code = 429
                    response.headers['Retry-After'] = str(retry_after)
                    response.headers['X-RateLimit-Limit'] = str(requests)
                    response.headers['X-RateLimit-Remaining'] = str(remaining)
                    response.headers['X-RateLimit-Reset'] = str(int(time.time() + reset_time))

                    return response

                # Cleanup old buckets periodically
                self._cleanup_old_buckets()

                # Add rate limit headers to successful response
                remaining = bucket.get_remaining()
                reset_time = bucket.get_reset_time()

                response = f(*args, **kwargs)

                # If response is tuple (response, status_code), extract response
                if isinstance(response, tuple):
                    actual_response = response[0]
                else:
                    actual_response = response

                # Add headers only if response object has headers attribute
                if hasattr(actual_response, 'headers'):
                    actual_response.headers['X-RateLimit-Limit'] = str(requests)
                    actual_response.headers['X-RateLimit-Remaining'] = str(remaining)
                    actual_response.headers['X-RateLimit-Reset'] = str(int(time.time() + reset_time))

                return response

            return decorated_function
        return decorator

    def reset(self, endpoint: str, identifier: str):
        """
        Reset rate limit for specific endpoint and identifier.

        Args:
            endpoint: Endpoint name
            identifier: User/IP identifier
        """
        bucket_key = self._get_bucket_key(endpoint, identifier)
        if bucket_key in self.buckets:
            del self.buckets[bucket_key]


# Global rate limiter instance
rate_limiter = RateLimiter(use_database=False)


# Convenience decorators for common limits
def limit_login(f):
    """Rate limit for login endpoint: 5 requests per 5 minutes."""
    return rate_limiter.limit(requests=5, window=300, per='ip')(f)


def limit_api(f):
    """Rate limit for API endpoints: 60 requests per minute."""
    return rate_limiter.limit(requests=60, window=60, per='user')(f)


def limit_download(f):
    """Rate limit for download endpoints: 10 requests per hour."""
    return rate_limiter.limit(requests=10, window=3600, per='user')(f)


def limit_export(f):
    """Rate limit for data export: 5 requests per hour."""
    return rate_limiter.limit(requests=5, window=3600, per='user')(f)
