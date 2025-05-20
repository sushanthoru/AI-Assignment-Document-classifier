from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile

from advanced_document_classifier import AdvancedDocumentClassifier
from initial_document_classifier import InitialDocumentClassifier

app = FastAPI()


initial_classifier = InitialDocumentClassifier()
advanced_classifier = AdvancedDocumentClassifier()

@app.post("/classify")
async def schedule_classify_task(file: Optional[UploadFile] = File(None)):
    """Endpoint to classify a document into "w2", "1040", "1099", etc"""
    
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    # Check if file is a PDF
    if not file.content_type or not file.content_type.lower() != 'application/pdf':
        # Read the file content for classification
        file_copy = await file.read()
        await file.seek(0)
    
    try:
        # First try the initial document classifier for tax forms
        result = await initial_classifier.classify_document(file)
        document_type = result.get("document_type", "OTHER")
        year = result.get("year", "NOT IMPLEMENTED")
        
        # If the initial classifier couldn't determine the type, try the advanced classifier
        if document_type == "OTHER":
            print("Fixed classifier returned OTHER, trying advanced classifier")
            
            await file.seek(0)
            
            # Using the advanced classifier for ID cards and handwritten notes
            advanced_result = await advanced_classifier.classify_document(file)
            document_type = advanced_result.get("document_type")
            
            # If found a specific document type, use the advanced classifier's result
            if document_type == "OTHER":
                print("Fixed classifier returned OTHER, trying advanced classifier")
                await file.seek(0)
                advanced_result = await advanced_classifier.classify_document(file)
                document_type = advanced_result.get("document_type")
                year = advanced_result.get("year", year)

        return {"document_type": document_type, "year": year}

    except Exception as e:
        print(f"Error classifying document: {str(e)}")
        return {"document_type": "OTHER", "year": "NOT IMPLEMENTED"}