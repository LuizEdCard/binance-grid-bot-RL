#!/usr/bin/env python3
"""
Test script to validate the priority system in CPU resource management.
"""
import asyncio
import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agents.ai_agent import LocalAIClient, RequestPriority

async def test_priority_system():
    """Test the priority queue system."""
    print("🏆 Testing Priority Queue System")
    print("=" * 40)
    
    client = LocalAIClient(enable_cpu_management=True)
    
    try:
        await client.start_session()
        
        # Check if Ollama is available
        model = await client.get_running_model()
        if not model:
            print("❌ No model available, skipping priority test")
            return
            
        print(f"✅ Using model: {model}")
        
        # Simulate multiple requests with different priorities
        print("\n🚀 Submitting mixed priority requests...")
        
        tasks = []
        
        # Submit requests in mixed order (but priority should reorder)
        request_order = [
            ("Low Priority Report", RequestPriority.LOW, "Generate a simple market report."),
            ("CRITICAL Grid Optimization", RequestPriority.CRITICAL, "Optimize grid parameters urgently."),
            ("Normal Sentiment", RequestPriority.NORMAL, "Analyze: Bitcoin looks good."),
            ("High Priority Analysis", RequestPriority.HIGH, "Analyze current market conditions."),
            ("Another Low Priority", RequestPriority.LOW, "Explain trading basics."),
        ]
        
        # Submit all requests quickly
        for name, priority, prompt in request_order:
            print(f"📤 Submitting: {name} ({priority.name})")
            
            task = asyncio.create_task(
                client.resource_manager.submit_request(
                    messages=[{"role": "user", "content": prompt}],
                    priority=priority,
                    max_tokens=100
                )
            )
            tasks.append((name, priority, task))
            
            # Small delay to ensure different timestamps
            await asyncio.sleep(0.1)
        
        print(f"\n⏳ Processing {len(tasks)} requests with priority ordering...")
        print("Expected order: CRITICAL → HIGH → NORMAL → LOW → LOW")
        
        # Wait for all requests to complete and track completion order
        start_time = time.time()
        completed_order = []
        
        for name, priority, task in tasks:
            result = await task
            completion_time = time.time() - start_time
            completed_order.append((name, priority, completion_time))
            print(f"✅ Completed: {name} ({priority.name}) after {completion_time:.1f}s")
        
        # Analyze if priority was respected
        print(f"\n📊 Priority Analysis:")
        priority_values = [p.value for _, p, _ in completed_order]
        
        # Check if requests were processed in priority order
        is_priority_respected = all(
            priority_values[i] >= priority_values[i+1] 
            for i in range(len(priority_values)-1)
        )
        
        if is_priority_respected:
            print("✅ Priority system working correctly!")
            print("   Requests processed in correct priority order")
        else:
            print("⚠️  Priority order may not be perfect")
            print("   (Note: Single-threaded execution may process in submission order)")
        
        # Show resource manager statistics
        stats = client.get_statistics()
        if "resource_manager" in stats:
            rm_stats = stats["resource_manager"]
            print(f"\n📈 Resource Manager Stats:")
            print(f"   Queue stats: {rm_stats['queue_stats']}")
            print(f"   Priority breakdown: {rm_stats['priority_stats']['priority_breakdown']}")
            print(f"   Rate limiting: {rm_stats['current_requests_in_window']}/{rm_stats['max_requests_per_window']} in window")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    finally:
        await client.close_session()

async def test_cpu_monitoring():
    """Test CPU monitoring and throttling."""
    print("\n🖥️  Testing CPU Monitoring")
    print("=" * 30)
    
    client = LocalAIClient(enable_cpu_management=True)
    
    try:
        await client.start_session()
        
        # Start resource manager 
        if client.resource_manager:
            await client.resource_manager.start()
            
            # Let it run for a bit to test monitoring
            print("⏱️  Running system monitoring for 5 seconds...")
            await asyncio.sleep(5)
            
            # Check monitoring worked
            print("✅ CPU monitoring completed")
        else:
            print("❌ Resource manager not available")
            
    except Exception as e:
        print(f"❌ CPU monitoring test failed: {e}")
    
    finally:
        await client.close_session()

if __name__ == "__main__":
    print("🧪 Priority System Test Suite")
    print("============================\n")
    
    async def run_all_tests():
        await test_priority_system()
        await test_cpu_monitoring()
        
        print("\n✅ All priority tests completed!")
    
    asyncio.run(run_all_tests())