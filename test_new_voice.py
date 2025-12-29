# test_new_voice.py
import asyncio
import os
import time
import aiohttp
from dotenv import load_dotenv
from livekit.plugins import elevenlabs

load_dotenv()

async def test_new_voice():
    print("=" * 70)
    print("TESTING NEW VOICE CONFIGURATION")
    print("=" * 70)
    print(f"NEW Voice ID: rfkTsdZrVWEVhDycUYn9")
    print(f"OLD Voice ID: lcMyyd2HUfFzxdCaC4Ta")
    print(f"Model: eleven_multilingual_v2")
    print(f"Speed: 0.87")
    print(f"Stability: 0.4")
    print(f"Similarity Boost: 0.6")
    print(f"Speaker Boost: True")
    print("=" * 70)
    
    # Create HTTP session for standalone testing
    async with aiohttp.ClientSession() as session:
        # Initialize TTS with new voice configuration and HTTP session
        tts = elevenlabs.TTS(
            voice_id="rfkTsdZrVWEVhDycUYn9",
            model="eleven_multilingual_v2",
            voice_settings=elevenlabs.VoiceSettings(
                stability=0.4,
                similarity_boost=0.6,
                speed=0.87,
                use_speaker_boost=True,
            ),
            session=session,
        )
        
        # Test phrases for dental receptionist
        test_phrases = [
            {
                "text": "Good morning, Westbury Dental Care, this is Emma speaking. How may I help you today?",
                "category": "Greeting"
            },
            {
                "text": "I'd be happy to help you book an appointment. Are you a new or existing patient?",
                "category": "Appointment Booking"
            },
            {
                "text": "The consultation fee is £65 for private patients. Would you like to proceed with booking?",
                "category": "Pricing Information"
            },
            {
                "text": "Let me check our availability for you. What type of consultation are you looking for?",
                "category": "Availability Check"
            },
            {
                "text": "We're located at 75 Kingston Road, New Malden, KT3 3PB. It's about a 10-minute walk from New Malden station.",
                "category": "Location Information"
            },
            {
                "text": "Our opening hours are Monday to Friday, 9:00 AM to 5:00 PM. We also have hygienist appointments on selected Saturdays.",
                "category": "Operating Hours"
            },
            {
                "text": "Thank you for calling Westbury Dental Care. Have a wonderful day and we look forward to seeing you soon!",
                "category": "Closing"
            }
        ]
        
        print("\nTesting voice synthesis with dental receptionist phrases...")
        print("-" * 70)
        
        total_tests = len(test_phrases)
        successful_tests = 0
        failed_tests = 0
        
        for i, phrase_data in enumerate(test_phrases, 1):
            phrase = phrase_data["text"]
            category = phrase_data["category"]
            
            print(f"\nTest {i}/{total_tests} - {category}")
            print(f"Text: {phrase}")
            
            try:
                start_time = time.time()
                # Generate audio
                audio = await tts.synthesize(phrase)
                end_time = time.time()
                
                synthesis_time = (end_time - start_time) * 1000  # Convert to milliseconds
                
                print("SUCCESS: Voice synthesis successful!")
                print(f"  Synthesis time: {synthesis_time:.2f}ms")
                print(f"  Audio length: {len(audio.data) if hasattr(audio, 'data') else 'Available'}")
                successful_tests += 1
                
            except Exception as e:
                print(f"ERROR: {e}")
                print(f"  Error type: {type(e).__name__}")
                failed_tests += 1
            
            print("-" * 50)
        
        # Summary
        print("\n" + "=" * 70)
        print("VOICE TEST SUMMARY")
        print("=" * 70)
        print(f"Total Tests: {total_tests}")
        print(f"Successful: {successful_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(successful_tests/total_tests)*100:.1f}%")
        
        if successful_tests == total_tests:
            print("\nSUCCESS: ALL TESTS PASSED! New voice is working perfectly!")
            print("SUCCESS: Voice ID is valid")
            print("SUCCESS: ElevenLabs API connection successful")
            print("SUCCESS: Voice synthesis functioning properly")
        elif successful_tests > 0:
            print(f"\nWARNING: PARTIAL SUCCESS: {successful_tests}/{total_tests} tests passed")
            print("Some tests failed - check your API key or voice access")
        else:
            print("\nERROR: ALL TESTS FAILED!")
            print("Check your:")
            print("- ELEVENLABS_API_KEY in .env file")
            print("- Voice ID: rfkTsdZrVWEVhDycUYn9")
            print("- Internet connection")
            print("- ElevenLabs account access to this voice")
        
        print("=" * 70)

if __name__ == "__main__":
    print("Starting new voice test...")
    asyncio.run(test_new_voice())
