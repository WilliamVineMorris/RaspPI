#!/usr/bin/env python3
"""
Test async handling in Flask context
"""

import asyncio
import concurrent.futures

async def mock_async_function(param):
    """Mock async function for testing"""
    await asyncio.sleep(0.1)  # Simulate async work
    return f"Result: {param}"

def test_async_execution():
    """Test the async execution approach used in web interface"""
    
    print("Testing async execution methods...")
    
    # Method 1: asyncio.run (preferred for new event loop)
    try:
        result1 = asyncio.run(mock_async_function("test1"))
        print(f"Method 1 (asyncio.run): {result1}")
    except Exception as e:
        print(f"Method 1 failed: {e}")
    
    # Method 2: ThreadPoolExecutor (for existing event loop)
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, mock_async_function("test2"))
            result2 = future.result(timeout=5.0)
            print(f"Method 2 (ThreadPoolExecutor): {result2}")
    except Exception as e:
        print(f"Method 2 failed: {e}")
    
    # Method 3: Get existing loop and run_until_complete (if no running loop)
    try:
        loop = asyncio.new_event_loop()
        result3 = loop.run_until_complete(mock_async_function("test3"))
        loop.close()
        print(f"Method 3 (new event loop): {result3}")
    except Exception as e:
        print(f"Method 3 failed: {e}")
        
    print("Async execution test completed!")

if __name__ == "__main__":
    test_async_execution()