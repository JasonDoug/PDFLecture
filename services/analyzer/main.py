"""
Document Understanding Service - Cloud Function
Analyzes PDF documents using Google Gemini vision model
"""

import os
import json
import base64
from datetime import datetime
from typing import Dict, Any

import functions_framework
from google.cloud import storage, firestore, pubsub_v1
import google.generativeai as genai
import google.generativeai.types as safety_types
from io import BytesIO

# Initialize clients
_storage_client = None
_firestore_client = None


def get_storage_client():
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client


def get_firestore_client():
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client()
    return _firestore_client


def download_pdf_from_gcs(storage_path: str) -> bytes:
    """Download PDF from Google Cloud Storage"""
    # Parse GCS path: gs://bucket-name/path/to/file
    if not storage_path.startswith('gs://'):
        raise ValueError(f"Invalid GCS path: {storage_path}")
    
    path_parts = storage_path[5:].split('/', 1)
    bucket_name = path_parts[0]
    blob_path = path_parts[1]
    
    client = get_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    return blob.download_as_bytes()

def extract_text_from_pdf(pdf_content: bytes) -> str:
    """Extract text from PDF using pypdf"""
    try:
        from pypdf import PdfReader
        pdf = PdfReader(BytesIO(pdf_content))
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"Text extraction failed: {e}")
        return ""


