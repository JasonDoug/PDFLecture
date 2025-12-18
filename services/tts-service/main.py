import functions_framework
from flask import Request, jsonify
import re
import os
import base64
import requests

# Imports for Google Cloud TTS
from google.cloud import texttospeech

@functions_framework.http
def synthesize_text(request: Request):
    """
    Synthesize text to speech.
    POST JSON body:
    {
        "text": "Text to synthesize",
        "provider": "google" | "elevenlabs",
        "settings": {
            "language_code": "en-US",
            "voice_name": "en-US-Journey-F", # for Google
            "voice_id": "...", # for ElevenLabs
            "api_key": "..." # for ElevenLabs if not in env
        }
    }
    """
    # Set CORS headers for the preflight request
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    # Set CORS headers for the main request
    headers = {
        'Access-Control-Allow-Origin': '*'
    }

    if request.method != 'POST':
        return ('Method not allowed', 405, headers)

    data = request.get_json(silent=True)
    if not data or 'text' not in data:
        return ('Missing text in request body', 400, headers)

    text = data['text']
    provider = data.get('provider', 'google').lower()
    settings = data.get('settings', {})

    try:
        if provider == 'google':
            audio_content = synthesize_google(text, settings)
        elif provider == 'elevenlabs':
            audio_content = synthesize_elevenlabs(text, settings)
        else:
            return (f'Unknown provider: {provider}', 400, headers)

        # Return base64 encoded audio
        return (jsonify({
            'provider': provider,
            'audio_content': base64.b64encode(audio_content).decode('utf-8')
        }), 200, headers)

    except Exception as e:
        print(f"Error in TTS: {e}")
        return (jsonify({'error': str(e)}), 500, headers)

def synthesize_google(text: str, settings: dict) -> bytes:
    """
    Synthesize using Google Cloud TTS.
    Requires GOOGLE_APPLICATION_CREDENTIALS to be set in the environment.
    """
    client = texttospeech.TextToSpeechClient()
    
    # Text limit for Google TTS is 5000 bytes. We use 4500 to be safe.
    MAX_CHARS = 4500
    
    # Simple chunking by length - could be improved by splitting at sentences
    chunks = [text[i:i+MAX_CHARS] for i in range(0, len(text), MAX_CHARS)]
    
    audio_full = b""
    
    # Default to Journey voice if not specified
    language_code = settings.get('language_code', 'en-US')
    voice_name = settings.get('voice_name', 'en-US-Journey-F')
    
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name
    )
    
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    for chunk in chunks:
        # print(f"Synthesizing chunk of length {len(chunk)}...")
        input_text = texttospeech.SynthesisInput(text=chunk)
        
        response = client.synthesize_speech(
            request={"input": input_text, "voice": voice, "audio_config": audio_config}
        )
        audio_full += response.audio_content
    
    return audio_full

def synthesize_elevenlabs(text: str, settings: dict) -> bytes:
    """
    Synthesize using ElevenLabs API.
    Note: ElevenLabs handles longer text better (up to 5000 chars on free tier, more on paid), 
    but for very large docs we should implement similar chunking here if needed.
    """
    api_key = settings.get('api_key') or os.environ.get('ELEVENLABS_API_KEY')
    if not api_key:
        raise ValueError("ElevenLabs API key is required")
    
    voice_id = settings.get('voice_id', '21m00Tcm4TlvDq8ikWAM') # Default 'Rachel'
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5
        }
    }
    
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"ElevenLabs API Error: {response.text}")
        
    return response.content
