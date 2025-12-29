# test_voice_parameters.py
import asyncio
import os
import time
from dotenv import load_dotenv
import requests

load_dotenv()

def test_voice_parameters():
    print("=" * 80)
    print("TESTING DIFFERENT VOICE PARAMETERS FOR NEW VOICE")
    print("=" * 80)
    print(f"Voice ID: rfkTsdZrVWEVhDycUYn9")
    print(f"Model: eleven_multilingual_v2")
    print("=" * 80)
    
    # Get API key
    api_key = os.getenv("ELEVEN_API_KEY")
    if not api_key:
        print("ERROR: ELEVEN_API_KEY not found in .env file!")
        return
    
    print(f"API Key found: {api_key[:10]}...")
    
    # Different parameter combinations to test
    test_configs = [
        {
            "speed": 0.87, 
            "stability": 0.4, 
            "similarity_boost": 0.6, 
            "name": "Current Settings (Baseline)",
            "description": "Your current configuration"
        },
        {
            "speed": 0.8, 
            "stability": 0.3, 
            "similarity_boost": 0.5, 
            "name": "Slower & More Natural",
            "description": "More variable, slower pace for clarity"
        },
        {
            "speed": 0.9, 
            "stability": 0.5, 
            "similarity_boost": 0.7, 
            "name": "Faster & More Consistent",
            "description": "Quicker pace, more stable delivery"
        },
        {
            "speed": 0.85, 
            "stability": 0.35, 
            "similarity_boost": 0.65, 
            "name": "Balanced Professional",
            "description": "Balanced settings for professional use"
        },
        {
            "speed": 0.95, 
            "stability": 0.6, 
            "similarity_boost": 0.8, 
            "name": "Fast & Ultra Consistent",
            "description": "Quick, very consistent for busy reception"
        },
        {
            "speed": 0.82, 
            "stability": 0.25, 
            "similarity_boost": 0.55, 
            "name": "Natural Conversational",
            "description": "Most human-like, variable delivery"
        }
    ]
    
    # Test phrases
    test_phrases = [
        "Good morning, Westbury Dental Care, this is Emma speaking. How may I help you today?",
        "I'd be happy to help you book an appointment. Are you a new or existing patient?",
        "The consultation fee is £65 for private patients. Would you like to proceed with booking?"
    ]
    
    results = []
    
    for config_idx, config in enumerate(test_configs, 1):
        print(f"\n{'='*60}")
        print(f"CONFIGURATION {config_idx}: {config['name']}")
        print(f"{'='*60}")
        print(f"Description: {config['description']}")
        print(f"Speed: {config['speed']}")
        print(f"Stability: {config['stability']}")
        print(f"Similarity Boost: {config['similarity_boost']}")
        print("-" * 60)
        
        # Setup API request
        voice_id = "rfkTsdZrVWEVhDycUYn9"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        
        config_results = {
            "name": config['name'],
            "config": config,
            "tests": [],
            "avg_time": 0,
            "success_count": 0
        }
        
        total_time = 0
        successful_tests = 0
        
        for phrase_idx, phrase in enumerate(test_phrases, 1):
            print(f"\nTest {phrase_idx}: {phrase[:50]}{'...' if len(phrase) > 50 else ''}")
            
            data = {
                "text": phrase,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": config['stability'],
                    "similarity_boost": config['similarity_boost'],
                    "speed": config['speed'],
                    "use_speaker_boost": True
                }
            }
            
            try:
                start_time = time.time()
                response = requests.post(url, json=data, headers=headers)
                end_time = time.time()
                
                synthesis_time = (end_time - start_time) * 1000
                
                if response.status_code == 200:
                    total_time += synthesis_time
                    successful_tests += 1
                    print(f"SUCCESS! Time: {synthesis_time:.2f}ms")
                    config_results["tests"].append({"success": True, "time": synthesis_time})
                else:
                    print(f"ERROR: HTTP {response.status_code}")
                    config_results["tests"].append({"success": False, "error": f"HTTP {response.status_code}"})
                
            except Exception as e:
                print(f"ERROR: {e}")
                config_results["tests"].append({"success": False, "error": str(e)})
        
        config_results["success_count"] = successful_tests
        config_results["avg_time"] = total_time / len(test_phrases) if successful_tests > 0 else 0
        results.append(config_results)
        
        print(f"\nConfiguration Summary:")
        print(f"  Success Rate: {successful_tests}/{len(test_phrases)} ({(successful_tests/len(test_phrases)*100):.1f}%)")
        if successful_tests > 0:
            print(f"  Average Synthesis Time: {config_results['avg_time']:.2f}ms")
    
    # Final comparison
    print("\n" + "=" * 80)
    print("PARAMETER COMPARISON RESULTS")
    print("=" * 80)
    
    print(f"{'Configuration':<25} {'Success Rate':<12} {'Avg Time':<12} {'Recommendation'}")
    print("-" * 80)
    
    for result in results:
        success_rate = f"{result['success_count']}/{len(test_phrases)}"
        avg_time = f"{result['avg_time']:.1f}ms" if result['avg_time'] > 0 else "N/A"
        
        # Determine recommendation
        if result['success_count'] == len(test_phrases):
            if result['avg_time'] < 1000:  # Less than 1 second
                recommendation = "EXCELLENT"
            elif result['avg_time'] < 2000:  # Less than 2 seconds
                recommendation = "GOOD"
            else:
                recommendation = "SLOW"
        else:
            recommendation = "FAILED"
        
        print(f"{result['name']:<25} {success_rate:<12} {avg_time:<12} {recommendation}")
    
    # Best configuration recommendation
    successful_configs = [r for r in results if r['success_count'] == len(test_phrases)]
    if successful_configs:
        best_config = min(successful_configs, key=lambda x: x['avg_time'])
        print(f"\nRECOMMENDED CONFIGURATION: {best_config['name']}")
        print(f"   Speed: {best_config['config']['speed']}")
        print(f"   Stability: {best_config['config']['stability']}")
        print(f"   Similarity Boost: {best_config['config']['similarity_boost']}")
        print(f"   Average Response Time: {best_config['avg_time']:.2f}ms")
        
        print(f"\nCODE TO UPDATE:")
        print(f"voice_settings=elevenlabs.VoiceSettings(")
        print(f"    stability={best_config['config']['stability']},")
        print(f"    similarity_boost={best_config['config']['similarity_boost']},")
        print(f"    speed={best_config['config']['speed']},")
        print(f"    use_speaker_boost=True,")
        print(f"),")
    
    print("=" * 80)

if __name__ == "__main__":
    print("Starting voice parameter testing...")
    test_voice_parameters()