def analyze_document_with_gemini(pdf_content: bytes) -> Dict[str, Any]:
    """
    Analyze PDF document using Gemini Flash
    """
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    
    # Configure Gemini
    genai.configure(api_key=api_key)
    
    # Use gemini-3.0-flash as default
    model_name = os.environ.get('GEMINI_MODEL', 'gemini-3.0-flash')
    model = genai.GenerativeModel(
        model_name,
        system_instruction="You are an expert document analyzer."
    )
    
    print(f"Using Gemini model: {model_name}")

    # Hybrid Strategy: defined below
    extracted_text = extract_text_from_pdf(pdf_content)
    print(f"Extracted {len(extracted_text)} chars of text for fallback availability.")

    analysis_prompt = """
Analyze this PDF document comprehensively for a lecture generation system.
Extract the following information in strict JSON format:

{
  "document_type": "Non-Fiction|Fiction|Textbook|Research Paper",
  "main_topics": ["list of main topics covered"],
  "difficulty_level": "Beginner|Intermediate|Advanced",
  "target_audience": "description of intended audience",
  "prerequisites": ["list of prerequisite knowledge needed"],
  "visual_elements": [
    {
      "type": "diagram|chart|table|equation|image",
      "description": "detailed description of what it shows",
      "page_number": "page number if visible",
      "relevance": "how it relates to the content"
    }
  ],
  "suggested_sections": [
    {
      "title": "section title for lecture",
      "topics": ["specific topics to cover"],
      "key_points": ["main point 1", "main point 2"],
      "detailed_content": "comprehensive summary of this section's content, including definitions, dates, and names. This is CRITICAL for the script writer.",
      "estimated_duration_minutes": 8
    }
  ],
  "learning_objectives": ["what students should understand after this lecture"],
  "summary": "2-3 sentence overview of the entire document",
  "recommended_examples": ["suggestion for real-world examples to add"]
}

Be thorough in analyzing the content structure."""

    # Generate analysis using uploaded file
    # Use explicit enum types for robustness
    safety_settings = {
        genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
        genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
        genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
        genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
    }
    
    # Build generation config
    gen_config = {
        'temperature': 0.2,  # Lower temperature for consistent analysis
        'response_mime_type': 'application/json'
    }
    
    # Strategy: Try Vision First (Best Quality). If blocked, fallback to Text (pypdf).
    # extracted_text is already available from line 88
    
    # 1. Attempt Vision Analysis
    try:
        print("Attempting Vision Analysis (Method: Upload)...")
        # Save bytes to temporary file for upload
        temp_pdf_path = '/tmp/temp_upload.pdf'
        with open(temp_pdf_path, 'wb') as f:
            f.write(pdf_content)

        # Upload PDF to Gemini Files API
        uploaded_file = genai.upload_file(
            path=temp_pdf_path,
            mime_type='application/pdf',
            display_name='document.pdf'
        )
        print(f"Uploaded file URI: {uploaded_file.uri}")
        
        content_parts = [uploaded_file, analysis_prompt]
        
        response = model.generate_content(
            content_parts,
            generation_config=gen_config,
            safety_settings=safety_settings
        )
        
        # Check for blocking
        if response.prompt_feedback.block_reason:
             print(f"Vision Analysis Blocked! Reason: {response.prompt_feedback.block_reason}")
             raise ValueError("Vision Blocked")
             
        # Parse JSON to confirm valid response
        try:
             analysis = json.loads(response.text)
        except Exception:
             # If parsing fails, it might be a block or empty response
             if not response.text:
                 raise ValueError("Empty response from Vision")
             # Fallback parsing logic
             text = response.text
             if "```json" in text:
                 text = text.split("```json")[1].split("```")[0]
             elif "```" in text:
                 text = text.split("```")[1].split("```")[0]
             analysis = json.loads(text)
             
        # Add metadata and calculate cost
        usage_metadata = {}
        cost = 0.0
        if hasattr(response, 'usage_metadata'):
            usage_metadata = {
                'prompt_token_count': getattr(response.usage_metadata, 'prompt_token_count', 0),
                'candidates_token_count': getattr(response.usage_metadata, 'candidates_token_count', 0),
                'total_token_count': getattr(response.usage_metadata, 'total_token_count', 0),
            }
            # Gemini 3.0 Flash Pricing: $0.50/1M input, $3.00/1M output
            input_cost = usage_metadata['prompt_token_count'] * 0.5e-6
            output_cost = usage_metadata['candidates_token_count'] * 3.0e-6
            cost = input_cost + output_cost
            print(f"Usage metadata: {usage_metadata}, Estimated Cost: ${cost:.6f}")
            
        analysis['_metadata'] = {
            'model': model_name,
            'usage': usage_metadata,
            'cost_usd': cost,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'file_uri': uploaded_file.uri,
            'method': 'vision'
        }
        
        # Cleanup
        try:
            genai.delete_file(uploaded_file.name)
        except:
            pass
            
        return analysis
        
    except Exception as e:
        print(f"Vision Analysis Failed or Blocked: {e}")
        print("Falling back to Text-Based Analysis (Method: pypdf)...")
        
        # 2. Attempt Text Fallback
        if len(extracted_text) < 50:
             raise ValueError("Text extraction failed or too short. Cannot fallback.")
             
        content_parts = [analysis_prompt, f"DOCUMENT CONTENT:\n{extracted_text}"]
        
        response = model.generate_content(
            content_parts,
            generation_config=gen_config,
            safety_settings=safety_settings
        )
        
        # Parse Fallback JSON
        try:
             analysis = json.loads(response.text)
        except json.JSONDecodeError:
             text = response.text
             if "```json" in text:
                 text = text.split("```json")[1].split("```")[0]
             elif "```" in text:
                 text = text.split("```")[1].split("```")[0]
             analysis = json.loads(text)
             
        # Add metadata and cost for fallback
        usage_metadata = {}
        cost = 0.0
        if hasattr(response, 'usage_metadata'):
            usage_metadata = {
                'prompt_token_count': getattr(response.usage_metadata, 'prompt_token_count', 0),
                'candidates_token_count': getattr(response.usage_metadata, 'candidates_token_count', 0),
                'total_token_count': getattr(response.usage_metadata, 'total_token_count', 0),
            }
            cost = (usage_metadata['prompt_token_count'] * 0.5e-6) + (usage_metadata['candidates_token_count'] * 3.0e-6)

        analysis['_metadata'] = {
            'model': model_name,
            'usage': usage_metadata,
            'cost_usd': cost,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'method': 'text_fallback'
        }
        return analysis


        



def save_analysis_to_gcs(bucket_name: str, job_id: str, analysis: Dict[str, Any]) -> str:
    """Save analysis results to GCS"""
    client = get_storage_client()
    bucket = client.bucket(bucket_name)
    
    blob_path = f"uploads/{job_id}/analysis.json"
    blob = bucket.blob(blob_path)
    
    blob.upload_from_string(
        json.dumps(analysis, indent=2),
        content_type='application/json'
    )
    
    return f"gs://{bucket_name}/{blob_path}"


