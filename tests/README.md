# Multi-Organization Testing

This directory contains testing scripts for the multi-tenant LiveKit dental agent.

## Test Files

### `test_multi_org.py`
Comprehensive test suite that validates:
- Customer identification from room names
- Configuration loading for multiple organizations
- Agent factory functionality
- Configuration caching with TTL
- Customer-specific data isolation

**Run with:**
```bash
cd livekit-worker-agent-dental
python tests/test_multi_org.py
```

### `quick_test.py`
Quick smoke test for verifying your setup is working.

**Run with:**
```bash
cd livekit-worker-agent-dental
python tests/quick_test.py
```

## Prerequisites

1. Set up environment variables in `.env`:
```env
BACKEND_API=https://your-backend-api
BACKEND_API_TOKEN=your-token
DEFAULT_CUSTOMER_ID=westbury
CONFIG_CACHE_TTL=300
```

2. Ensure your backend API is running and accessible

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Expected Output

### Quick Test
```
🔍 Quick Multi-Tenant Test

==================================================

1. Testing customer: westbury
   Room: westbury-smiledesk-agent-test123
   ✓ Agent created successfully
   ✓ Customer ID: westbury
   ✓ Customer name: Westbury Dental Care
   ✓ Recording URL: https://oaipublic.blob.core.windows.net/dental/...

2. Cache Statistics:
   ✓ Cached customers: 1
   ✓ TTL: 300s

==================================================
✅ Quick test PASSED!
==================================================
```

### Full Test Suite
The full test suite will run 5 test categories and provide colored output showing pass/fail status for each test case.

## Testing Multiple Organizations

To test with multiple organizations:

1. Set up test customers in your backend API
2. Modify the test cases in `test_multi_org.py`:
```python
test_sessions = [
    {
        "room_name": "org1-smiledesk-agent-1234567890",
        "phone": "+447947254785",
        "expected_customer": "org1"
    },
    {
        "room_name": "org2-smiledesk-agent-9876543210",
        "phone": "+447123456789",
        "expected_customer": "org2"
    },
]
```

3. Run the test suite to verify each organization's configuration

## Troubleshooting

### Connection Errors
- Verify `BACKEND_API` is set correctly
- Check your API token is valid
- Ensure the backend API is running

### Customer Not Found
- Verify the customer exists in your backend database
- Check the `DEFAULT_CUSTOMER_ID` environment variable
- Review room name format: `{customer-id}-smiledesk-agent-{phone}`

### Cache Issues
- Clear cache with: `AgentFactory.clear_cache()`
- Check `CONFIG_CACHE_TTL` is set appropriately
- Monitor cache hit/miss rates in logs

## CI/CD Integration

These tests can be integrated into your CI/CD pipeline:

```bash
# Run tests and exit with error code on failure
python tests/test_multi_org.py || exit 1
```

For GitHub Actions:
```yaml
- name: Test Multi-Tenant Agent
  run: |
    cd livekit-worker-agent-dental
    python tests/test_multi_org.py
```

## Adding New Tests

To add new test cases:

1. Create a new test function in `test_multi_org.py`:
```python
async def test_my_feature():
    logger.info(f"\nTEST: My Feature\n")
    # Your test logic
    return passed, failed
```

2. Add to the `main()` function:
```python
tests = [
    test_customer_identification,
    test_config_loading,
    # ... existing tests
    test_my_feature,  # Add your test
]
```

3. Run the test suite to verify

## Support

For issues or questions, please contact the development team or check the main documentation in:
- `GENERICIZATION_GUIDE.md`
- `QUICK_START_MULTI_TENANT.md`

