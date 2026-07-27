#!/usr/bin/env python3
"""
Quick test script to verify transcript extraction is working.
Run this before running the full app to diagnose issues.
"""

import sys
from chains import fetch_transcript_tool

def test_transcript(url: str):
    print(f"\n{'='*70}")
    print(f"Testing transcript extraction for: {url}")
    print(f"{'='*70}\n")
    
    try:
        result = fetch_transcript_tool.invoke({"url": url})
        
        print(f"✅ SUCCESS!")
        print(f"\nTranscript Length: {len(result)} characters")
        print(f"\n--- First 800 Characters ---")
        print(result[:800])
        print(f"\n--- Last 500 Characters ---")
        print(result[-500:])
        print(f"\n{'='*70}")
        
        # Check quality
        if "VIDEO TITLE:" in result and "TRANSCRIPT:" in result:
            print("✅ High-quality transcript with title")
        elif "VIDEO ID:" in result and len(result) > 1000:
            print("⚠️  Transcript extracted but no title")
        elif len(result) < 500:
            print("❌ Transcript too short - video might not have captions")
        else:
            print("⚠️  Transcript quality unknown")
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Default test video (Python tutorial by Mosh)
    test_url = "https://www.youtube.com/watch?v=rfscVS0vtbw"
    
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
    
    print(f"\n🧪 YT Notes Maker - Transcript Test")
    print(f"Usage: python test_transcript.py [youtube_url]\n")
    
    test_transcript(test_url)
