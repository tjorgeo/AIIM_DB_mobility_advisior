import os
from openai import OpenAI

# University of Cologne GPT Endpoint Configuration
UNI_GPT_BASE_URL = "https://chat.kiconnect.nrw/api/v1"
UNI_GPT_MODEL = "Openai GPT OSS 120B"

def build_university_gpt_connection():
    # Get API key from environment variable or prompt user
    UNI_GPT_API_KEY = os.getenv("UNI_GPT_API_KEY", "")
        
    # Configuration summary
    print("=" * 60)
    print("University GPT API Configuration")
    print("=" * 60)
    print(f"Base URL: {UNI_GPT_BASE_URL}")
    print(f"Model: {UNI_GPT_MODEL}")
    print(f"API Key: {'***' + UNI_GPT_API_KEY[-8:] if UNI_GPT_API_KEY else 'NOT SET'}")
    print("=" * 60)

    # Initialize OpenAI client with university endpoint
    client = OpenAI(
        base_url=UNI_GPT_BASE_URL,
        api_key=UNI_GPT_API_KEY
    )

    print("✓ OpenAI client initialized with University endpoint")
    
    return client

def call_university_gpt(client, messages, max_new_tokens=512, temperature=0.0):
    """
    Call the University of Cologne GPT endpoint.
    
    Args:
        client: the OpenAI client
        messages: List of message dicts with 'role' and 'content' keys
        max_new_tokens: Maximum tokens to generate
        temperature: Temperature for sampling (0.0 = deterministic)
    
    Returns:
        str: The generated response
    """
    response = client.chat.completions.create(
        model=UNI_GPT_MODEL,
        messages=messages,
        max_tokens=max_new_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()