# Test Configurations

This directory contains sample configuration files for testing the multi-tenant dental agent.

## Purpose

These configurations help you:
1. Test the agent with different dental practices
2. Verify multi-tenant isolation
3. Validate configuration loading
4. Develop new features without affecting production data

## Files

### `test-practice-config.json`

A complete sample configuration for "Test Dental Practice" - a fictional dental clinic. Use this as a template when creating configurations for new organizations.

### Required Fields

Every customer configuration must include:

```json
{
  "customer_id": "unique-identifier",
  "customer": {
    "name": "Practice Name",
    "phone": "+44...",
    "email": "...",
    "address": "..."
  },
  "system_prompt": "AI receptionist instructions...",
  "greeting": "Initial greeting message",
  "consultation_types": {
    "Service Name": "service-id"
  },
  "doctors": {
    "doctor-id": {
      "name": "Dr. Name",
      "specialization": "..."
    }
  },
  "azure_storage": {
    "container": "dental",
    "folder": "customer-specific-folder"
  }
}
```

### Optional Fields

- `voice`: ElevenLabs voice settings
- `keyterms`: Deepgram keyword boosting
- `slack`: Slack notification settings
- `features`: Feature flags
- `business_hours`: Operating hours
- `metadata`: Additional info

## Usage

### Local Testing

Use these configs with `test_multi_org.py`:

```bash
python test_multi_org.py --customer test-practice
```

### Backend Integration

Your backend API should return similar JSON structure when queried for a customer's configuration.

Example API endpoint:
```
GET /api/customers/{customer_id}/config
```

## Creating New Test Configs

1. Copy `test-practice-config.json`
2. Update `customer_id` to be unique
3. Modify `customer` details
4. Customize `system_prompt` and `greeting`
5. Define `consultation_types` for the practice
6. List all `doctors`
7. Set `azure_storage.folder` to match `customer_id`
8. Validate using `validate_config.py` (if available)

## Configuration Guidelines

### Customer ID

- Use lowercase
- Hyphen-separated words
- Must be URL-safe
- Examples: `oak-dental`, `city-smiles`, `riverside-clinic`

### System Prompt

- Should be 200-500 words
- Define agent role clearly
- Include tone/style guidelines
- List key responsibilities
- Mention important policies

### Consultation Types

- Map user-friendly names to backend service IDs
- Cover common dental services
- Include emergency categories
- Be specific (not just "Appointment")

### Doctor Configuration

- Use consistent ID format: `dr-lastname`
- Include full name and specialization
- Optional: availability, phone, email

### Voice Settings

Voice settings control ElevenLabs TTS:
- `stability`: 0.0-1.0 (0.6 recommended)
- `similarity_boost`: 0.0-1.0 (0.8 recommended)
- `speed`: 0.5-1.5 (0.87 recommended)
- `use_speaker_boost`: true/false

## Security Notes

⚠️ **Never commit sensitive data**:
- API keys
- Passwords
- Real patient data
- Production credentials

Use environment variables for:
- Azure storage keys
- Slack webhook URLs
- Backend API tokens
- LiveKit credentials

## Validation

Before using a new configuration:

1. **JSON Syntax**: Ensure valid JSON (use a validator)
2. **Required Fields**: Check all mandatory fields present
3. **Service IDs**: Verify service IDs exist in backend
4. **Doctor IDs**: Ensure doctor IDs are valid
5. **Storage Path**: Confirm Azure path doesn't conflict

## Testing Checklist

For each new configuration:

- [ ] JSON is valid
- [ ] All required fields present
- [ ] Customer ID is unique
- [ ] System prompt is appropriate
- [ ] Consultation types mapped correctly
- [ ] Doctor list is complete
- [ ] Azure storage path is unique
- [ ] Voice settings are reasonable
- [ ] Passes `test_multi_org.py` tests

## Examples

### Minimal Configuration

```json
{
  "customer_id": "simple-dental",
  "customer": {
    "name": "Simple Dental",
    "phone": "+441234567890"
  },
  "system_prompt": "You are a receptionist for Simple Dental.",
  "greeting": "Hi, this is Simple Dental.",
  "consultation_types": {
    "Check-up": "service-1"
  },
  "doctors": {
    "dr-smith": {
      "name": "Dr. Smith"
    }
  },
  "azure_storage": {
    "container": "dental",
    "folder": "simple-dental"
  }
}
```

### Full Configuration

See `test-practice-config.json` for a complete example with all optional fields.

## Support

For questions about configurations:
1. Review the main README.md
2. Check GENERICIZATION_GUIDE.md for architecture details
3. See TESTING_GUIDE.md for testing procedures







