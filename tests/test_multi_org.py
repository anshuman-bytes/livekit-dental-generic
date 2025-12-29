"""
Multi-Organization Testing Script for LiveKit Dental Agent

This script tests the multi-tenant functionality by simulating
different organizations and verifying customer-specific behavior.
"""

import os
import asyncio
import logging
from dotenv import load_dotenv

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_core.agent_factory import AgentFactory
from customer_context import (
    identify_customer_from_room,
    load_customer_config,
    get_customer_name,
    get_recording_url,
    get_consultation_service_mapping,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


async def test_customer_identification():
    """Test customer identification from room names"""
    logger.info(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
    logger.info(f"{Colors.HEADER}TEST 1: Customer Identification{Colors.ENDC}")
    logger.info(f"{Colors.HEADER}{'='*60}{Colors.ENDC}\n")
    
    test_cases = [
        ("westbury-smiledesk-agent-1234567890", "westbury"),
        ("test-practice-smiledesk-agent-9876543210", "test-practice"),
        ("dental2-smiledesk-agent-5555555555", "dental2"),
        ("smiledesk-agent-1111111111", os.getenv('DEFAULT_CUSTOMER_ID', 'westbury')),
    ]
    
    passed = 0
    failed = 0
    
    for room_name, expected_id in test_cases:
        try:
            customer_id = await identify_customer_from_room(room_name, None)
            if customer_id == expected_id:
                logger.info(f"{Colors.OKGREEN}✓ PASS{Colors.ENDC}: {room_name} → {customer_id}")
                passed += 1
            else:
                logger.error(f"{Colors.FAIL}✗ FAIL{Colors.ENDC}: {room_name} → Expected: {expected_id}, Got: {customer_id}")
                failed += 1
        except Exception as e:
            logger.error(f"{Colors.FAIL}✗ ERROR{Colors.ENDC}: {room_name} → {e}")
            failed += 1
    
    logger.info(f"\n{Colors.BOLD}Results: {passed} passed, {failed} failed{Colors.ENDC}\n")
    return passed, failed


async def test_config_loading():
    """Test configuration loading for different customers"""
    logger.info(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
    logger.info(f"{Colors.HEADER}TEST 2: Configuration Loading{Colors.ENDC}")
    logger.info(f"{Colors.HEADER}{'='*60}{Colors.ENDC}\n")
    
    test_customers = [
        os.getenv('DEFAULT_CUSTOMER_ID', 'westbury'),
    ]
    
    passed = 0
    failed = 0
    
    for customer_id in test_customers:
        try:
            config = await load_customer_config(customer_id)
            
            # Check required fields
            required_fields = ['customer_id', 'customer', 'system_prompt', 'consultation_types']
            missing_fields = [field for field in required_fields if field not in config]
            
            if not missing_fields:
                customer_name = get_customer_name(config)
                logger.info(f"{Colors.OKGREEN}✓ PASS{Colors.ENDC}: {customer_id} → {customer_name}")
                logger.info(f"  - System prompt length: {len(config.get('system_prompt', ''))} chars")
                logger.info(f"  - Consultation types: {len(config.get('consultation_types', {}))} types")
                logger.info(f"  - Doctors: {len(config.get('doctors', {}))} specialties")
                passed += 1
            else:
                logger.error(f"{Colors.FAIL}✗ FAIL{Colors.ENDC}: {customer_id} → Missing fields: {missing_fields}")
                failed += 1
                
        except Exception as e:
            logger.error(f"{Colors.FAIL}✗ ERROR{Colors.ENDC}: {customer_id} → {e}")
            failed += 1
    
    logger.info(f"\n{Colors.BOLD}Results: {passed} passed, {failed} failed{Colors.ENDC}\n")
    return passed, failed


async def test_agent_factory():
    """Test AgentFactory with multiple organizations"""
    logger.info(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
    logger.info(f"{Colors.HEADER}TEST 3: Agent Factory{Colors.ENDC}")
    logger.info(f"{Colors.HEADER}{'='*60}{Colors.ENDC}\n")
    
    test_sessions = [
        {
            "room_name": "westbury-smiledesk-agent-1234567890",
            "phone": "+447947254785",
            "expected_customer": "westbury"
        },
        {
            "room_name": "test-practice-smiledesk-agent-9876543210",
            "phone": "+447123456789",
            "expected_customer": "test-practice"
        },
    ]
    
    passed = 0
    failed = 0
    
    for session_metadata in test_sessions:
        try:
            agent_session = await AgentFactory.create_agent(session_metadata)
            
            if agent_session.customer_id == session_metadata["expected_customer"]:
                logger.info(f"{Colors.OKGREEN}✓ PASS{Colors.ENDC}: Room '{session_metadata['room_name'][:30]}...' → {agent_session.customer_id}")
                
                # Test config access
                customer_name = get_customer_name(agent_session.config)
                logger.info(f"  - Customer name: {customer_name}")
                
                # Test recording URL generation
                recording_url = get_recording_url(agent_session.config, session_metadata["room_name"])
                logger.info(f"  - Recording URL: {recording_url[:60]}...")
                
                passed += 1
            else:
                logger.error(f"{Colors.FAIL}✗ FAIL{Colors.ENDC}: Expected {session_metadata['expected_customer']}, got {agent_session.customer_id}")
                failed += 1
                
        except Exception as e:
            logger.error(f"{Colors.FAIL}✗ ERROR{Colors.ENDC}: {session_metadata['room_name']} → {e}")
            failed += 1
    
    logger.info(f"\n{Colors.BOLD}Results: {passed} passed, {failed} failed{Colors.ENDC}\n")
    return passed, failed


async def test_config_cache():
    """Test configuration caching"""
    logger.info(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
    logger.info(f"{Colors.HEADER}TEST 4: Configuration Caching{Colors.ENDC}")
    logger.info(f"{Colors.HEADER}{'='*60}{Colors.ENDC}\n")
    
    import time
    
    customer_id = os.getenv('DEFAULT_CUSTOMER_ID', 'westbury')
    session_metadata = {
        "room_name": f"{customer_id}-smiledesk-agent-1234567890",
        "phone": "+447947254785"
    }
    
    passed = 0
    failed = 0
    
    try:
        # Clear cache first
        AgentFactory.clear_cache()
        logger.info(f"{Colors.OKCYAN}Cache cleared{Colors.ENDC}")
        
        # First call - should fetch from API
        start = time.time()
        agent_session1 = await AgentFactory.create_agent(session_metadata)
        time1 = time.time() - start
        logger.info(f"{Colors.OKGREEN}✓ First call{Colors.ENDC}: {time1:.3f}s (expected cache miss)")
        
        # Second call - should hit cache
        start = time.time()
        agent_session2 = await AgentFactory.create_agent(session_metadata)
        time2 = time.time() - start
        logger.info(f"{Colors.OKGREEN}✓ Second call{Colors.ENDC}: {time2:.3f}s (expected cache hit)")
        
        # Check if caching improved performance
        if time2 < time1:
            logger.info(f"{Colors.OKGREEN}✓ PASS{Colors.ENDC}: Cache improved performance by {(time1-time2)/time1*100:.1f}%")
            passed += 1
        else:
            logger.warning(f"{Colors.WARNING}⚠ WARNING{Colors.ENDC}: Cache didn't improve performance")
            failed += 1
        
        # Check cache stats
        stats = AgentFactory.get_cache_stats()
        logger.info(f"{Colors.OKCYAN}Cache stats:{Colors.ENDC}")
        logger.info(f"  - Cached customers: {stats['cached_customers']}")
        logger.info(f"  - TTL: {stats['ttl_seconds']}s")
        
        passed += 1
        
    except Exception as e:
        logger.error(f"{Colors.FAIL}✗ ERROR{Colors.ENDC}: {e}")
        failed += 1
    
    logger.info(f"\n{Colors.BOLD}Results: {passed} passed, {failed} failed{Colors.ENDC}\n")
    return passed, failed


async def test_customer_specific_data():
    """Test customer-specific data isolation"""
    logger.info(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
    logger.info(f"{Colors.HEADER}TEST 5: Customer-Specific Data{Colors.ENDC}")
    logger.info(f"{Colors.HEADER}{'='*60}{Colors.ENDC}\n")
    
    customer_id = os.getenv('DEFAULT_CUSTOMER_ID', 'westbury')
    
    passed = 0
    failed = 0
    
    try:
        config = await load_customer_config(customer_id)
        
        # Test customer name
        customer_name = get_customer_name(config)
        logger.info(f"{Colors.OKGREEN}✓{Colors.ENDC} Customer name: {customer_name}")
        passed += 1
        
        # Test recording URL
        test_room = f"{customer_id}-smiledesk-agent-test123"
        recording_url = get_recording_url(config, test_room)
        if customer_id in recording_url:
            logger.info(f"{Colors.OKGREEN}✓{Colors.ENDC} Recording URL contains customer ID")
            logger.info(f"  URL: {recording_url}")
            passed += 1
        else:
            logger.error(f"{Colors.FAIL}✗{Colors.ENDC} Recording URL doesn't contain customer ID")
            failed += 1
        
        # Test consultation types
        consultation_mapping = get_consultation_service_mapping(config)
        if consultation_mapping:
            logger.info(f"{Colors.OKGREEN}✓{Colors.ENDC} Consultation types: {len(consultation_mapping)} types")
            for consultation, service_id in list(consultation_mapping.items())[:3]:
                logger.info(f"  - {consultation}: {service_id}")
            passed += 1
        else:
            logger.error(f"{Colors.FAIL}✗{Colors.ENDC} No consultation types found")
            failed += 1
        
        # Test voice configuration (if available)
        voice_config = config.get("voice", {})
        if voice_config:
            logger.info(f"{Colors.OKGREEN}✓{Colors.ENDC} Voice config found")
            logger.info(f"  - Voice ID: {voice_config.get('voice_id', 'default')}")
            logger.info(f"  - Model: {voice_config.get('model', 'default')}")
            passed += 1
        else:
            logger.info(f"{Colors.WARNING}⚠{Colors.ENDC} No voice config (will use defaults)")
        
    except Exception as e:
        logger.error(f"{Colors.FAIL}✗ ERROR{Colors.ENDC}: {e}")
        failed += 1
    
    logger.info(f"\n{Colors.BOLD}Results: {passed} passed, {failed} failed{Colors.ENDC}\n")
    return passed, failed


async def main():
    """Run all tests"""
    logger.info(f"\n{Colors.BOLD}{Colors.HEADER}")
    logger.info("=" * 60)
    logger.info(" MULTI-ORGANIZATION TESTING SUITE")
    logger.info("=" * 60)
    logger.info(f"{Colors.ENDC}\n")
    
    total_passed = 0
    total_failed = 0
    
    # Run all tests
    tests = [
        test_customer_identification,
        test_config_loading,
        test_agent_factory,
        test_config_cache,
        test_customer_specific_data,
    ]
    
    for test_func in tests:
        try:
            passed, failed = await test_func()
            total_passed += passed
            total_failed += failed
        except Exception as e:
            logger.error(f"{Colors.FAIL}Test suite error: {e}{Colors.ENDC}")
            total_failed += 1
    
    # Final summary
    logger.info(f"\n{Colors.BOLD}{Colors.HEADER}")
    logger.info("=" * 60)
    logger.info(" FINAL RESULTS")
    logger.info("=" * 60)
    logger.info(f"{Colors.ENDC}")
    logger.info(f"{Colors.OKGREEN}✓ Passed: {total_passed}{Colors.ENDC}")
    logger.info(f"{Colors.FAIL}✗ Failed: {total_failed}{Colors.ENDC}")
    logger.info(f"{Colors.BOLD}Total: {total_passed + total_failed}{Colors.ENDC}\n")
    
    if total_failed == 0:
        logger.info(f"{Colors.OKGREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! 🎉{Colors.ENDC}\n")
    else:
        logger.warning(f"{Colors.WARNING}⚠️  Some tests failed. Please review the output above.{Colors.ENDC}\n")


if __name__ == "__main__":
    asyncio.run(main())

