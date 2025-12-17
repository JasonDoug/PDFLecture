"""
Local Development Server
Run both Cloud Functions locally for testing
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("Starting local development server...")
print(f"Project ID: {os.getenv('GCP_PROJECT_ID')}")
print(f"Bucket: {os.getenv('GCS_BUCKET_NAME')}")
print(f"Gemini API Key: {'Set' if os.getenv('GEMINI_API_KEY') else 'Not set'}")
print("\nAvailable endpoints:")
print("- Upload PDF: POST http://localhost:8080/upload")
print("- Analyze Document: POST http://localhost:8081/analyze (with JSON: {\"jobId\": \"...\"})")
print("\nPress Ctrl+C to stop\n")

# Note: Run functions separately using:
# functions-framework --target=upload_pdf --source=upload_handler/main.py --port=8080 --debug
# functions-framework --target=analyze_document_http --source=document_analyzer/main.py --port=8081 --debug