def update_job_status(job_id: str, analysis: Dict[str, Any], storage_path: str, success: bool = True, error: str = None):
    """Update job status in Firestore"""
    db = get_firestore_client()
    collection_name = os.environ.get('FIRESTORE_COLLECTION', 'lecture-jobs')
    
    job_ref = db.collection(collection_name).document(job_id)
    
    if success:
        analysis_data = {
            'status': 'completed',
            'main_topics': analysis.get('main_topics', []),
            'difficulty': analysis.get('difficulty_level', 'unknown'),
            'storage_path': storage_path,
            'summary': analysis.get('summary', ''),
            'section_count': len(analysis.get('suggested_sections', [])),
            'cost_usd': analysis.get('_metadata', {}).get('cost_usd', 0.0)
        }
        update_data = {
            'status': 'analyzed',
            'updated_at': datetime.utcnow().isoformat() + 'Z',
            'analysis': analysis_data,
            'total_estimated_cost_usd': analysis_data['cost_usd'],
            'progress': {
                'current_step': 'analyzed',
                'percentage': 30,
                'message': 'Document analysis complete'
            }
        }
    else:
        update_data = {
            'status': 'failed',
            'updated_at': datetime.utcnow().isoformat() + 'Z',
            'analysis': {
                'status': 'failed',
                'error': error
            },
            'progress': {
                'current_step': 'failed',
                'percentage': 0,
                'message': f'Analysis failed: {error}'
            }
        }
    
    job_ref.update(update_data)


@functions_framework.cloud_event
def analyze_document(cloud_event):
    """
    Cloud Function triggered by Pub/Sub message
    Analyzes document and stores results
    """
    try:
        # Parse Pub/Sub message
        message_data = base64.b64decode(cloud_event.data["message"]["data"]).decode()
        message = json.loads(message_data)
        
        job_id = message.get('jobId')
        if not job_id:
            print("Error: No jobId in message")
            return
        
        print(f"Starting analysis for job: {job_id}")
        
        # Get job details from Firestore
        db = get_firestore_client()
        collection_name = os.environ.get('FIRESTORE_COLLECTION', 'lecture-jobs')
        job_doc = db.collection(collection_name).document(job_id).get()
        
        if not job_doc.exists:
            print(f"Error: Job {job_id} not found")
            return
        
        job_data = job_doc.to_dict()
        storage_path = job_data['pdf']['storage_path']
        
        # Update status to analyzing
        db.collection(collection_name).document(job_id).update({
            'status': 'analyzing',
            'progress.current_step': 'analyzing',
            'progress.percentage': 20,
            'progress.message': 'Analyzing document with AI...'
        })
        
        # Download PDF
        print(f"Downloading PDF from: {storage_path}")
        pdf_content = download_pdf_from_gcs(storage_path)
        
        # Analyze with Gemini vision model
        print("Analyzing document with Gemini vision model...")
        analysis = analyze_document_with_gemini(pdf_content)
        
        # Save analysis results
        bucket_name = os.environ.get('GCS_BUCKET_NAME', 'pdf-lecture-uploads')
        analysis_path = save_analysis_to_gcs(bucket_name, job_id, analysis)
        
        print(f"Analysis saved to: {analysis_path}")
        
        # Update job status
        update_job_status(job_id, analysis, analysis_path, success=True)
        
        print(f"Analysis complete for job: {job_id}")
        
        # Trigger next step (script generation)
        trigger_script_generation(job_id)
        
    except Exception as e:
        print(f"Error in document analysis: {str(e)}")
        if 'job_id' in locals():
            update_job_status(job_id, {}, '', success=False, error=str(e))


def trigger_script_generation(job_id: str) -> None:
    """Trigger script generation via Pub/Sub"""
    client = pubsub_v1.PublisherClient()
    project_id = os.environ.get('GCP_PROJECT_ID')
    topic_name = f"projects/{project_id}/topics/script-generation"
    
    message_data = json.dumps({
        'jobId': job_id,
        'timestamp': datetime.utcnow().isoformat()
    }).encode('utf-8')
    
    try:
        future = client.publish(topic_name, message_data)
        future.result()
        print(f"Triggered script generation for job: {job_id}")
    except Exception as e:
        print(f"Warning: Could not publish to Pub/Sub: {e}")

@functions_framework.http
def analyze_document_http(request):
    """
    HTTP endpoint for document analysis (for testing/manual trigger)
    """
    try:
        data = request.get_json()
        job_id = data.get('jobId')
        
        if not job_id:
            return {'error': 'jobId required'}, 400
        
        # Simulate Pub/Sub message
        class MockEvent:
            data = {
                "message": {
                    "data": base64.b64encode(json.dumps({'jobId': job_id}).encode())
                }
            }
        
        analyze_document(MockEvent())
        
        return {'success': True, 'jobId': job_id}, 200
        
    except Exception as e:
        return {'error': str(e)}, 500

