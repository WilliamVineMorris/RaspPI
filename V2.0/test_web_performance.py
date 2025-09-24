#!/usr/bin/env python3
"""
Web UI Performance Test - Measure response times for web interface
"""

import asyncio
import aiohttp
import time
import statistics
import sys
from typing import List, Dict

class WebUIPerformanceTester:
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=10)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_status_endpoint(self, num_requests: int = 10) -> List[float]:
        """Test the /api/status endpoint response times"""
        response_times = []
        
        print(f"🔬 Testing /api/status endpoint ({num_requests} requests)...")
        
        for i in range(num_requests):
            start_time = time.time()
            try:
                async with self.session.get(f"{self.base_url}/api/status") as response:
                    await response.json()
                    response_time = (time.time() - start_time) * 1000
                    response_times.append(response_time)
                    print(f"  Request {i+1}: {response_time:.1f}ms")
            except Exception as e:
                print(f"  Request {i+1}: ERROR - {e}")
            
            # Small delay between requests
            await asyncio.sleep(0.1)
        
        return response_times
    
    async def test_jog_command(self, num_commands: int = 5) -> List[float]:
        """Test jog command response times"""
        response_times = []
        
        print(f"🔬 Testing jog commands ({num_commands} commands)...")
        
        jog_payload = {
            "x": 0.0,
            "y": 0.0, 
            "z": 0.1,  # Small Z movement
            "c": 0.0,
            "speed": 10.0
        }
        
        for i in range(num_commands):
            start_time = time.time()
            try:
                async with self.session.post(
                    f"{self.base_url}/api/jog",
                    json=jog_payload
                ) as response:
                    await response.json()
                    response_time = (time.time() - start_time) * 1000
                    response_times.append(response_time)
                    print(f"  Jog {i+1}: {response_time:.1f}ms")
            except Exception as e:
                print(f"  Jog {i+1}: ERROR - {e}")
            
            # Wait between jog commands
            await asyncio.sleep(1.0)
        
        return response_times
    
    def analyze_results(self, response_times: List[float], test_name: str):
        """Analyze and report response time statistics"""
        if not response_times:
            print(f"❌ No valid responses for {test_name}")
            return
        
        avg_time = statistics.mean(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        median_time = statistics.median(response_times)
        
        print(f"\n📊 {test_name} Results:")
        print(f"  Average: {avg_time:.1f}ms")
        print(f"  Median:  {median_time:.1f}ms")
        print(f"  Min:     {min_time:.1f}ms")
        print(f"  Max:     {max_time:.1f}ms")
        
        # Performance classification
        if avg_time < 100:
            print(f"  ✅ EXCELLENT performance (<100ms average)")
        elif avg_time < 250:
            print(f"  ✅ GOOD performance (<250ms average)")
        elif avg_time < 500:
            print(f"  ⚠️  FAIR performance (<500ms average)")
        else:
            print(f"  ❌ SLOW performance (>{avg_time:.0f}ms average)")

async def main():
    print("🔬 Web UI Performance Testing")
    print("Testing web interface response times...")
    
    try:
        async with WebUIPerformanceTester() as tester:
            # Test status endpoint
            status_times = await tester.test_status_endpoint(10)
            tester.analyze_results(status_times, "Status API")
            
            print("\n" + "="*50)
            
            # Test jog commands  
            jog_times = await tester.test_jog_command(3)
            tester.analyze_results(jog_times, "Jog Commands")
            
            print("\n🎯 Performance Test Complete!")
            
            # Overall assessment
            if status_times and jog_times:
                avg_status = statistics.mean(status_times)
                avg_jog = statistics.mean(jog_times)
                
                print(f"\n📈 Overall Assessment:")
                print(f"  Status polling: {avg_status:.1f}ms average")
                print(f"  Movement commands: {avg_jog:.1f}ms average")
                
                if avg_status < 100 and avg_jog < 500:
                    print(f"  ✅ Web UI performance is EXCELLENT for real-time control")
                elif avg_status < 250 and avg_jog < 1000:
                    print(f"  ✅ Web UI performance is GOOD for interactive use")
                else:
                    print(f"  ⚠️  Web UI may feel sluggish - optimization needed")
    
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("Make sure the web interface is running on localhost:5000")

if __name__ == "__main__":
    asyncio.run(main())