# ===== Arquivo: routers/document_router.py =====
from fastapi import APIRouter, HTTPException
from models.document_request import DocumentRequest
from services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/store")
async def store_document(request: DocumentRequest):
    try:
        result = DocumentService.store_document(request)
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))