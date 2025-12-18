import os
import json
import base64
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Re-define config classes to avoid import issues if not in same package
@dataclass
class TTSConfig:
    provider: str
    voice_id: str
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    speaking_rate: float = 1.0

@dataclass
class AudioResult:
    audio_content: bytes
    duration_seconds: float
    # List of {word: str, start: float, end: float}
    timestamps: List[Dict[str, Any]] 
    format: str = "mp3"

class TTSProvider(ABC):
    @abstractmethod
    def generate_audio(self, text: str, config: TTSConfig) -> AudioResult:
        pass

    def clean_text(self, text: str) -> str:
        """Remove markdown artifacts that might be spoken"""
        # Remove asterisks (often used for bold/italics)
        text = text.replace('*', '')
        # Remove hashes (headers)
        text = text.replace('#', '')
        return text

class ElevenLabsProvider(TTSProvider):
    def generate_audio(self, text: str, config: TTSConfig) -> AudioResult:
        text = self.clean_text(text)
        api_key = os.environ.get('ELEVENLABS_API_KEY')
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY environment variable not set")
            
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.voice_id}/with-timestamps"
        
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": config.stability,
                "similarity_boost": config.similarity_boost,
                "style": config.style,
                "use_speaker_boost": True
            }
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"ElevenLabs API Error: {response.status_code} - {response.text}")
            
        data = response.json()
        
        # Decode audio from base64 (ElevenLabs timestamps endpoint returns JSON with base64 audio)
        audio_content = base64.b64decode(data["audio_base64"])
        alignment = data.get("alignment", {})
        
        # Convert alignment to standard timestamp format
        timestamps = []
        chars = alignment.get("characters", [])
        starts = alignment.get("character_start_times_seconds", [])
        ends = alignment.get("character_end_times_seconds", [])
        
        # ElevenLabs returns character-level alignment. 
        # For simplicity/karaoke, we might process this into words later, 
        # or just store character alignment. 
        # Let's try to group into words for the frontend.
        current_word = ""
        word_start = 0.0
        
        for i, char in enumerate(chars):
            if i >= len(starts) or i >= len(ends):
                break
                
            if char.strip():
                if not current_word:
                    word_start = starts[i]
                current_word += char
            elif current_word:
                # Space or punctuation ending a word
                timestamps.append({
                    "word": current_word,
                    "start": word_start,
                    "end": ends[i-1]
                })
                current_word = ""
                
        # Catch last word
        if current_word:
             timestamps.append({
                "word": current_word,
                "start": word_start,
                "end": ends[len(current_word)-1] if ends else 0.0
            })

        # Calculate duration roughly from last timestamp or audio length
        duration = ends[-1] if ends else len(audio_content) / 44100  # fallback
        
        return AudioResult(
            audio_content=audio_content,
            duration_seconds=duration,
            timestamps=timestamps
        )

class GoogleTTSProvider(TTSProvider):
    def generate_audio(self, text: str, config: TTSConfig) -> AudioResult:
        text = self.clean_text(text)
        from google.cloud import texttospeech
        
        client = texttospeech.TextToSpeechClient()
        
        # Audio Configuration
        # Extract language code
        language_code = "en-US"
        if config.voice_id:
            parts = config.voice_id.split('-')
            if len(parts) >= 2:
                language_code = f"{parts[0]}-{parts[1]}"

        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=config.voice_id if config.voice_id else "en-US-Journey-F"
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=config.speaking_rate
        )

        # Chunking Logic (Limit is 5000 bytes, using 4500 safe limit)
        LIMIT = 4500
        chunks = []
        
        if len(text) <= LIMIT:
            chunks.append(text)
        else:
            # Split by sentences to match rough boundaries
            sentences = text.replace('. ', '.|').replace('? ', '?|').replace('! ', '!|').split('|')
            current_chunk = ""
            for s in sentences:
                if len(current_chunk) + len(s) < LIMIT:
                    current_chunk += s
                else:
                    if current_chunk: chunks.append(current_chunk)
                    current_chunk = s
            if current_chunk:
                chunks.append(current_chunk)
        
        # Process Chunks
        combined_audio = b""
        all_timestamps = []
        current_time_offset = 0.0
        
        for chunk_text in chunks:
            if not chunk_text.strip(): continue
            
            synthesis_input = texttospeech.SynthesisInput(text=chunk_text)
            
            try:
                response = client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
                
                combined_audio += response.audio_content
                
                # Estimate timestamps for this chunk
                words = chunk_text.split()
                # 150 wpm * speaking_rate
                wpm = 150 * config.speaking_rate
                duration_est = len(words) / (wpm/60)
                avg_word_dur = duration_est / len(words) if words else 0
                
                chunk_curr = current_time_offset
                for w in words:
                    all_timestamps.append({
                        "word": w,
                        "start": chunk_curr,
                        "end": chunk_curr + avg_word_dur
                    })
                    chunk_curr += avg_word_dur
                
                # Update offset for next chunk logic
                # For more accuracy we could inspect MP3 headers but estimation is consistent with previous logic
                current_time_offset += duration_est
                
            except Exception as e:
                print(f"Error synthesizing chunk: {e}")
                # Continue best effort? Or fail? Fail is safer.
                raise e
            
        return AudioResult(
            audio_content=combined_audio,
            duration_seconds=current_time_offset,
            timestamps=all_timestamps
        )

def get_provider(provider_name: str) -> TTSProvider:
    if provider_name.lower() == "elevenlabs":
        return ElevenLabsProvider()
    elif provider_name.lower() == "google":
        return GoogleTTSProvider()
    else:
        # Default to Google as it might be cheaper/easier if env var missing, 
        # but let's stick to explicit requests.
        return GoogleTTSProvider()
