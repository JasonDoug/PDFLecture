import os
import json
import datetime
from typing import Dict, Any, Union

import functions_framework
from google.cloud import firestore, storage

import google.auth
from google.auth import impersonated_credentials

# Initialize clients
_firestore_client = None
_storage_client = None

def get_firestore_client():
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client()
    return _firestore_client

def get_storage_client():
    global _storage_client
    if _storage_client is None:
        # Use impersonated credentials to allow signing blobs
        # The service account must have 'Service Account Token Creator' role on itself (or project)
        source_credentials, project_id = google.auth.default()
        
        target_principal = "852565109955-compute@developer.gserviceaccount.com"
        
        creds = impersonated_credentials.Credentials(
            source_credentials=source_credentials,
            target_principal=target_principal,
            target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
            lifetime=3600
        )
        
        _storage_client = storage.Client(credentials=creds)
    return _storage_client

def generate_signed_url(gcs_uri: str, expiration_minutes: int = 60) -> Union[str, None]:
    """Generates a v4 signed URL for a GCS blob."""
    if not gcs_uri or not gcs_uri.startswith('gs://'):
        return None
        
    try:
        client = get_storage_client()
        path_parts = gcs_uri.replace('gs://', '').split('/', 1)
        bucket_name = path_parts[0]
        blob_name = path_parts[1]
        
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=expiration_minutes),
            method="GET"
        )
        return url
    except Exception as e:
        print(f"Error generating signed URL for {gcs_uri}: {e}")
        return None

@functions_framework.http
def get_job_status(request):
    """
    HTTP Cloud Function to get job status and signed URLs
    GET /api/status?jobId=<jobId>
    """
    # CORS headers
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Max-Age': '3600'
    }
    
    if request.method == 'OPTIONS':
        return ('', 204, headers)

    try:
        job_id = request.args.get('jobId')
        if not job_id:
            # Try getting from JSON body if not in params
            request_json = request.get_json(silent=True)
            if request_json and 'jobId' in request_json:
                job_id = request_json['jobId']
                
        if not job_id:
            return ({'error': 'jobId required'}, 400, headers)

        db = get_firestore_client()
        collection_name = os.environ.get('FIRESTORE_COLLECTION', 'lecture-jobs')
        
        doc_ref = db.collection(collection_name).document(job_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return ({'error': 'Job not found'}, 404, headers)
            
        job_data = doc.to_dict()
        
        # Determine current state for frontend
        response_data = {
            'jobId': job_data.get('jobId'),
            'status': job_data.get('status'),
            'progress': job_data.get('progress', {}),
            'updated_at': job_data.get('updated_at'),
            'created_at': job_data.get('created_at')
        }
        
        # If script is ready, add script content (optional: or a signed URL)
        # For frontend simplicity, let's fetch the JSON content if it's small, 
        # or provide a signed URL if it's large. 
        # But we probably want the actual text for the transcript view.
        if job_data.get('script', {}).get('status') == 'completed':
            script_path = job_data['script'].get('storage_path')
            response_data['scriptUrl'] = generate_signed_url(script_path)
            
        # If audio is ready, generate signed URLs for sections
        if job_data.get('audio', {}).get('status') == 'completed':
            audio_sections = job_data['audio'].get('sections', [])
            playable_sections = []
            
            for section in audio_sections:
                playable_sections.append({
                    'section_id': section.get('section_id'),
                    'duration': section.get('duration_seconds'),
                    'audioUrl': generate_signed_url(section.get('audio_path')),
                    'timestampsUrl': generate_signed_url(section.get('timestamps_path'))
                })
                
            response_data['audio'] = {
                'total_duration': job_data['audio'].get('total_duration_seconds'),
                'sections': playable_sections
            }
            
        return (json.dumps(response_data), 200, headers)

    except Exception as e:
        print(f"Error retrieving status: {e}")
        return ({'error': str(e)}, 500, headers)
