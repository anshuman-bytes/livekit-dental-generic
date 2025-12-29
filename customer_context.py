"""
Organization Context Module for Multi-Tenant Agent Support

This module provides utilities for managing organization context in the LiveKit agent.
It handles organization identification, configuration loading, and provides helper
functions for organization-specific operations.

Key Functions:
- identify_org_from_room(): Determine org_id from room name
- load_org_config(): Load full organization configuration from backend API
- get_recording_url(): Generate organization-specific recording URL
"""

import os
import logging
import aiohttp
import asyncio
from typing import Optional, Dict, Any

logger = logging.getLogger("smiledesk-agent")

# Backend API configuration
BACKEND_API = os.getenv("BACKEND_API", "http://localhost:8000")
BACKEND_API_TOKEN = os.getenv("BACKEND_API_TOKEN", "")
# Backward compatibility: support both DEFAULT_ORG_ID and DEFAULT_CUSTOMER_ID
DEFAULT_ORG_ID = os.getenv("DEFAULT_ORG_ID") or os.getenv("DEFAULT_ORGANIZATION_ID") or os.getenv("DEFAULT_CUSTOMER_ID", "westbury")

# API timeout configuration (in seconds)
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "10"))
API_RETRY_MAX_ATTEMPTS = int(os.getenv("API_RETRY_MAX_ATTEMPTS", "3"))
API_RETRY_INITIAL_DELAY = float(os.getenv("API_RETRY_INITIAL_DELAY", "1.0"))

# Azure storage defaults
DEFAULT_AZURE_CONTAINER = "dental"
DEFAULT_AZURE_BASE_URL = "https://oaipublic.blob.core.windows.net"


async def identify_org_from_room(
    room_name: str,
    phone: Optional[str] = None
) -> str:
    """
    Identify organization from room name.
    
    Priority:
    1. Extract from room name prefix (e.g., "westbury-smiledesk-agent-123" -> "westbury")
    2. Default to DEFAULT_ORG_ID environment variable
    
    Note: The /customer/identify endpoint no longer exists in the new API structure.
    Organization identification is done via room name parsing only.
    
    Args:
        room_name: LiveKit room name
        phone: Optional phone number from SIP attributes (not used in new API, kept for compatibility)
    
    Returns:
        org_id string
    """
    org_id = None
    
    # Method 1: Try to extract from room name prefix
    if room_name:
        # Room names are typically formatted as: {org_id}-smiledesk-agent-{timestamp}
        # or: {org_id}-{something}-{timestamp}
        parts = room_name.lower().split("-")
        if len(parts) >= 1:
            potential_org_id = parts[0]
            # Common prefixes that indicate a valid org_id pattern
            # Skip if it looks like a generic prefix
            if potential_org_id not in ["room", "call", "test", "dev", "prod", "smiledesk"]:
                org_id = potential_org_id
                logger.info(f"Extracted org_id from room name prefix: {org_id}")
    
    # Method 2: Fall back to default
    if not org_id:
        org_id = DEFAULT_ORG_ID
        logger.info(f"Using default org_id: {org_id}")
    
    return org_id


