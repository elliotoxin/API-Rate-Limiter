"""
Comprehensive test suite for rate limiters
Tests all algorithms and edge cases
"""

import unittest
import time
import threading
from unittest.mock import patch, MagicMock

from rate_limiter import (
    TokenBucketLimiter, SlidingWindowLimiter, LeakyBucketLimiter,
    FixedWindowLimiter, RateLimitConfig, RateLimitAlgorithm,
    RateLimiterFactory
)


class TestTokenBucketLimiter(unittest.TestCase):
    """Test Token Bucket algorithm"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = RateLimitConfig(
            max_requests=10,
            time_window=60,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET
        )
        self.limiter = TokenBucketLimiter(self.config)
    
    def test_initial_tokens(self):
        """Test initial tokens are available"""
        response = self.limiter.is_allowed('client1')
        self.assertTrue(response.allowed)
        self.assertEqual(response.remaining, 9)
    
    def test_max_requests_allowed(self):
        """Test max requests are allowed"""
        for i in range(10):
            response = self.limiter.is_allowed('client1')
            self.assertTrue(response.allowed)
        
        # 11th request should be rejected
        response = self.limiter.is_allowed('client1')
        self.assertFalse(response.allowed)
    
    def test_token_refill(self):
        """Test tokens are refilled over time"""
        # Use all tokens
        for _ in range(10):
            self.limiter.is_allowed('client2')
        
        # Wait for token refill (simulated)
        self.limiter.buckets['client2']['last_refill'] = time.time() - 6  # 6 seconds ago
        
        response = self.limiter.is_allowed('client2')
        self.assertTrue(response.allowed)  # Should have at least 1 token after 6s
    
    def test_burst_protection(self):
        """Test burst size limits"""
        config = RateLimitConfig(
            max_requests=10,
            time_window=60,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
            burst_size=5
        )
        limiter = TokenBucketLimiter(config)
        
        # Check burst size is respected
        status = limiter.get_status('client3')
        self.assertEqual(status['max_tokens'], 5)
    
    def test_separate_client_limits(self):
        """Test different clients have separate limits"""
        for _ in range(10):
            self.limiter.is_allowed('client_a')
        
        response_a = self.limiter.is_allowed('client_a')
        self.assertFalse(response_a.allowed)
        
        response_b = self.limiter.is_allowed('client_b')
        self.assertTrue(response_b.allowed)
    
    def test_reset(self):
        """Test reset functionality"""
        # Use all tokens
        for _ in range(10):
            self.limiter.is_allowed('client4')
        
        self.assertFalse(self.limiter.is_allowed('client4').allowed)
        
        # Reset
        self.limiter.reset('client4')
        self.assertTrue(self.limiter.is_allowed('client4').allowed)


class TestSlidingWindowLimiter(unittest.TestCase):
    """Test Sliding Window algorithm"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = RateLimitConfig(
            max_requests=5,
            time_window=10,
            algorithm=RateLimitAlgorithm.SLIDING_WINDOW
        )
        self.limiter = SlidingWindowLimiter(self.config)
    
    def test_request_tracking(self):
        """Test requests are tracked in window"""
        for _ in range(5):
            response = self.limiter.is_allowed('client1')
            self.assertTrue(response.allowed)
        
        response = self.limiter.is_allowed('client1')
        self.assertFalse(response.allowed)
    
    def test_window_expiration(self):
        """Test requests expire after window"""
        self.limiter.is_allowed('client2')
        
        # Simulate time passing beyond window
        self.limiter.windows['client2'][0] = time.time() - 20
        
        response = self.limiter.is_allowed('client2')
        self.assertTrue(response.allowed)
    
    def test_precise_counting(self):
        """Test precise request counting"""
        for i in range(5):
            response = self.limiter.is_allowed('client3')
            self.assertEqual(response.requests_in_window, i + 1)
    
    def test_reset(self):
        """Test reset functionality"""
        for _ in range(5):
            self.limiter.is_allowed('client4')
        
        self.limiter.reset('client4')
        response = self.limiter.is_allowed('client4')
        self.assertTrue(response.allowed)
        self.assertEqual(response.requests_in_window, 1)


