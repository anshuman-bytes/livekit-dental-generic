# agent_factory.py

import asyncio
import time
import logging
import os
from typing import Dict, Any, Optional
from customer_context import identify_org_from_room, load_org_config

logger = logging.getLogger("smiledesk-agent")


class ConfigCache:
    """
    TTL-based cache for organization configurations.
    Reduces backend API calls and improves performance.
    """
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize config cache.
        
        Args:
            ttl_seconds: Time-to-live in seconds (default: 300 = 5 minutes)
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, float] = {}
        self.ttl_seconds = ttl_seconds
        logger.info(f"ConfigCache initialized with TTL: {ttl_seconds}s")
    
    def get(self, org_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached config if not expired.
        
        Args:
            org_id: Organization identifier
            
        Returns:
            Cached config dict or None if expired/not found
        """
        if org_id not in self._cache:
            return None
        
        # Check TTL
        age = time.time() - self._timestamps[org_id]
        if age > self.ttl_seconds:
            # Expired - remove from cache
            logger.info(f"Cache expired for {org_id} (age: {age:.1f}s)")
            del self._cache[org_id]
            del self._timestamps[org_id]
            return None
        
        logger.info(f"Cache hit for {org_id} (age: {age:.1f}s)")
        return self._cache[org_id]
    
    def set(self, org_id: str, config: Dict[str, Any]):
        """
        Cache config with current timestamp.
        
        Args:
            org_id: Organization identifier
            config: Configuration dictionary to cache
        """
        self._cache[org_id] = config
        self._timestamps[org_id] = time.time()
        logger.info(f"Config cached for {org_id}")
    
    def clear(self, org_id: Optional[str] = None):
        """
        Clear cache for specific organization or all.
        
        Args:
            org_id: Specific organization to clear, or None for all
        """
        if org_id:
            self._cache.pop(org_id, None)
            self._timestamps.pop(org_id, None)
            logger.info(f"Cache cleared for {org_id}")
        else:
            self._cache.clear()
            self._timestamps.clear()
            logger.info("All cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cached_organizations": len(self._cache),
            "org_ids": list(self._cache.keys()),
            "customer_ids": list(self._cache.keys()),  # Backward compatibility
            "cached_customers": len(self._cache),  # Backward compatibility
            "ttl_seconds": self.ttl_seconds
        }


# Global cache instance with TTL from environment variable
_config_cache = ConfigCache(ttl_seconds=int(os.getenv('CONFIG_CACHE_TTL', '300')))


class AgentFactory:
    """
    Factory for creating agent sessions with organization-specific configurations.
    Implements caching to reduce backend API calls.
    """
    
    @staticmethod
    async def create_agent(session_metadata):
        """
        Create agent session with organization config (cached or fetched).
        
        Args:
            session_metadata: Dict with 'room_name' and 'phone'
            
        Returns:
            AgentSession with org_id and config
        """
        room_name = session_metadata.get('room_name')
        phone = session_metadata.get('phone')
        
        # Step 1: Identify organization
        org_id = await identify_org_from_room(room_name, phone)
        logger.info(f"Creating agent for organization: {org_id}")
        
        # Step 2: Try cache first
        org_config = _config_cache.get(org_id)
        
        if org_config is None:
            # Cache miss - fetch from backend API
            logger.info(f"Cache miss for {org_id}, fetching from backend API")
            org_config = await load_org_config(org_id)
            
            # Cache the fetched config
            _config_cache.set(org_id, org_config)
            logger.info(f"Config fetched and cached for {org_id}")
        
        # Step 3: Return agent session with config
        return AgentSession(org_id, org_config)
    
    @staticmethod
    def clear_cache(org_id: Optional[str] = None):
        """
        Clear config cache for specific organization or all.
        
        Args:
            org_id: Organization to clear, or None for all
        """
        _config_cache.clear(org_id)
    
    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """Get cache statistics."""
        return _config_cache.get_stats()


class AgentSession:
    """
    Agent session object containing organization configuration.
    
    Maintains backward compatibility by also exposing customer_id as an alias.
    """
    def __init__(self, org_id: str, config: Dict[str, Any]):
        self.org_id = org_id
        self.organization_id = org_id  # Alias for clarity
        self.customer_id = org_id  # Backward compatibility alias
        self.config = config
        # You can add more fields as needed, e.g. prompts, storage, etc.