async def load_org_config(org_id: str) -> Dict[str, Any]:
    """
    Load complete organization configuration from backend API.
    
    This loads configuration from multiple endpoints:
    - GET /organization (BE-030): Organization details (name, address, contact, etc.)
    - GET /ai-receptionist/config (BE-034): AI receptionist configuration (system prompt, voice, etc.)
    
    Args:
        org_id: Organization identifier (e.g., 'westbury')
    
    Returns:
        Dictionary with complete organization configuration
    
    Raises:
        ValueError: If org_id is invalid or organization not found
        ConnectionError: If network error occurs after retries
        Exception: If configuration cannot be loaded
    """
    if not org_id or not org_id.strip():
        raise ValueError("org_id cannot be empty")
    
    timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
    headers = {}
    if BACKEND_API_TOKEN:
        headers["Authorization"] = f"Bearer {BACKEND_API_TOKEN}"
    # Add organization ID header (backend will use this to identify the organization)
    headers["X-Organization-ID"] = org_id
    
    # URLs for the new API endpoints
    org_url = f"{BACKEND_API}/organization"  # BE-030
    ai_config_url = f"{BACKEND_API}/ai-receptionist/config"  # BE-034
    
    config = {}
    last_exception = None
    
    # Retry logic with exponential backoff
    for attempt in range(API_RETRY_MAX_ATTEMPTS):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Step 1: Get organization details
                async with session.get(org_url, headers=headers) as org_response:
                    if org_response.status == 200:
                        org_data = await org_response.json()
                        # Merge organization data into config
                        config.update(org_data)
                        # Store org_id in config for backward compatibility
                        config["org_id"] = org_id
                        config["organization_id"] = org_id
                        # For backward compatibility, also store as customer_id
                        config["customer_id"] = org_id
                        logger.info(f"Loaded organization details for: {org_id}")
                    elif org_response.status == 404:
                        logger.error(f"Organization '{org_id}' not found in backend")
                        raise ValueError(f"Organization '{org_id}' not found")
                    else:
                        error_text = await org_response.text()
                        logger.warning(f"Failed to load organization config: {org_response.status} - {error_text} (attempt {attempt + 1}/{API_RETRY_MAX_ATTEMPTS})")
                        if attempt < API_RETRY_MAX_ATTEMPTS - 1:
                            delay = API_RETRY_INITIAL_DELAY * (2 ** attempt)
                            await asyncio.sleep(delay)
                        else:
                            raise Exception(f"Failed to load organization config: {org_response.status}")
                
                # Step 2: Get AI receptionist configuration
                async with session.get(ai_config_url, headers=headers) as ai_response:
                    if ai_response.status == 200:
                        ai_data = await ai_response.json()
                        # Store AI config in nested structure for clarity
                        config["ai_receptionist"] = ai_data
                        # Extract system prompt to top level for easy access
                        config["system_prompt"] = ai_data.get("system_prompt", "")
                        # Extract voice config to top level for easy access
                        config["voice"] = ai_data.get("voice", {})
                        # Extract agent name
                        config["agent_name"] = ai_data.get("agent_name", "Emma")
                        # Extract greeting if available
                        if "greeting" in ai_data:
                            config["greeting"] = ai_data.get("greeting")
                        logger.info(f"Loaded AI receptionist config for: {org_id}")
                    else:
                        logger.warning(f"Failed to load AI receptionist config: {ai_response.status} (attempt {attempt + 1}/{API_RETRY_MAX_ATTEMPTS})")
                        # AI config failure is not critical, continue with org config only
                        if ai_response.status == 404:
                            logger.warning("AI receptionist config not found, using defaults")
                            config["system_prompt"] = ""
                            config["ai_receptionist"] = {}
                        elif attempt < API_RETRY_MAX_ATTEMPTS - 1:
                            delay = API_RETRY_INITIAL_DELAY * (2 ** attempt)
                            await asyncio.sleep(delay)
                
                # If we got here, we have at least organization config
                if config:
                    logger.info(f"Successfully loaded configuration for organization: {org_id}")
                    return config
                else:
                    raise Exception("No configuration data received")
        
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_exception = e
            logger.warning(f"Network error loading org config (attempt {attempt + 1}/{API_RETRY_MAX_ATTEMPTS}): {e}")
            if attempt < API_RETRY_MAX_ATTEMPTS - 1:
                delay = API_RETRY_INITIAL_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)
            else:
                logger.error(f"Failed to load org config after {API_RETRY_MAX_ATTEMPTS} attempts: {last_exception}")
                raise ConnectionError(f"Network error loading org config after {API_RETRY_MAX_ATTEMPTS} attempts: {last_exception}")
        
        except (ValueError, Exception) as e:
            # Don't retry for client errors (404, validation errors, etc.)
            raise
    
    # Should never reach here, but just in case
    raise Exception(f"Failed to load org config for {org_id} after {API_RETRY_MAX_ATTEMPTS} attempts")