class TestLeakyBucketLimiter(unittest.TestCase):
    """Test Leaky Bucket algorithm"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = RateLimitConfig(
            max_requests=10,
            time_window=10,
            algorithm=RateLimitAlgorithm.LEAKY_BUCKET
        )
        self.limiter = LeakyBucketLimiter(self.config)
    
    def test_queue_capacity(self):
        """Test queue capacity"""
        for i in range(10):
            response = self.limiter.is_allowed('client1')
            self.assertTrue(response.allowed)
        
        response = self.limiter.is_allowed('client1')
        self.assertFalse(response.allowed)
    
    def test_leaking(self):
        """Test requests leak over time"""
        # Fill bucket
        for _ in range(5):
            self.limiter.is_allowed('client2')
        
        initial_queue = self.limiter._leak('client2')
        self.assertEqual(initial_queue, 5)
        
        # Simulate time passing
        self.limiter.buckets['client2']['last_leak_time'] = time.time() - 5
        
        leaked_queue = self.limiter._leak('client2')
        self.assertLess(leaked_queue, initial_queue)
    
    def test_statistics(self):
        """Test statistics tracking"""
        for _ in range(3):
            self.limiter.is_allowed('client3')
        
        status = self.limiter.get_status('client3')
        self.assertIn('total_leaked', status)


class TestFixedWindowLimiter(unittest.TestCase):
    """Test Fixed Window algorithm"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = RateLimitConfig(
            max_requests=5,
            time_window=10,
            algorithm=RateLimitAlgorithm.FIXED_WINDOW
        )
        self.limiter = FixedWindowLimiter(self.config)
    
    def test_request_counting(self):
        """Test request counting within window"""
        for i in range(5):
            response = self.limiter.is_allowed('client1')
            self.assertTrue(response.allowed)
            self.assertEqual(response.requests_in_window, i + 1)
    
    def test_window_reset(self):
        """Test window resets after time_window"""
        for _ in range(5):
            self.limiter.is_allowed('client2')
        
        # Simulate window expiration
        self.limiter.windows['client2']['window_start'] = time.time() - 15
        
        response = self.limiter.is_allowed('client2')
        self.assertTrue(response.allowed)
        self.assertEqual(response.requests_in_window, 1)
    
    def test_hard_limit(self):
        """Test hard limit enforcement"""
        for _ in range(5):
            self.limiter.is_allowed('client3')
        
        response = self.limiter.is_allowed('client3')
        self.assertFalse(response.allowed)


class TestRateLimiterFactory(unittest.TestCase):
    """Test rate limiter factory"""
    
    def test_token_bucket_creation(self):
        """Test token bucket creation"""
        config = RateLimitConfig(
            max_requests=10,
            time_window=60,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET
        )
        limiter = RateLimiterFactory.create(config)
        self.assertIsInstance(limiter, TokenBucketLimiter)
    
    def test_sliding_window_creation(self):
        """Test sliding window creation"""
        config = RateLimitConfig(
            max_requests=10,
            time_window=60,
            algorithm=RateLimitAlgorithm.SLIDING_WINDOW
        )
        limiter = RateLimiterFactory.create(config)
        self.assertIsInstance(limiter, SlidingWindowLimiter)
    
    def test_leaky_bucket_creation(self):
        """Test leaky bucket creation"""
        config = RateLimitConfig(
            max_requests=10,
            time_window=60,
            algorithm=RateLimitAlgorithm.LEAKY_BUCKET
        )
        limiter = RateLimiterFactory.create(config)
        self.assertIsInstance(limiter, LeakyBucketLimiter)
    
    def test_fixed_window_creation(self):
        """Test fixed window creation"""
        config = RateLimitConfig(
            max_requests=10,
            time_window=60,
            algorithm=RateLimitAlgorithm.FIXED_WINDOW
        )
        limiter = RateLimiterFactory.create(config)
        self.assertIsInstance(limiter, FixedWindowLimiter)


