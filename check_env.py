# check_env.py
import os
from dotenv import load_dotenv

print("Checking environment setup...")
print("=" * 50)

# Load .env file
load_dotenv()

# Check for required environment variables
required_vars = [
    "ELEVEN_API_KEY",
    "AZURE_OPENAI_API_KEY", 
    "DEEPGRAM_API_KEY",
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET"
]

print("Environment Variables Status:")
print("-" * 30)

found_vars = 0
for var in required_vars:
    value = os.getenv(var)
    if value:
        # Show first 10 characters for security
        masked_value = f"{value[:10]}..." if len(value) > 10 else value
        print(f"SUCCESS {var}: {masked_value}")
        found_vars += 1
    else:
        print(f"MISSING {var}: NOT FOUND")

print("-" * 30)
print(f"Found: {found_vars}/{len(required_vars)} variables")

# Specific check for ElevenLabs
elevenlabs_key = os.getenv("ELEVEN_API_KEY")
if elevenlabs_key:
    print(f"\nSUCCESS: ElevenLabs API Key is available")
    print(f"  Key length: {len(elevenlabs_key)} characters")
    print(f"  Key preview: {elevenlabs_key[:10]}...")
else:
    print(f"\nERROR: ElevenLabs API Key is missing!")
    print("  Make sure your .env file contains:")
    print("  ELEVEN_API_KEY=your-api-key-here")

print("=" * 50)
