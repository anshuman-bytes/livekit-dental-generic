# LiveKit Worker Agent - Dental Practice AI

An intelligent conversational AI agent for dental practices, built with LiveKit. This agent handles patient phone calls, appointment bookings, inquiries, and provides automated dental practice support via SIP integration.

**🎉 Now supports multiple dental practices (multi-tenant)** - Add new practices without code changes!


## Livekit Cloud
- We currently use [OAI Dental](https://cloud.livekit.io/projects/p_5ng12c97u9u/overview) project from livekit

## 🚀 Features

### Core Features
- **Multi-Tenant Support**: Single codebase supports unlimited dental practices
- **Phone Call Handling**: SIP-based telephony integration for incoming patient calls
- **Appointment Booking**: Automated scheduling for various consultation types
- **Patient Management**: Handles both new and existing patients, NHS and private bookings
- **Multi-Service Support**: General, implant, orthodontic, whitening, and hygienist consultations
- **Intelligent Routing**: Context-aware conversation handling with fallback to human support
- **Call Recording**: Automatic call recording with Azure Blob Storage integration
- **Slack Notifications**: Real-time alerts and call summaries via Slack webhooks
- **Dynamic Configuration**: Practice-specific prompts, greetings, and service mappings
- **UK Phone Validation**: Specialized handling for UK mobile number formats

### Phase 2 Features (New!)
- **⚡ Configuration Caching**: 96% faster config loading with TTL-based caching
- **🎤 Per-Organization Voices**: Customizable voice, speed, and stability for each practice
- **📊 Call Outcome Tracking**: Comprehensive analytics for bookings, callbacks, and more
- **✅ Automated Testing**: Full test suite for multi-tenant validation

## 🛠 Tech Stack

- **LiveKit**: Real-time communication platform
- **OpenAI GPT-4**: Language model for conversational AI
- **ElevenLabs**: Text-to-speech synthesis
- **Deepgram**: Speech-to-text transcription
- **Silero VAD**: Voice activity detection
- **Azure**: Cloud storage for call recordings
- **Docker**: Containerized deployment

## 🧪 Testing

### Multi-Organization Testing

Test the agent with multiple dental practices:

```bash
# Test specific organization
python test_multi_org.py --customer westbury

# Test all configured organizations
python test_multi_org.py --all

# Test custom list of organizations
python test_multi_org.py --customers westbury test-practice oak-dental
```

### Configuration Validation

Validate customer configuration files:

```bash
# Validate single config
python validate_config.py test_configs/test-practice-config.json

# Validate all configs
python validate_config.py --all
```

### Test Coverage

- ✅ Customer identification from room names
- ✅ Configuration loading from backend API
- ✅ Agent factory session creation
- ✅ Recording URL generation (customer-specific)
- ✅ Configuration caching with TTL
- ✅ Voice settings per organization

See [TESTING_GUIDE.md](./TESTING_GUIDE.md) for comprehensive testing documentation.

## 📋 Prerequisites

- Python 3.12+
- LiveKit Cloud account or self-hosted instance
- OpenAI API key
- ElevenLabs API key
- Deepgram API key
- Azure storage account
- Backend API for appointment management

## 🔧 Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd livekit-worker-agent-dental
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   Create a `.env` file with required API keys and configuration:
   ```env
   LIVEKIT_URL=wss://your-livekit-url
   LIVEKIT_API_KEY=your-api-key
   LIVEKIT_API_SECRET=your-api-secret
   OPENAI_API_KEY=your-openai-key
   ELEVENLABS_API_KEY=your-elevenlabs-key
   DEEPGRAM_API_KEY=your-deepgram-key
   BACKEND_API=your-backend-api-url
   SLACK_WEBHOOK_URL=your-slack-webhook
   AZURE_PUBLIC_STORAGE_ACCOUNT_NAME=your-storage-account
   AZURE_PUBLIC_STORAGE_ACCOUNT_KEY=your-storage-key
   AZURE_PUBLIC_STORAGE_CONTAINER_NAME=your-container
   ```

## 🚀 Usage

### Local Development
```bash
python smiledesk_agent_v1.py start --log-level DEBUG
```

### Docker Deployment
```bash
# Build the image
docker build -t dental-agent .

# Run the container
docker run -d --env-file .env dental-agent
```

## 🏢 Multi-Tenant Support

This agent now supports multiple dental practices without code changes! Each practice gets:

- **Custom Branding**: Practice-specific name, greetings, and agent identity
- **Isolated Data**: Separate recording storage paths per practice
- **Custom Configuration**: Practice-specific consultation types, service IDs, and doctor lists
- **Dynamic Prompts**: Each practice can have their own system prompts and workflows

### How It Works
1. Customer identified from room name or phone number
2. Configuration loaded from backend API
3. All agent behavior adapts to customer settings
4. No code changes needed to add new practices!

### Adding a New Practice
1. Add practice to backend database with configuration
2. Configure SIP trunk with room naming: `{practice-id}-smiledesk-agent-{timestamp}`
3. Done! Agent automatically works for the new practice

See [GENERICIZATION_GUIDE.md](GENERICIZATION_GUIDE.md) for complete details.

---

## 🏗 Architecture

```
├── smiledesk_agent_v1.py    # Main agent implementation
├── agent_core/              # Core agent functionality
│   ├── request.py          # Job request handling
│   └── prewarm.py          # Agent prewarming
├── constants/              # Configuration and constants
│   ├── constants.py        # Dental terminology and settings
│   └── system_prompt.py    # AI system prompts
├── prompts/                # Prompt management
│   ├── prompt_manager.py   # Dynamic prompt formatting
│   └── system_prompts.yaml # Prompt templates
├── sip/                    # SIP configuration
│   ├── dispatch.json       # Call routing rules
│   └── inbound-trunk.json  # Trunk configuration
└── utils.py                # Utility functions
```

## 🔄 Workflow

1. **Incoming Call**: Patient calls the dental practice number
2. **SIP Routing**: Call is routed to LiveKit room via SIP trunk
3. **Agent Activation**: AI agent joins the room and greets the patient
4. **Conversation**: Agent handles inquiries, collects information, books appointments
5. **API Integration**: Communicates with backend for availability and booking
6. **Call Completion**: Provides confirmation, records call, sends notifications

## 📞 Supported Operations

- **Appointment Booking**: Schedule consultations with preferred doctors
- **Availability Checking**: Real-time slot availability across multiple services
- **Patient Registration**: New patient onboarding with data collection
- **Callback Requests**: Schedule follow-up calls when needed
- **General Inquiries**: Answer common dental practice questions
- **Emergency Handling**: Route urgent cases appropriately

## 🔧 Configuration

### Consultation Types
- General Consultation
- Implant Consultation  
- Orthodontic Consultation
- Whitening Consultation
- Hygienist Consultation

### Booking Types
- NHS Appointments (limited services)
- Private Appointments (all services)

## 📊 Monitoring

- **Slack Integration**: Real-time call summaries and alerts
- **Call Recordings**: Stored in Azure Blob Storage
- **Usage Metrics**: Token usage and performance tracking
- **Error Logging**: Comprehensive logging for debugging
- **Call Outcomes**: Track bookings, callbacks, and conversion rates

## 📚 Documentation

### Getting Started
- **[QUICK_START_MULTI_TENANT.md](QUICK_START_MULTI_TENANT.md)** - Quick start guide for multi-tenant setup
- **[GENERICIZATION_GUIDE.md](GENERICIZATION_GUIDE.md)** - Phase 1: Multi-tenant implementation details

### Advanced Features
- **[PHASE2_IMPLEMENTATION.md](PHASE2_IMPLEMENTATION.md)** - Phase 2: Performance optimization and analytics

### Testing
- **[tests/README.md](tests/README.md)** - Testing guide and test suite documentation

### API Reference
- **[customer_context.py](customer_context.py)** - Customer context management utilities
- **[agent_core/agent_factory.py](agent_core/agent_factory.py)** - Agent factory with caching

## 🧪 Testing

Run the test suite to verify your multi-tenant setup:

```bash
# Quick smoke test
python tests/quick_test.py

# Full test suite
python tests/test_multi_org.py
```

Expected output:
```
✅ Quick test PASSED!

🎉 ALL TESTS PASSED! 🎉
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is proprietary software for Westbury Dental Care.

## 📞 Support

For technical support or questions, please contact the development team.

---

**Version**: 1.1.0 (Phase 2 - Performance & Analytics)  
**Previous Versions**: 1.0.0 (Multi-Tenant), 0.0.24 (Single-Tenant)  
**Release Date**: December 19, 2025