class TestConcurrency(unittest.TestCase):
    """Test thread-safety"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = RateLimitConfig(
            max_requests=100,
            time_window=60,
            algorithm=RateLimitAlgorithm.SLIDING_WINDOW
        )
        self.limiter = SlidingWindowLimiter(self.config)
    
    def test_concurrent_requests(self):
        """Test handling concurrent requests"""
        allowed_count = [0]
        rejected_count = [0]
        lock = threading.Lock()
        
        def make_requests():
            for _ in range(10):
                response = self.limiter.is_allowed('concurrent_client')
                with lock:
                    if response.allowed:
                        allowed_count[0] += 1
                    else:
                        rejected_count[0] += 1
        
        threads = [threading.Thread(target=make_requests) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Total requests should be 50
        self.assertEqual(allowed_count[0] + rejected_count[0], 50)
        # Allowed should be max 100
        self.assertLessEqual(allowed_count[0], 100)
    
    def test_race_condition_token_bucket(self):
        """Test token bucket handles race conditions"""
        config = RateLimitConfig(
            max_requests=10,
            time_window=60,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET
        )
        limiter = TokenBucketLimiter(config)
        
        allowed = [0]
        lock = threading.Lock()
        
        def concurrent_check():
            response = limiter.is_allowed('race_test')
            if response.allowed:
                with lock:
                    allowed[0] += 1
        
        threads = [threading.Thread(target=concurrent_check) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should not exceed max_requests
        self.assertLessEqual(allowed[0], 10)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions"""
    
    def test_zero_window(self):
        """Test zero time window handling"""
        config = RateLimitConfig(
            max_requests=10,
            time_window=0,
            algorithm=RateLimitAlgorithm.SLIDING_WINDOW
        )
        limiter = SlidingWindowLimiter(config)
        
        # Should handle gracefully
        response = limiter.is_allowed('edge1')
        self.assertTrue(response.allowed)
    
    def test_large_request_count(self):
        """Test large request counts"""
        config = RateLimitConfig(
            max_requests=1000000,
            time_window=60,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET
        )
        limiter = TokenBucketLimiter(config)
        
        response = limiter.is_allowed('edge2')
        self.assertTrue(response.allowed)
    
    def test_negative_remaining(self):
        """Test negative remaining is handled"""
        config = RateLimitConfig(
            max_requests=5,
            time_window=60,
            algorithm=RateLimitAlgorithm.FIXED_WINDOW
        )
        limiter = FixedWindowLimiter(config)
        
        for _ in range(5):
            limiter.is_allowed('edge3')
        
        response = limiter.is_allowed('edge3')
        self.assertFalse(response.allowed)
        self.assertEqual(response.remaining, 0)
    
    def test_multiple_resets(self):
        """Test multiple resets"""
        config = RateLimitConfig(
            max_requests=5,
            time_window=60,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET
        )
        limiter = TokenBucketLimiter(config)
        
        limiter.reset('edge4')
        limiter.reset('edge4')
        limiter.reset('edge4')
        
        response = limiter.is_allowed('edge4')
        self.assertTrue(response.allowed)


def run_benchmarks():
    """Run performance benchmarks"""
    import sys
    
    algorithms = [
        ('TokenBucket', RateLimitAlgorithm.TOKEN_BUCKET),
        ('SlidingWindow', RateLimitAlgorithm.SLIDING_WINDOW),
        ('LeakyBucket', RateLimitAlgorithm.LEAKY_BUCKET),
        ('FixedWindow', RateLimitAlgorithm.FIXED_WINDOW),
    ]
    
    print("\n=== Rate Limiter Benchmarks ===\n")
    
    for name, algo in algorithms:
        config = RateLimitConfig(
            max_requests=10000,
            time_window=60,
            algorithm=algo
        )
        limiter = RateLimiterFactory.create(config)
        
        start = time.time()
        for i in range(100000):
            limiter.is_allowed(f'client_{i % 1000}')
        elapsed = time.time() - start
        
        print(f"{name:20} - 100,000 requests in {elapsed:.3f}s "
              f"({100000/elapsed:,.0f} req/s)")


if __name__ == '__main__':
    # Run unit tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run benchmarks
    run_benchmarks()