async def get_system_prompt_from_api(org_id: str) -> str:
    """
    Get system prompt for an organization from the backend API.
    
    Uses GET /ai-receptionist/config endpoint (BE-034).
    
    Args:
        org_id: Organization identifier
    
    Returns:
        System prompt string (empty string if not found or error occurs)
    """
    if not org_id or not org_id.strip():
        logger.error("org_id cannot be empty")
        return ""
    
    timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
    headers = {}
    if BACKEND_API_TOKEN:
        headers["Authorization"] = f"Bearer {BACKEND_API_TOKEN}"
    headers["X-Organization-ID"] = org_id
    
    url = f"{BACKEND_API}/ai-receptionist/config"  # BE-034
    last_exception = None
    
    # Retry logic with exponential backoff
    for attempt in range(API_RETRY_MAX_ATTEMPTS):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        prompt = data.get("system_prompt", "")
                        if prompt:
                            logger.info(f"Retrieved system prompt for {org_id}")
                        return prompt
                    else:
                        logger.warning(f"Failed to get system prompt: {response.status} (attempt {attempt + 1}/{API_RETRY_MAX_ATTEMPTS})")
                        if attempt < API_RETRY_MAX_ATTEMPTS - 1:
                            delay = API_RETRY_INITIAL_DELAY * (2 ** attempt)
                            await asyncio.sleep(delay)
                        else:
                            return ""
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_exception = e
            logger.warning(f"Network error getting system prompt (attempt {attempt + 1}/{API_RETRY_MAX_ATTEMPTS}): {e}")
            if attempt < API_RETRY_MAX_ATTEMPTS - 1:
                delay = API_RETRY_INITIAL_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)
            else:
                logger.error(f"Failed to get system prompt after {API_RETRY_MAX_ATTEMPTS} attempts: {last_exception}")
                return ""
        except Exception as e:
            logger.error(f"Unexpected error getting system prompt for {org_id}: {e}")
            return ""
    
    return ""


def get_recording_url(org_config: Dict[str, Any], room_name: str) -> str:
    """
    Generate organization-specific recording URL.
    
    Args:
        org_config: Organization configuration dict with azure_storage info
        room_name: LiveKit room name
    
    Returns:
        Full URL to the recording file
    """
    azure_config = org_config.get("azure_storage", {})
    container = azure_config.get("container", DEFAULT_AZURE_CONTAINER)
    # Support both org_id and customer_id for backward compatibility
    org_id = org_config.get("org_id") or org_config.get("organization_id") or org_config.get("customer_id", "default")
    folder = azure_config.get("folder", org_id)
    
    return f"{DEFAULT_AZURE_BASE_URL}/{container}/{folder}/{room_name}.ogg"


def get_consultation_service_mapping(org_config: Dict[str, Any]) -> Dict[str, str]:
    """
    Get consultation type to service ID mapping for an organization.
    
    Args:
        org_config: Organization configuration dict
    
    Returns:
        Dictionary mapping consultation_type -> service_id
    """
    return org_config.get("consultation_types", {})


def get_service_id_mappings(org_config: Dict[str, Any]) -> Dict[str, str]:
    """
    Get old to new service ID mappings for an organization.
    
    Args:
        org_config: Organization configuration dict
    
    Returns:
        Dictionary mapping old_service_id -> new_service_id
    """
    return org_config.get("service_id_mappings", {})


def get_doctors_by_consultation(
    org_config: Dict[str, Any],
    consultation_type: str
) -> list:
    """
    Get list of doctors available for a specific consultation type.
    
    Args:
        org_config: Organization configuration dict
        consultation_type: Type of consultation (e.g., 'general_consultation')
    
    Returns:
        List of doctor dictionaries with 'name' and 'id' keys
    """
    doctors = org_config.get("doctors", {})
    return doctors.get(consultation_type, [])


def get_all_doctor_ids(org_config: Dict[str, Any]) -> list:
    """
    Get all unique doctor IDs for an organization.
    
    Args:
        org_config: Organization configuration dict
    
    Returns:
        List of unique doctor ID strings
    """
    doctors = org_config.get("doctors", {})
    all_ids = set()
    
    for consultation_doctors in doctors.values():
        for doctor in consultation_doctors:
            if isinstance(doctor, dict) and "id" in doctor:
                all_ids.add(doctor["id"])
    
    return list(all_ids)


def get_organization_name(org_config: Dict[str, Any]) -> str:
    """
    Get organization/practice name.
    
    Args:
        org_config: Organization configuration dict
    
    Returns:
        Organization name string
    """
    # Support multiple possible structures
    org = org_config.get("organization", {}) or org_config.get("customer", {})
    if isinstance(org, dict):
        return org.get("name", "Dental Practice")
    return org_config.get("name", "Dental Practice")


