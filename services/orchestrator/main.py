import functions_framework
from flask import Request, jsonify
import requests
import os
import json

# Configuration with defaults for local testing
PDF_PROCESSOR_URL = os.environ.get('PDF_PROCESSOR_URL', 'http://localhost:8081')
TTS_SERVICE_URL = os.environ.get('TTS_SERVICE_URL', 'http://localhost:8082')

@functions_framework.http
def orchestrate(request: Request):
    """
    Orchestrator endpoint.
    Accepts POST multipart/form-data:
    - file: PDF file
    - tts_settings: JSON string (optional)
    """
    # Restricted CORS headers
    # Allow from Firebase hosting or local development
    origin = request.headers.get('Origin', '')
    allowed_patterns = [
        'http://localhost:',
        'https://pdf2audiobook-477309.web.app',
        'https://pdf2audiobook-477309.firebaseapp.com'
    ]
    
    cors_origin = '*'
    if any(origin.startswith(p) for p in allowed_patterns):
        cors_origin = origin

    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': cors_origin,
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    headers = {
        'Access-Control-Allow-Origin': cors_origin
    }

    if request.method != 'POST':
        return ('Method not allowed', 405, headers)

    # 1. Validate Input
    if 'file' not in request.files:
        return ('No file uploaded', 400, headers)
    
    file = request.files['file']
    if file.filename == '':
        return ('No file selected', 400, headers)

    tts_settings_str = request.form.get('tts_settings', '{}')
    try:
        tts_settings = json.loads(tts_settings_str)
    except json.JSONDecodeError:
        return ('Invalid tts_settings JSON', 400, headers)

    try:
        # 2. Call PDF Processor
        # We need to repost the file. 
        # requests.post(files=...) takes a dictionary
        files = {'file': (file.filename, file.read(), file.content_type)}
        
        print(f"Calling PDF Processor at {PDF_PROCESSOR_URL}...")
        pdf_resp = requests.post(PDF_PROCESSOR_URL, files=files)
        
        if pdf_resp.status_code != 200:
            return jsonify({
                'error': 'PDF Processing failed',
                'details': pdf_resp.text
            }), pdf_resp.status_code, headers
            
        pdf_data = pdf_resp.json()
        text = pdf_data.get('text', '')
        
        if not text:
             return (jsonify({'error': 'No text extracted from PDF'}), 400, headers)
             
        # 3. Call TTS Service
        print(f"Calling TTS Service at {TTS_SERVICE_URL}...")
        tts_payload = {
            "text": text,
            "provider": tts_settings.get('provider', 'google'),
            "settings": tts_settings.get('settings', {})
        }
        
        tts_resp = requests.post(TTS_SERVICE_URL, json=tts_payload)
        
        if tts_resp.status_code != 200:
             return jsonify({
                'error': 'TTS generation failed',
                'details': tts_resp.text
            }), tts_resp.status_code, headers
            
        tts_data = tts_resp.json()
        
        # 4. Return Result
        return (jsonify({
            'status': 'success',
            'filename': file.filename,
            'text_preview': text[:100] + '...',
            'audio_content': tts_data.get('audio_content'), # Base64
            'provider': tts_data.get('provider')
        }), 200, headers)

    except Exception as e:
        print(f"Orchestration error: {e}")
        return (jsonify({'error': str(e)}), 500, headers)
