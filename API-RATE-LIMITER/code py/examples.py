"""
elliotoxin | 2025
Advanced Rate Limiter - Usage Examples and Demonstrations
Shows practical examples of using the rate limiter
"""

from rate_limiter import (
    RateLimitConfig, RateLimitAlgorithm,
    RateLimiterFactory, RateLimitResponse
)
import time
from datetime import datetime


def print_header(title):
    """Print formatted header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_response(response: RateLimitResponse, request_num: int):
    """Print rate limit response"""
    status = "✅ ALLOWED" if response.allowed else "❌ REJECTED"
    print(f"Request {request_num:3d}: {status} | "
          f"Remaining: {response.remaining:3d} | "
          f"In Window: {response.requests_in_window:3d}", end="")
    
    if not response.allowed:
        print(f" | Retry After: {response.retry_after}s")
    else:
        print()


def example_1_basic_token_bucket():
    """Example 1: Basic Token Bucket Rate Limiting"""
    print_header("Example 1: Basic Token Bucket")
    
    # Configuration: 10 requests per 60 seconds
    config = RateLimitConfig(
        max_requests=10,
        time_window=60,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET
    )
    
    limiter = RateLimiterFactory.create(config)
    client_id = "user_123"
    
    print("Config: 10 requests per 60 seconds")
    print("Making 15 requests in quick succession...\n")
    
    for i in range(1, 16):
        response = limiter.is_allowed(client_id)
        print_response(response, i)


def example_2_sliding_window():
    """Example 2: Precise Sliding Window Counting"""
    print_header("Example 2: Sliding Window Counter")
    
    config = RateLimitConfig(
        max_requests=5,
        time_window=10,
        algorithm=RateLimitAlgorithm.SLIDING_WINDOW
    )
    
    limiter = RateLimiterFactory.create(config)
    client_id = "api_client_456"
    
    print("Config: 5 requests per 10 seconds")
    print("Testing precise request tracking...\n")
    
    # Make 7 requests immediately
    for i in range(1, 8):
        response = limiter.is_allowed(client_id)
        print_response(response, i)
    
    # Simulate window expiration
    print("\nWaiting 11 seconds for window to expire...")
    time.sleep(11)
    
    print("Window expired. Trying again...\n")
    for i in range(8, 10):
        response = limiter.is_allowed(client_id)
        print_response(response, i)


def example_3_leaky_bucket():
    """Example 3: Traffic Smoothing with Leaky Bucket"""
    print_header("Example 3: Leaky Bucket (Traffic Smoothing)")
    
    config = RateLimitConfig(
        max_requests=5,
        time_window=10,
        algorithm=RateLimitAlgorithm.LEAKY_BUCKET
    )
    
    limiter = RateLimiterFactory.create(config)
    client_id = "streaming_client"
    
    print("Config: 5 requests per 10 seconds")
    print("Leaky Bucket smooths traffic at fixed rate\n")
    
    # Simulate burst of requests
    for i in range(1, 8):
        response = limiter.is_allowed(client_id)
        print_response(response, i)
        
        # Show queue status
        status = limiter.get_status(client_id)
        print(f"         Queue size: {status['queue_size']}/{status['max_capacity']}")


def example_4_fixed_window():
    """Example 4: Simple Fixed Window"""
    print_header("Example 4: Fixed Window Counter")
    
    config = RateLimitConfig(
        max_requests=10,
        time_window=5,
        algorithm=RateLimitAlgorithm.FIXED_WINDOW
    )
    
    limiter = RateLimiterFactory.create(config)
    client_id = "simple_api"
    
    print("Config: 10 requests per 5 seconds")
    print("Simple fixed window implementation\n")
    
    for i in range(1, 13):
        response = limiter.is_allowed(client_id)
        print_response(response, i)


def example_5_per_client_isolation():
    """Example 5: Independent Limits Per Client"""
    print_header("Example 5: Per-Client Isolation")
    
    config = RateLimitConfig(
        max_requests=5,
        time_window=10,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET
    )
    
    limiter = RateLimiterFactory.create(config)
    
    print("Config: 5 requests per 10 seconds (per client)")
    print("Each client has independent rate limit\n")
    
    clients = ["client_A", "client_B", "client_C"]
    
    for round_num in range(1, 8):
        print(f"Round {round_num}:")
        for client_id in clients:
            response = limiter.is_allowed(client_id)
            status = "✅" if response.allowed else "❌"
            print(f"  {client_id}: {status} (Remaining: {response.remaining})")
        print()


def example_6_burst_handling():
    """Example 6: Burst Traffic Handling"""
    print_header("Example 6: Burst Traffic with Token Bucket")
    
    config = RateLimitConfig(
        max_requests=100,
        time_window=60,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
        burst_size=150  # Allow burst up to 150
    )
    
    limiter = RateLimiterFactory.create(config)
    client_id = "burst_client"
    
    print("Config: 100 req/min, burst up to 150 tokens")
    print("Token Bucket handles burst spikes well\n")
    
    # Simulate burst
    print("Sending burst of 120 requests...")
    allowed = 0
    for i in range(1, 121):
        response = limiter.is_allowed(client_id)
        if response.allowed:
            allowed += 1
        if i % 30 == 0:
            print(f"  {i} requests: {allowed} allowed")
    
    print(f"\nTotal burst: 120 requests")
    print(f"Allowed: {allowed} requests")
    print(f"Rejected: {120 - allowed} requests")


def example_7_status_monitoring():
    """Example 7: Monitoring Rate Limit Status"""
    print_header("Example 7: Status Monitoring")
    
    algorithms = [
        ("Token Bucket", RateLimitAlgorithm.TOKEN_BUCKET),
        ("Sliding Window", RateLimitAlgorithm.SLIDING_WINDOW),
        ("Leaky Bucket", RateLimitAlgorithm.LEAKY_BUCKET),
        ("Fixed Window", RateLimitAlgorithm.FIXED_WINDOW),
    ]
    
    for name, algo in algorithms:
        config = RateLimitConfig(
            max_requests=10,
            time_window=60,
            algorithm=algo
        )
        
        limiter = RateLimiterFactory.create(config)
        client_id = "status_client"
        
        # Make some requests
        for _ in range(5):
            limiter.is_allowed(client_id)
        
        # Get status
        status = limiter.get_status(client_id)
        
        print(f"\n{name}:")
        for key, value in status.items():
            print(f"  {key}: {value}")


def example_8_reset_functionality():
    """Example 8: Resetting Rate Limits"""
    print_header("Example 8: Manual Reset")
    
    config = RateLimitConfig(
        max_requests=5,
        time_window=60,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET
    )
    
    limiter = RateLimiterFactory.create(config)
    client_id = "reset_client"
    
    print("Config: 5 requests per 60 seconds\n")
    
    # Use all tokens
    print("Using 5 requests...")
    for i in range(5):
        response = limiter.is_allowed(client_id)
        print(f"  Request {i+1}: {'✅' if response.allowed else '❌'}")
    
    # Try one more - should be rejected
    response = limiter.is_allowed(client_id)
    print(f"\nRequest 6: {'✅' if response.allowed else '❌'} (Expected: ❌)")
    
    # Reset
    print("\nResetting rate limit...")
    limiter.reset(client_id)
    
    # Try again
    response = limiter.is_allowed(client_id)
    print(f"Request 6 (after reset): {'✅' if response.allowed else '❌'} (Expected: ✅)")


def example_9_comparison():
    """Example 9: Algorithm Comparison"""
    print_header("Example 9: Algorithm Comparison")
    
    print("Sending 20 requests quickly, then waiting 5 seconds\n")
    
    algorithms = [
        ("Token Bucket", RateLimitAlgorithm.TOKEN_BUCKET),
        ("Sliding Window", RateLimitAlgorithm.SLIDING_WINDOW),
        ("Leaky Bucket", RateLimitAlgorithm.LEAKY_BUCKET),
        ("Fixed Window", RateLimitAlgorithm.FIXED_WINDOW),
    ]
    
    for name, algo in algorithms:
        config = RateLimitConfig(
            max_requests=10,
            time_window=10,
            algorithm=algo
        )
        
        limiter = RateLimiterFactory.create(config)
        client_id = f"comp_{name}"
        
        # Send 20 requests quickly
        allowed_phase1 = 0
        for _ in range(20):
            response = limiter.is_allowed(client_id)
            if response.allowed:
                allowed_phase1 += 1
        
        # Wait 5 seconds
        time.sleep(5)
        
        # Send 5 more requests
        allowed_phase2 = 0
        for _ in range(5):
            response = limiter.is_allowed(client_id)
            if response.allowed:
                allowed_phase2 += 1
        
        print(f"{name:20} - Phase 1: {allowed_phase1:2d}/20 | "
              f"Phase 2: {allowed_phase2:2d}/5 | Total: {allowed_phase1 + allowed_phase2:2d}/25")


def example_10_real_world_scenario():
    """Example 10: Real-World API Scenario"""
    print_header("Example 10: Real-World API Scenario")
    
    print("Scenario: API with different endpoints having different limits\n")
    
    # Create limiters for different endpoints
    public_config = RateLimitConfig(
        max_requests=100,
        time_window=60,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET
    )
    
    premium_config = RateLimitConfig(
        max_requests=1000,
        time_window=3600,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET
    )
    
    write_config = RateLimitConfig(
        max_requests=10,
        time_window=60,
        algorithm=RateLimitAlgorithm.FIXED_WINDOW
    )
    
    public_limiter = RateLimiterFactory.create(public_config)
    premium_limiter = RateLimiterFactory.create(premium_config)
    write_limiter = RateLimiterFactory.create(write_config)
    
    # Simulate requests from two clients
    clients = ["free_user", "premium_user"]
    
    print("Endpoint: /api/public (100 req/min)")
    for client in clients:
        response = public_limiter.is_allowed(client)
        status = "✅" if response.allowed else "❌"
        print(f"  {client}: {status}")
    
    print("\nEndpoint: /api/premium (1000 req/hour)")
    for client in clients:
        response = premium_limiter.is_allowed(client)
        status = "✅" if response.allowed else "❌"
        print(f"  {client}: {status}")
    
    print("\nEndpoint: /api/write (10 req/min - strict)")
    for client in clients:
        response = write_limiter.is_allowed(client)
        status = "✅" if response.allowed else "❌"
        print(f"  {client}: {status}")


def main():
    """Run all examples"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*10 + "ADVANCED RATE LIMITER - EXAMPLES" + " "*16 + "║")
    print("╚" + "="*58 + "╝")
    
    examples = [
        example_1_basic_token_bucket,
        example_2_sliding_window,
        example_3_leaky_bucket,
        example_4_fixed_window,
        example_5_per_client_isolation,
        example_6_burst_handling,
        example_7_status_monitoring,
        example_8_reset_functionality,
        example_9_comparison,
        example_10_real_world_scenario,
    ]
    
    for example_func in examples:
        try:
            example_func()
        except Exception as e:
            print(f"\n❌ Error in {example_func.__name__}: {e}\n")
        
        input("\nPress Enter to continue to next example...")
    
    print("\n" + "="*60)
    print("All examples completed!")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
