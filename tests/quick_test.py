"""
Quick Test Script for Multi-Tenant Agent

Run this to quickly verify your multi-tenant setup is working.
"""

import os
import asyncio
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_core.agent_factory import AgentFactory
from customer_context import get_customer_name, get_recording_url

load_dotenv()


async def quick_test():
    """Quick smoke test for multi-tenant agent"""
    print("\n🔍 Quick Multi-Tenant Test\n")
    print("=" * 50)
    
    # Test customer identification
    customer_id = os.getenv('DEFAULT_CUSTOMER_ID', 'westbury')
    print(f"\n1. Testing customer: {customer_id}")
    
    # Create agent session
    session_metadata = {
        "room_name": f"{customer_id}-smiledesk-agent-test123",
        "phone": "+447947254785"
    }
    
    print(f"   Room: {session_metadata['room_name']}")
    
    try:
        # Create agent
        agent_session = await AgentFactory.create_agent(session_metadata)
        print(f"   ✓ Agent created successfully")
        print(f"   ✓ Customer ID: {agent_session.customer_id}")
        
        # Get customer name
        customer_name = get_customer_name(agent_session.config)
        print(f"   ✓ Customer name: {customer_name}")
        
        # Get recording URL
        recording_url = get_recording_url(agent_session.config, session_metadata['room_name'])
        print(f"   ✓ Recording URL: {recording_url[:60]}...")
        
        # Check cache
        stats = AgentFactory.get_cache_stats()
        print(f"\n2. Cache Statistics:")
        print(f"   ✓ Cached customers: {stats['cached_customers']}")
        print(f"   ✓ TTL: {stats['ttl_seconds']}s")
        
        print("\n" + "=" * 50)
        print("✅ Quick test PASSED!")
        print("=" * 50 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test FAILED: {e}\n")
        raise


if __name__ == "__main__":
    asyncio.run(quick_test())