def get_organization_address(org_config: Dict[str, Any]) -> str:
    """
    Get formatted organization address.
    
    Args:
        org_config: Organization configuration dict
    
    Returns:
        Formatted address string
    """
    # Support multiple possible structures
    org = org_config.get("organization", {}) or org_config.get("customer", {})
    if isinstance(org, dict):
        address = org.get("address", {})
    else:
        address = org_config.get("address", {})
    
    parts = [
        address.get("street", ""),
        address.get("city", ""),
        address.get("postcode", ""),
    ]
    
    return "\n".join(filter(None, parts))


def get_agent_name(org_config: Dict[str, Any]) -> str:
    """
    Get AI agent name for the organization.
    
    Args:
        org_config: Organization configuration dict
    
    Returns:
        Agent name string (default: "Emma")
    """
    # Check in ai_receptionist config first, then top level
    ai_config = org_config.get("ai_receptionist", {})
    if isinstance(ai_config, dict):
        agent_name = ai_config.get("agent_name")
        if agent_name:
            return agent_name
    return org_config.get("agent_name", "Emma")


class OrganizationContext:
    """
    Class to hold and manage organization context throughout a call.
    
    This class provides easy access to all organization-specific configuration
    and can be passed to function tools.
    
    Note: This class maintains backward compatibility by also exposing
    customer_id as an alias for org_id.
    """
    
    def __init__(self, org_id: str, config: Dict[str, Any]):
        """
        Initialize organization context.
        
        Args:
            org_id: Organization identifier
            config: Full organization configuration from load_org_config()
        """
        self.org_id = org_id
        self.organization_id = org_id  # Alias for clarity
        self.customer_id = org_id  # Backward compatibility alias
        self.config = config
        self._consultation_mapping = None
    
    @property
    def name(self) -> str:
        """Get organization/practice name."""
        return get_organization_name(self.config)
    
    @property
    def address(self) -> str:
        """Get formatted organization address."""
        return get_organization_address(self.config)
    
    @property
    def agent_name(self) -> str:
        """Get AI agent name."""
        return get_agent_name(self.config)
    
    @property
    def system_prompt(self) -> str:
        """Get system prompt."""
        return self.config.get("system_prompt", "")
    
    @property
    def consultation_types(self) -> Dict[str, str]:
        """Get consultation type to service ID mapping."""
        return get_consultation_service_mapping(self.config)
    
    @property
    def service_id_mappings(self) -> Dict[str, str]:
        """Get old to new service ID mappings."""
        return get_service_id_mappings(self.config)
    
    def get_recording_url(self, room_name: str) -> str:
        """Generate recording URL for this organization."""
        return get_recording_url(self.config, room_name)
    
    def get_doctors_for_consultation(self, consultation_type: str) -> list:
        """Get doctors available for a consultation type."""
        return get_doctors_by_consultation(self.config, consultation_type)
    
    def get_all_doctor_ids(self) -> list:
        """Get all unique doctor IDs."""
        return get_all_doctor_ids(self.config)
    
    def get_api_headers(self) -> Dict[str, str]:
        """Get headers for API requests including org_id."""
        headers = {"X-Organization-ID": self.org_id}
        if BACKEND_API_TOKEN:
            headers["Authorization"] = f"Bearer {BACKEND_API_TOKEN}"
        return headers
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for logging/debugging."""
        return {
            "org_id": self.org_id,
            "organization_id": self.organization_id,
            "customer_id": self.customer_id,  # Backward compatibility
            "name": self.name,
            "agent_name": self.agent_name,
            "consultation_types": self.consultation_types,
        }


# Backward compatibility aliases
CustomerContext = OrganizationContext  # Alias for backward compatibility
get_customer_name = get_organization_name  # Alias for backward compatibility
get_customer_address = get_organization_address  # Alias for backward compatibility


async def create_organization_context(room_name: str, phone: Optional[str] = None) -> OrganizationContext:
    """
    Factory function to create an OrganizationContext instance.
    
    This handles the full flow of identifying the organization and loading their config.
    
    Args:
        room_name: LiveKit room name
        phone: Optional phone number from SIP
    
    Returns:
        Initialized OrganizationContext instance
    """
    org_id = await identify_org_from_room(room_name, phone)
    config = await load_org_config(org_id)
    return OrganizationContext(org_id, config)


# Backward compatibility alias
create_customer_context = create_organization_context
