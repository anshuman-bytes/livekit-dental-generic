#!/usr/bin/env python3
"""
Multi-Organization Testing Script for LiveKit Dental Agent

This script helps test the agent with multiple dental practices to ensure
proper multi-tenant functionality.

Usage:
    python test_multi_org.py --customer westbury
    python test_multi_org.py --customer test-practice
    python test_multi_org.py --all
"""

import asyncio
import argparse
import logging
import sys
from typing import Dict, Any
from agent_core.agent_factory import AgentFactory
from customer_context import identify_customer_from_room, load_customer_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultiOrgTester:
    """Test agent functionality across multiple organizations"""
    
    def __init__(self):
        self.test_results = []
    
    async def test_customer_identification(self, room_name: str, expected_customer_id: str) -> bool:
        """
        Test if customer is correctly identified from room name.
        
        Args:
            room_name: Room name to test
            expected_customer_id: Expected customer ID
            
        Returns:
            True if test passed, False otherwise
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST: Customer Identification")
        logger.info(f"Room Name: {room_name}")
        logger.info(f"Expected: {expected_customer_id}")
        
        try:
            customer_id = await identify_customer_from_room(room_name, phone=None)
            
            if customer_id == expected_customer_id:
                logger.info(f"✅ PASS: Correctly identified as '{customer_id}'")
                return True
            else:
                logger.error(f"❌ FAIL: Got '{customer_id}', expected '{expected_customer_id}'")
                return False
        except Exception as e:
            logger.error(f"❌ FAIL: Exception occurred: {e}")
            return False
    
    async def test_config_loading(self, customer_id: str, expected_fields: list) -> bool:
        """
        Test if customer config loads correctly with all required fields.
        
        Args:
            customer_id: Customer ID to load config for
            expected_fields: List of required field names
            
        Returns:
            True if test passed, False otherwise
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST: Config Loading")
        logger.info(f"Customer: {customer_id}")
        logger.info(f"Expected fields: {expected_fields}")
        
        try:
            config = await load_customer_config(customer_id)
            
            # Check for required fields
            missing_fields = []
            for field in expected_fields:
                if field not in config:
                    missing_fields.append(field)
            
            if not missing_fields:
                logger.info(f"✅ PASS: All required fields present")
                logger.info(f"   Customer name: {config.get('customer', {}).get('name', 'N/A')}")
                logger.info(f"   Consultation types: {len(config.get('consultation_types', {}))}")
                logger.info(f"   Doctors defined: {len(config.get('doctors', {}))}")
                return True
            else:
                logger.error(f"❌ FAIL: Missing fields: {missing_fields}")
                return False
        except Exception as e:
            logger.error(f"❌ FAIL: Exception occurred: {e}")
            return False
    
    async def test_agent_factory(self, room_name: str, expected_customer_id: str) -> bool:
        """
        Test if AgentFactory creates agent session correctly.
        
        Args:
            room_name: Room name for session
            expected_customer_id: Expected customer ID
            
        Returns:
            True if test passed, False otherwise
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST: Agent Factory")
        logger.info(f"Room Name: {room_name}")
        
        try:
            session_metadata = {"room_name": room_name, "phone": "+447000000000"}
            agent_session = await AgentFactory.create_agent(session_metadata)
            
            # Verify customer ID
            if agent_session.customer_id != expected_customer_id:
                logger.error(f"❌ FAIL: Customer ID mismatch")
                logger.error(f"   Got: {agent_session.customer_id}")
                logger.error(f"   Expected: {expected_customer_id}")
                return False
            
            # Verify config loaded
            if not agent_session.config:
                logger.error(f"❌ FAIL: Config not loaded")
                return False
            
            customer_name = agent_session.config.get('customer', {}).get('name', 'N/A')
            logger.info(f"✅ PASS: Agent session created")
            logger.info(f"   Customer ID: {agent_session.customer_id}")
            logger.info(f"   Customer Name: {customer_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ FAIL: Exception occurred: {e}")
            return False
    
    async def test_recording_url(self, customer_id: str, room_name: str) -> bool:
        """
        Test if recording URL is correctly generated for customer.
        
        Args:
            customer_id: Customer ID
            room_name: Room name
            
        Returns:
            True if test passed, False otherwise
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST: Recording URL Generation")
        logger.info(f"Customer: {customer_id}")
        logger.info(f"Room: {room_name}")
        
        try:
            from customer_context import get_recording_url
            config = await load_customer_config(customer_id)
            recording_url = get_recording_url(config, room_name)
            
            # Verify customer-specific path
            if customer_id in recording_url or config.get('azure_storage', {}).get('folder', '') in recording_url:
                logger.info(f"✅ PASS: Recording URL generated")
                logger.info(f"   URL: {recording_url}")
                return True
            else:
                logger.error(f"❌ FAIL: Recording URL doesn't contain customer identifier")
                logger.error(f"   URL: {recording_url}")
                return False
                
        except Exception as e:
            logger.error(f"❌ FAIL: Exception occurred: {e}")
            return False
    
    async def test_cache_functionality(self, customer_id: str) -> bool:
        """
        Test if config caching works correctly.
        
        Args:
            customer_id: Customer ID to test
            
        Returns:
            True if test passed, False otherwise
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST: Config Caching")
        logger.info(f"Customer: {customer_id}")
        
        try:
            # Clear cache first
            AgentFactory.clear_cache(customer_id)
            
            # First call - should be cache miss
            session_metadata = {"room_name": f"{customer_id}-test-1", "phone": "+447000000000"}
            agent1 = await AgentFactory.create_agent(session_metadata)
            
            # Second call - should be cache hit
            session_metadata2 = {"room_name": f"{customer_id}-test-2", "phone": "+447000000001"}
            agent2 = await AgentFactory.create_agent(session_metadata2)
            
            # Get cache stats
            stats = AgentFactory.get_cache_stats()
            
            if customer_id in stats.get('customer_ids', []):
                logger.info(f"✅ PASS: Config caching working")
                logger.info(f"   Cached customers: {stats.get('cached_customers', 0)}")
                logger.info(f"   TTL: {stats.get('ttl_seconds', 0)}s")
                return True
            else:
                logger.error(f"❌ FAIL: Customer not in cache")
                return False
                
        except Exception as e:
            logger.error(f"❌ FAIL: Exception occurred: {e}")
            return False
    
    async def run_customer_tests(self, customer_id: str, room_name_prefix: str = None) -> Dict[str, bool]:
        """
        Run all tests for a specific customer.
        
        Args:
            customer_id: Customer ID to test
            room_name_prefix: Optional room name prefix (defaults to customer_id)
            
        Returns:
            Dict of test names and their results
        """
        if room_name_prefix is None:
            room_name_prefix = customer_id
        
        room_name = f"{room_name_prefix}-smiledesk-agent-1234567890"
        
        logger.info(f"\n{'#'*60}")
        logger.info(f"# TESTING CUSTOMER: {customer_id}")
        logger.info(f"{'#'*60}")
        
        results = {}
        
        # Run tests
        results['identification'] = await self.test_customer_identification(room_name, customer_id)
        results['config_loading'] = await self.test_config_loading(
            customer_id,
            expected_fields=['customer', 'system_prompt', 'consultation_types', 'doctors', 'azure_storage']
        )
        results['agent_factory'] = await self.test_agent_factory(room_name, customer_id)
        results['recording_url'] = await self.test_recording_url(customer_id, room_name)
        results['caching'] = await self.test_cache_functionality(customer_id)
        
        # Summary
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"SUMMARY for {customer_id}:")
        logger.info(f"  Passed: {passed}/{total}")
        logger.info(f"  Failed: {total - passed}/{total}")
        
        if passed == total:
            logger.info(f"  ✅ ALL TESTS PASSED")
        else:
            logger.error(f"  ❌ SOME TESTS FAILED")
        
        return results
    
    async def run_all_tests(self, customers: list = None) -> Dict[str, Dict[str, bool]]:
        """
        Run tests for all specified customers.
        
        Args:
            customers: List of customer IDs to test (defaults to westbury and test-practice)
            
        Returns:
            Dict of customer IDs to their test results
        """
        if customers is None:
            customers = ['westbury', 'test-practice']
        
        all_results = {}
        
        for customer_id in customers:
            try:
                results = await self.run_customer_tests(customer_id)
                all_results[customer_id] = results
            except Exception as e:
                logger.error(f"❌ Failed to test customer '{customer_id}': {e}")
                all_results[customer_id] = {'error': str(e)}
        
        # Overall summary
        logger.info(f"\n{'#'*60}")
        logger.info(f"# OVERALL SUMMARY")
        logger.info(f"{'#'*60}")
        
        for customer_id, results in all_results.items():
            if 'error' in results:
                logger.error(f"{customer_id}: ERROR - {results['error']}")
            else:
                passed = sum(1 for v in results.values() if v)
                total = len(results)
                status = "✅" if passed == total else "❌"
                logger.info(f"{customer_id}: {status} {passed}/{total} tests passed")
        
        return all_results


async def main():
    """Main entry point for testing script"""
    parser = argparse.ArgumentParser(description='Multi-organization testing for LiveKit dental agent')
    parser.add_argument('--customer', type=str, help='Test specific customer ID')
    parser.add_argument('--all', action='store_true', help='Test all customers')
    parser.add_argument('--customers', type=str, nargs='+', help='List of customer IDs to test')
    
    args = parser.parse_args()
    
    tester = MultiOrgTester()
    
    try:
        if args.customer:
            # Test single customer
            await tester.run_customer_tests(args.customer)
        elif args.customers:
            # Test specified list of customers
            await tester.run_all_tests(args.customers)
        elif args.all:
            # Test default list
            await tester.run_all_tests(['westbury', 'test-practice'])
        else:
            # Default: test westbury
            logger.info("No customer specified, testing 'westbury' by default")
            await tester.run_customer_tests('westbury')
    
    except KeyboardInterrupt:
        logger.info("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\nTest failed with exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())







