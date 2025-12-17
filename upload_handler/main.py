"""
PDF Upload Handler - Cloud Function
Accepts PDF uploads, validates them, stores in GCS, and triggers processing pipeline
"""

import os
import uuid
import json
from datetime import datetime
from typing import Dict, Any

import functions_framework
from flask import jsonify, Request
from google.cloud import storage, firestore, pubsub_v1
from werkzeug.utils import secure_filename

# Configuration
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {'pdf'}

# Initialize clients (lazy loading for better performance)
_storage_client = None
_firestore_client = None
_pubsub_client = None


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


def get_pubsub_client():
    global _pubsub_client
    if _pubsub_client is None:
        _pubsub_client = pubsub_v1.PublisherClient()
    return _pubsub_client


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_to_gcs(bucket_name: str, job_id: str, filename: str, file_content: bytes) -> str:
    """Upload file to Google Cloud Storage"""
    client = get_storage_client()
    bucket = client.bucket(bucket_name)
    
    # Create blob path: uploads/{job_id}/original.pdf
    blob_path = f"uploads/{job_id}/original.pdf"
    blob = bucket.blob(blob_path)
    
    # Upload with metadata
    blob.upload_from_string(
        file_content,
        content_type='application/pdf'
    )
    
    return f"gs://{bucket_name}/{blob_path}"


def create_job_record(job_id: str, filename: str, file_size: int, storage_path: str) -> None:
    """Create job record in Firestore"""
    db = get_firestore_client()
    collection_name = os.environ.get('FIRESTORE_COLLECTION', 'lecture-jobs')
    
    job_data = {
        'jobId': job_id,
        'status': 'uploaded',
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'updated_at': datetime.utcnow().isoformat() + 'Z',
        'pdf': {
            'filename': filename,
            'size_bytes': file_size,
            'storage_path': storage_path
        },
        'analysis': {
            'status': 'pending'
        },
        'script': {
            'status': 'pending'
        },
        'audio': {
            'status': 'pending'
        },
        'progress': {
            'current_step': 'uploaded',
            'percentage': 10,
            'message': 'PDF uploaded successfully, starting analysis...'
        }
    }
    
    db.collection(collection_name).document(job_id).set(job_data)


def trigger_document_analysis(job_id: str) -> None:
    """Trigger document analysis via Pub/Sub"""
    client = get_pubsub_client()
    project_id = os.environ.get('GCP_PROJECT_ID')
    topic_name = f"projects/{project_id}/topics/document-analysis"
    
    message_data = json.dumps({
        'jobId': job_id,
        'timestamp': datetime.utcnow().isoformat()
    }).encode('utf-8')
    
    try:
        future = client.publish(topic_name, message_data)
        future.result()  # Wait for publish to complete
    except Exception as e:
        print(f"Warning: Could not publish to Pub/Sub: {e}")
        # In local development, Pub/Sub might not be available
        # The job is still created and can be processed manually


@functions_framework.http
def upload_pdf(request: Request):
    """
    HTTP Cloud Function for PDF upload
    
    Accepts: multipart/form-data with 'file' field
    Returns: JSON with jobId and status
    """
    
    # CORS headers for development
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)
    
    headers = {'Access-Control-Allow-Origin': '*'}
    
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({
                'error': 'No file provided',
                'message': 'Please upload a PDF file'
            }), 400, headers
        
        file = request.files['file']
        
        # Check if file is selected
        if file.filename == '':
            return jsonify({
                'error': 'No file selected',
                'message': 'Please select a PDF file'
            }), 400, headers
        
        # Check file extension
        if not allowed_file(file.filename):
            return jsonify({
                'error': 'Invalid file type',
                'message': 'Only PDF files are allowed'
            }), 400, headers
        
        # Read file content
        file_content = file.read()
        
        # Check file size
        if len(file_content) > MAX_FILE_SIZE_BYTES:
            return jsonify({
                'error': 'File too large',
                'message': f'Maximum file size is {MAX_FILE_SIZE_MB}MB'
            }), 400, headers
        
        # Basic check that it's actually a PDF (starts with %PDF)
        if not file_content.startswith(b'%PDF'):
            return jsonify({
                'error': 'Invalid PDF',
                'message': 'File does not appear to be a valid PDF'
            }), 400, headers
        
        # Generate unique job ID
        job_id = f"job-{uuid.uuid4()}"
        filename = secure_filename(file.filename)
        
        # Upload to GCS
        bucket_name = os.environ.get('GCS_BUCKET_NAME', 'pdf-lecture-uploads')
        storage_path = upload_to_gcs(bucket_name, job_id, filename, file_content)
        
        # Create job record in Firestore
        create_job_record(job_id, filename, len(file_content), storage_path)
        
        # Trigger document analysis
        trigger_document_analysis(job_id)
        
        # Return success response
        return jsonify({
            'success': True,
            'jobId': job_id,
            'message': 'PDF uploaded successfully',
            'pdf': {
                'filename': filename,
                'size_mb': round(len(file_content) / (1024 * 1024), 2)
            },
            'status': 'processing',
            'statusUrl': f'/api/status/{job_id}'
        }), 200, headers
        
    except Exception as e:
        print(f"Error processing upload: {str(e)}")
        return jsonify({
            'error': 'Upload failed',
            'message': str(e)
        }), 500, headers
