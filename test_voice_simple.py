# test_voice_simple.py
import asyncio
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

def test_elevenlabs_voice():
    """Simple test using ElevenLabs API directly"""
    
    print("=" * 70)
    print("TESTING NEW VOICE WITH ELEVENLABS API")
    print("=" * 70)
    print(f"Voice ID: rfkTsdZrVWEVhDycUYn9")
    print("=" * 70)
    
    # Get API key
    api_key = os.getenv("ELEVEN_API_KEY")
    if not api_key:
        print("ERROR: ELEVEN_API_KEY not found in .env file!")
        return
    
    print(f"API Key found: {api_key[:10]}...")
    
    # Test phrases
    test_phrases = [
        "Good morning, Westbury Dental Care, this is Emma speaking.",
        "I'd be happy to help you book an appointment.",
        "The consultation fee is £65 for private patients."
    ]
    
    voice_id = "rfkTsdZrVWEVhDycUYn9"
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    successful_tests = 0
    total_tests = len(test_phrases)
    
    for i, phrase in enumerate(test_phrases, 1):
        print(f"\nTest {i}/{total_tests}")
        print(f"Text: {phrase}")
        
        data = {
            "text": phrase,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.6,
                "speed": 0.87,
                "use_speaker_boost": True
            }
        }
        
        try:
            start_time = time.time()
            response = requests.post(url, json=data, headers=headers)
            end_time = time.time()
            
            response_time = (end_time - start_time) * 1000
            
            if response.status_code == 200:
                print("SUCCESS: Voice synthesis successful!")
                print(f"  Response time: {response_time:.2f}ms")
                print(f"  Audio size: {len(response.content)} bytes")
                successful_tests += 1
            else:
                print(f"ERROR: HTTP {response.status_code}")
                print(f"  Response: {response.text}")
                
        except Exception as e:
            print(f"ERROR: {e}")
        
        print("-" * 50)
    
    # Summary
    print("\n" + "=" * 70)
    print("VOICE TEST SUMMARY")
    print("=" * 70)
    print(f"Total Tests: {total_tests}")
    print(f"Successful: {successful_tests}")
    print(f"Failed: {total_tests - successful_tests}")
    print(f"Success Rate: {(successful_tests/total_tests)*100:.1f}%")
    
    if successful_tests == total_tests:
        print("\nSUCCESS: ALL TESTS PASSED!")
        print("SUCCESS: Voice ID is valid")
        print("SUCCESS: ElevenLabs API connection successful")
        print("SUCCESS: New voice is working perfectly!")
        print("\nNEXT STEPS:")
        print("1. Voice is ready to use in production")
        print("2. You can now test the full agent")
        print("3. Consider parameter optimization if needed")
    elif successful_tests > 0:
        print(f"\nWARNING: PARTIAL SUCCESS")
        print("Some tests failed - check your API key or voice access")
    else:
        print("\nERROR: ALL TESTS FAILED!")
        print("Check your:")
        print("- ELEVEN_API_KEY in .env file")
        print("- Voice ID: rfkTsdZrVWEVhDycUYn9")
        print("- Internet connection")
        print("- ElevenLabs account access to this voice")
        print("- ElevenLabs account credits")
    
    print("=" * 70)

if __name__ == "__main__":
    print("Starting simple voice test...")
    test_elevenlabs_voice()
