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


def analyze_document_with_gemini(pdf_content: bytes) -> Dict[str, Any]:
    """
    Analyze PDF document using Gemini Flash
    """
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    
    # Configure Gemini
    genai.configure(api_key=api_key)
    
    # Use gemini-2.5-flash as default, or fallback/upgrade based on env
    model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
    model = genai.GenerativeModel(model_name)
    
    print(f"Using Gemini model: {model_name}")

    analysis_prompt = """
Analyze this PDF document comprehensively for a lecture generation system.
Extract the following information in strict JSON format:

{
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
      "estimated_duration_minutes": 8
    }
  ],
  "learning_objectives": ["what students should understand after this lecture"],
  "summary": "2-3 sentence overview of the entire document",
  "recommended_examples": ["suggestion for real-world examples to add"]
}

Be thorough in analyzing all pages, diagrams, and content structure."""

    try:
        # Upload PDF to Gemini Files API for processing
        print("Uploading PDF to Gemini Files API...")
        uploaded_file = genai.upload_file(
            file_data=pdf_content,
            mime_type='application/pdf',
            display_name='document.pdf'
        )
        print(f"Uploaded file URI: {uploaded_file.uri}")
        
        # Build generation config
        gen_config = {
            'temperature': 0.2,  # Lower temperature for consistent analysis
            'response_mime_type': 'application/json'
        }
        
        # Add media_resolution. Valid for Gemini 2.5-Flash (if supported) and 3.0-Flash
        # Reference: 'LOW' | 'MEDIUM' | 'HIGH' - controls PDF rendering quality
        # We target HIGH for best text/visual extraction
        if any(ver in model_name for ver in ['2.5', '3.0', 'gemini-3']):
             gen_config['media_resolution'] = 'HIGH'
        
        # Generate analysis using uploaded file
        response = model.generate_content(
            [uploaded_file, analysis_prompt],
            generation_config=gen_config
        )
        
        # Parse JSON response
        try:
             analysis = json.loads(response.text)
        except json.JSONDecodeError:
             # Fallback if response is wrapped in markdown code blocks
             text = response.text
             if "```json" in text:
                 text = text.split("```json")[1].split("```")[0]
             elif "```" in text:
                 text = text.split("```")[1].split("```")[0]
             analysis = json.loads(text)
        
        # Extract usage metadata
        usage_metadata = {}
        if hasattr(response, 'usage_metadata'):
            usage_metadata = {
                'prompt_token_count': getattr(response.usage_metadata, 'prompt_token_count', 0),
                'candidates_token_count': getattr(response.usage_metadata, 'candidates_token_count', 0),
                'total_token_count': getattr(response.usage_metadata, 'total_token_count', 0),
            }
            print(f"Usage metadata: {usage_metadata}")
        
        # Add metadata to analysis for storage
        analysis['_metadata'] = {
            'model': model_name,
            'usage': usage_metadata,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'file_uri': uploaded_file.uri
        }
        
        # Clean up uploaded file from Gemini Files API
        try:
            genai.delete_file(uploaded_file.name)
            print(f"Deleted uploaded file: {uploaded_file.name}")
        except Exception as cleanup_error:
            print(f"Warning: Could not delete uploaded file: {cleanup_error}")
        
        return analysis
        
    except Exception as e:
        print(f"Error analyzing document with Gemini: {str(e)}")
        raise


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
        update_data = {
            'status': 'analyzed',
            'updated_at': datetime.utcnow().isoformat() + 'Z',
            'analysis': {
                'status': 'completed',
                'main_topics': analysis.get('main_topics', []),
                'difficulty': analysis.get('difficulty_level', 'unknown'),
                'storage_path': storage_path,
                'summary': analysis.get('summary', ''),
                'section_count': len(analysis.get('suggested_sections', []))
            },
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

