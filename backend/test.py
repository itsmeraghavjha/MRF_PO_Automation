import os
import sys
import httpx
# Make sure you installed this via: pip install google-genai
from google import genai
from google.genai import types

# Use your actual key here
API_KEY = "AIzaSyDtsYY71SSw"

def log_request_url(request: httpx.Request):
    """
    Interceptors for the new SDK's underlying HTTPX engine.
    """
    print("\n" + "="*60)
    print("🚨 INTERCEPTED NETWORK REQUEST 🚨")
    print("="*60)
    print(f"HTTP Method : {request.method}")
    print(f"Exact URL   : {request.url}")
    print(f"Base Domain : {request.url.host}")
    print("="*60 + "\n")

def run_dynamic_test():
    print("Configuring the new google-genai client with network hooks...")
    
    # Configure the network listener hooks
    http_opts = types.HttpOptions(
        client_args={"event_hooks": {"request": [log_request_url]}}
    )
    
    try:
        # Correct initialization for the new SDK
        client = genai.Client(api_key=API_KEY, http_options=http_opts)
        
        print("Triggering the API call to force the network request...")
        response = client.models.generate_content(
            model="gemini-2.0-flash", # Corrected model version
            contents="Hello"
        )
        print(f"Success! Response: {response.text}")
        
    except Exception as e:
        print(f"⚠️ The request failed as expected due to: {type(e).__name__}")
        print(f"Error details: {e}")

if __name__ == "__main__":
    run_dynamic_test()