"""
elliotoxin | 2025
Advanced API Rate Limiter Implementation
Supports multiple algorithms: Token Bucket, Sliding Window, Leaky Bucket, Fixed Window
With Redis integration for distributed systems
"""

import time
import redis
import json
import hashlib
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from typing import Dict, Tuple, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RateLimitAlgorithm(Enum):
    """Available rate limiting algorithms"""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    LEAKY_BUCKET = "leaky_bucket"
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW_LOG = "sliding_window_log"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    max_requests: int
    time_window: int  # in seconds
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    burst_size: Optional[int] = None
    refill_rate: Optional[float] = None
    distributed: bool = False
    redis_url: str = "redis://localhost:6379/0"


@dataclass
class RateLimitResponse:
    """Response from rate limit check"""
    allowed: bool
    remaining: int
    reset_time: int
    retry_after: Optional[int] = None
    requests_in_window: int = 0


class BaseRateLimiter(ABC):
    """Abstract base class for rate limiters"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def is_allowed(self, client_id: str) -> RateLimitResponse:
        """Check if request is allowed"""
        pass
    
    @abstractmethod
    def reset(self, client_id: str) -> None:
        """Reset rate limit for client"""
        pass
    
    @abstractmethod
    def get_status(self, client_id: str) -> Dict:
        """Get current status of rate limit"""
        pass


class TokenBucketLimiter(BaseRateLimiter):
    """
    Token Bucket Algorithm
    - Clients have a bucket with max_tokens
    - Tokens are added at a fixed rate (refill_rate)
    - Each request costs 1 token
    - If bucket is empty, request is rejected
    """
    
    def __init__(self, config: RateLimitConfig):
        super().__init__(config)
        self.buckets: Dict[str, Dict] = defaultdict(lambda: {
            'tokens': config.max_requests,
            'last_refill': time.time(),
            'burst_size': config.burst_size or config.max_requests
        })
        
        # Calculate refill rate (tokens per second)
        if config.refill_rate:
            self.refill_rate = config.refill_rate
        else:
            self.refill_rate = config.max_requests / config.time_window
        
        self.logger.info(f"TokenBucket initialized: {config.max_requests} tokens "
                        f"per {config.time_window}s (rate: {self.refill_rate:.2f} tokens/s)")
    
    def _refill(self, client_id: str) -> float:
        """Refill tokens based on elapsed time"""
        bucket = self.buckets[client_id]
        now = time.time()
        elapsed = now - bucket['last_refill']
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        bucket['tokens'] = min(
            bucket['tokens'] + tokens_to_add,
            bucket['burst_size']
        )
        bucket['last_refill'] = now
        
        return bucket['tokens']
    
    def is_allowed(self, client_id: str) -> RateLimitResponse:
        """Check if request is allowed"""
        self._refill(client_id)
        bucket = self.buckets[client_id]
        
        if bucket['tokens'] >= 1:
            bucket['tokens'] -= 1
            reset_time = int(self.config.time_window + time.time())
            
            return RateLimitResponse(
                allowed=True,
                remaining=int(bucket['tokens']),
                reset_time=reset_time,
                requests_in_window=self.config.max_requests - int(bucket['tokens'])
            )
        else:
            retry_after = int(1 / self.refill_rate)  # Time until next token
            reset_time = int(time.time() + retry_after)
            
            return RateLimitResponse(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                retry_after=retry_after,
                requests_in_window=self.config.max_requests
            )
    
    def reset(self, client_id: str) -> None:
        """Reset rate limit for client"""
        self.buckets[client_id] = {
            'tokens': self.config.max_requests,
            'last_refill': time.time(),
            'burst_size': self.config.burst_size or self.config.max_requests
        }
        self.logger.info(f"Rate limit reset for client: {client_id}")
    
    def get_status(self, client_id: str) -> Dict:
        """Get current status"""
        self._refill(client_id)
        bucket = self.buckets[client_id]
        return {
            'algorithm': 'token_bucket',
            'tokens': bucket['tokens'],
            'max_tokens': bucket['burst_size'],
            'refill_rate': self.refill_rate
        }


class SlidingWindowLimiter(BaseRateLimiter):
    """
    Sliding Window Counter Algorithm
    - Maintains exact request count in a rolling time window
    - More precise than fixed window but uses more memory
    - Good for strict rate limiting requirements
    """
    
    def __init__(self, config: RateLimitConfig):
        super().__init__(config)
        self.windows: Dict[str, deque] = defaultdict(deque)
        self.logger.info(f"SlidingWindow initialized: {config.max_requests} "
                        f"requests per {config.time_window}s")
    
    def is_allowed(self, client_id: str) -> RateLimitResponse:
        """Check if request is allowed"""
        now = time.time()
        window_start = now - self.config.time_window
        
        # Remove old requests outside the window
        window = self.windows[client_id]
        while window and window[0] < window_start:
            window.popleft()
        
        requests_in_window = len(window)
        reset_time = int(self.config.time_window + now) if window else int(now + self.config.time_window)
        
        if requests_in_window < self.config.max_requests:
            window.append(now)
            return RateLimitResponse(
                allowed=True,
                remaining=self.config.max_requests - requests_in_window - 1,
                reset_time=reset_time,
                requests_in_window=requests_in_window + 1
            )
        else:
            retry_after = int(window[0] - window_start + 1)
            return RateLimitResponse(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                retry_after=retry_after,
                requests_in_window=requests_in_window
            )
    
    def reset(self, client_id: str) -> None:
        """Reset rate limit for client"""
        self.windows[client_id].clear()
        self.logger.info(f"Rate limit reset for client: {client_id}")
    
    def get_status(self, client_id: str) -> Dict:
        """Get current status"""
        now = time.time()
        window_start = now - self.config.time_window
        
        window = self.windows[client_id]
        requests_in_window = sum(1 for t in window if t >= window_start)
        
        return {
            'algorithm': 'sliding_window',
            'requests_in_window': requests_in_window,
            'max_requests': self.config.max_requests,
            'window_size': self.config.time_window
        }


class LeakyBucketLimiter(BaseRateLimiter):
    """
    Leaky Bucket Algorithm
    - Requests are added to a queue (bucket)
    - Requests are processed at a fixed rate
    - Excess requests are dropped
    - Good for smoothing burst traffic
    """
    
    def __init__(self, config: RateLimitConfig):
        super().__init__(config)
        self.buckets: Dict[str, Dict] = defaultdict(lambda: {
            'queue': deque(),
            'last_leak_time': time.time(),
            'total_leaked': 0
        })
        
        # Leak rate: requests per second
        self.leak_rate = config.max_requests / config.time_window
        self.logger.info(f"LeakyBucket initialized: {config.max_requests} "
                        f"requests per {config.time_window}s (leak_rate: {self.leak_rate:.2f})")
    
    def _leak(self, client_id: str) -> int:
        """Process queued requests at fixed leak rate"""
        bucket = self.buckets[client_id]
        now = time.time()
        elapsed = now - bucket['last_leak_time']
        
        # Calculate how many requests should leak
        requests_to_leak = int(elapsed * self.leak_rate)
        
        for _ in range(requests_to_leak):
            if bucket['queue']:
                bucket['queue'].popleft()
                bucket['total_leaked'] += 1
        
        bucket['last_leak_time'] = now
        return len(bucket['queue'])
    
    def is_allowed(self, client_id: str) -> RateLimitResponse:
        """Check if request is allowed"""
        queue_size = self._leak(client_id)
        bucket = self.buckets[client_id]
        
        if queue_size < self.config.max_requests:
            bucket['queue'].append(time.time())
            reset_time = int(self.config.time_window + time.time())
            
            return RateLimitResponse(
                allowed=True,
                remaining=self.config.max_requests - queue_size - 1,
                reset_time=reset_time,
                requests_in_window=queue_size + 1
            )
        else:
            retry_after = int(1 / self.leak_rate)
            return RateLimitResponse(
                allowed=False,
                remaining=0,
                reset_time=int(time.time() + retry_after),
                retry_after=retry_after,
                requests_in_window=queue_size
            )
    
    def reset(self, client_id: str) -> None:
        """Reset rate limit for client"""
        self.buckets[client_id] = {
            'queue': deque(),
            'last_leak_time': time.time(),
            'total_leaked': 0
        }
        self.logger.info(f"Rate limit reset for client: {client_id}")
    
    def get_status(self, client_id: str) -> Dict:
        """Get current status"""
        queue_size = self._leak(client_id)
        return {
            'algorithm': 'leaky_bucket',
            'queue_size': queue_size,
            'max_capacity': self.config.max_requests,
            'leak_rate': self.leak_rate,
            'total_leaked': self.buckets[client_id]['total_leaked']
        }


class FixedWindowLimiter(BaseRateLimiter):
    """
    Fixed Window Counter Algorithm
    - Time is divided into fixed windows
    - Counter resets at window boundaries
    - Simple but can have edge-case issues at boundaries
    """
    
    def __init__(self, config: RateLimitConfig):
        super().__init__(config)
        self.windows: Dict[str, Dict] = defaultdict(lambda: {
            'count': 0,
            'window_start': time.time()
        })
        self.logger.info(f"FixedWindow initialized: {config.max_requests} "
                        f"requests per {config.time_window}s")
    
    def is_allowed(self, client_id: str) -> RateLimitResponse:
        """Check if request is allowed"""
        now = time.time()
        window = self.windows[client_id]
        
        # Check if we need to reset the window
        if now - window['window_start'] >= self.config.time_window:
            window['count'] = 0
            window['window_start'] = now
        
        reset_time = int(window['window_start'] + self.config.time_window)
        
        if window['count'] < self.config.max_requests:
            window['count'] += 1
            return RateLimitResponse(
                allowed=True,
                remaining=self.config.max_requests - window['count'],
                reset_time=reset_time,
                requests_in_window=window['count']
            )
        else:
            retry_after = int(reset_time - now)
            return RateLimitResponse(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                retry_after=retry_after,
                requests_in_window=window['count']
            )
    
    def reset(self, client_id: str) -> None:
        """Reset rate limit for client"""
        self.windows[client_id] = {
            'count': 0,
            'window_start': time.time()
        }
        self.logger.info(f"Rate limit reset for client: {client_id}")
    
    def get_status(self, client_id: str) -> Dict:
        """Get current status"""
        now = time.time()
        window = self.windows[client_id]
        
        # Check if window needs reset
        if now - window['window_start'] >= self.config.time_window:
            window['count'] = 0
            window['window_start'] = now
        
        return {
            'algorithm': 'fixed_window',
            'count': window['count'],
            'max_requests': self.config.max_requests,
            'window_reset_in': int(window['window_start'] + self.config.time_window - now)
        }


class DistributedRateLimiter(BaseRateLimiter):
    """
    Redis-based distributed rate limiter
    Uses Lua scripts for atomic operations
    """
    
    def __init__(self, config: RateLimitConfig):
        super().__init__(config)
        self.redis_client = redis.from_url(config.redis_url, decode_responses=True)
        self.algorithm = config.algorithm
        
        # Lua script for sliding window with Redis
        self.lua_script = self.redis_client.register_script("""
            local key = KEYS[1]
            local now = tonumber(ARGV[1])
            local window_start = now - tonumber(ARGV[2])
            local max_requests = tonumber(ARGV[3])
            
            -- Remove old entries outside the window
            redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
            
            -- Count requests in current window
            local current_count = redis.call('ZCOUNT', key, window_start, now)
            
            if current_count < max_requests then
                -- Add new request
                redis.call('ZADD', key, now, now .. '-' .. math.random())
                redis.call('EXPIRE', key, tonumber(ARGV[2]))
                return {1, max_requests - current_count - 1, current_count + 1}
            else
                return {0, 0, current_count}
            end
        """)
        
        self.logger.info(f"DistributedRateLimiter initialized with {config.algorithm.value}")
    
    def is_allowed(self, client_id: str) -> RateLimitResponse:
        """Check if request is allowed using Redis"""
        key = f"rate_limit:{client_id}"
        now = time.time()
        reset_time = int(now + self.config.time_window)
        
        try:
            result = self.lua_script(
                keys=[key],
                args=[int(now * 1000), self.config.time_window * 1000, self.config.max_requests]
            )
            
            allowed, remaining, requests_in_window = result
            
            if allowed:
                return RateLimitResponse(
                    allowed=True,
                    remaining=remaining,
                    reset_time=reset_time,
                    requests_in_window=requests_in_window
                )
            else:
                return RateLimitResponse(
                    allowed=False,
                    remaining=0,
                    reset_time=reset_time,
                    retry_after=int(self.config.time_window / requests_in_window),
                    requests_in_window=requests_in_window
                )
        except Exception as e:
            self.logger.error(f"Redis error: {e}")
            # Fallback to allowing request on error
            return RateLimitResponse(
                allowed=True,
                remaining=self.config.max_requests - 1,
                reset_time=reset_time
            )
    
    def reset(self, client_id: str) -> None:
        """Reset rate limit for client"""
        key = f"rate_limit:{client_id}"
        self.redis_client.delete(key)
        self.logger.info(f"Rate limit reset for client: {client_id}")
    
    def get_status(self, client_id: str) -> Dict:
        """Get current status"""
        key = f"rate_limit:{client_id}"
        count = self.redis_client.zcount(key, '-inf', '+inf')
        
        return {
            'algorithm': 'distributed_' + self.algorithm.value,
            'requests_in_window': count,
            'max_requests': self.config.max_requests,
            'ttl': self.redis_client.ttl(key)
        }


class RateLimiterFactory:
    """Factory for creating rate limiters"""
    
    _limiters = {
        RateLimitAlgorithm.TOKEN_BUCKET: TokenBucketLimiter,
        RateLimitAlgorithm.SLIDING_WINDOW: SlidingWindowLimiter,
        RateLimitAlgorithm.LEAKY_BUCKET: LeakyBucketLimiter,
        RateLimitAlgorithm.FIXED_WINDOW: FixedWindowLimiter,
    }
    
    @classmethod
    def create(cls, config: RateLimitConfig) -> BaseRateLimiter:
        """Create a rate limiter based on config"""
        if config.distributed:
            return DistributedRateLimiter(config)
        
        limiter_class = cls._limiters.get(config.algorithm)
        if not limiter_class:
            raise ValueError(f"Unknown algorithm: {config.algorithm}")
        
        return limiter_class(config)
    
    @classmethod
    def register(cls, algorithm: RateLimitAlgorithm, limiter_class: type):
        """Register a custom rate limiter"""
        cls._limiters[algorithm] = limiter_class
        logger.info(f"Registered custom limiter: {algorithm.value}")
