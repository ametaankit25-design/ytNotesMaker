#!/usr/bin/env python3
"""
Cookie Testing Script for YouTube Transcript Extraction
Tests if cookies are valid and working with YouTube
"""

import os
import sys
import requests
from http.cookiejar import MozillaCookieJar

def test_cookies(cookies_path: str) -> dict:
    """Test if cookies are valid for YouTube access."""
    results = {
        'cookies_exist': False,
        'cookies_readable': False,
        'youtube_accessible': False,
        'signed_in': False,
        'errors': []
    }
    
    # Check if cookies file exists
    if not os.path.exists(cookies_path):
        results['errors'].append(f"Cookies file not found: {cookies_path}")
        return results
    
    results['cookies_exist'] = True
    file_size = os.path.getsize(cookies_path)
    
    if file_size < 100:
        results['errors'].append(f"Cookies file too small ({file_size} bytes)")
        return results
    
    # Try to load cookies
    try:
        jar = MozillaCookieJar(cookies_path)
        jar.load(ignore_discard=True, ignore_expires=True)
        results['cookies_readable'] = True
        print(f"✓ Successfully loaded {len(jar)} cookies from file")
    except Exception as e:
        results['errors'].append(f"Failed to load cookies: {e}")
        return results
    
    # Test YouTube access with cookies
    try:
        session = requests.Session()
        session.cookies = jar
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })
        
        # Test with YouTube homepage
        response = session.get("https://www.youtube.com", timeout=15, allow_redirects=True)
        
        if response.status_code == 200:
            results['youtube_accessible'] = True
            print(f"✓ YouTube accessible (HTTP {response.status_code})")
            
            # Check if signed in
            if "Sign in" not in response.text and "Create account" not in response.text:
                results['signed_in'] = True
                print("✓ Appears to be signed in to YouTube")
            else:
                print("⚠ Not signed in or cookies expired")
                results['errors'].append("Cookies may be expired - not signed in")
        else:
            results['errors'].append(f"YouTube returned HTTP {response.status_code}")
            
    except Exception as e:
        results['errors'].append(f"YouTube access failed: {e}")
    
    return results

def main():
    """Main testing function."""
    print("=" * 60)
    print("YouTube Cookie Testing Tool")
    print("=" * 60)
    print()
    
    # Find cookies file
    possible_paths = [
        "cookies.txt",
        "/app/cookies.txt",
        os.path.expanduser("~/cookies.txt"),
        os.environ.get("YT_COOKIES_PATH"),
    ]
    
    cookies_path = None
    for path in possible_paths:
        if path and os.path.exists(path):
            cookies_path = path
            break
    
    if not cookies_path:
        print("❌ No cookies.txt file found in expected locations:")
        for path in possible_paths:
            if path:
                print(f"  - {path}")
        print()
        print("Please export cookies from your browser and save as cookies.txt")
        print("See DEPLOYMENT.md for instructions")
        return 1
    
    print(f"Testing cookies from: {cookies_path}")
    print()
    
    results = test_cookies(cookies_path)
    
    print()
    print("=" * 60)
    print("Test Results")
    print("=" * 60)
    
    status_map = {
        'cookies_exist': 'Cookies file exists',
        'cookies_readable': 'Cookies can be read',
        'youtube_accessible': 'YouTube accessible',
        'signed_in': 'Signed in to YouTube'
    }
    
    for key, description in status_map.items():
        status = "✓" if results[key] else "✗"
        print(f"{status} {description}")
    
    if results['errors']:
        print()
        print("Errors encountered:")
        for error in results['errors']:
            print(f"  • {error}")
    
    print()
    
    # Overall assessment
    if results['signed_in']:
        print("🎉 Cookies are working properly!")
        return 0
    elif results['youtube_accessible']:
        print("⚠️  YouTube accessible but cookies may be expired")
        print("   Consider exporting fresh cookies from your browser")
        return 1
    else:
        print("❌ Cookies are not working properly")
        print("   Please export fresh cookies from your browser")
        return 2

if __name__ == "__main__":
    sys.exit(main())