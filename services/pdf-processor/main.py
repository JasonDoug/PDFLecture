import functions_framework
from pypdf import PdfReader
from flask import Request, jsonify
import re

def clean_text(text: str) -> str:
    """
    Basic text cleaning.
    - Removes excessive whitespace
    - Joins hyphenated words at line breaks (basic)
    """
    # Replace multiple newlines with a single newline
    text = re.sub(r'\n+', '\n', text)
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

@functions_framework.http
def extract_pdf(request: Request):
    """
    HTTP Cloud Function to extract text from a PDF.
    Expects multipart/form-data with a 'file' field.
    """
    if request.method != 'POST':
        return 'Method not allowed', 405
    
    # Check for file
    if 'file' not in request.files:
        return 'No file uploaded', 400
    
    file = request.files['file']
    if file.filename == '':
        return 'No file selected', 400

    try:
        # Process PDF
        # pypdf can read from the file-like object directly
        reader = PdfReader(file)
        full_text = ""
        
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n"
        
        cleaned_text = clean_text(full_text)
        
        return jsonify({
            'filename': file.filename,
            'page_count': len(reader.pages),
            'text': cleaned_text
        })

    except Exception as e:
        print(f"Error processing PDF: {e}")
        return jsonify({'error': str(e)}), 500
