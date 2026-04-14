# ===== Arquivo: routers/document_router.py =====
from fastapi import APIRouter, HTTPException
from models.document_request import (
    DocumentRequest,
    DocumentListRequest,
    DocumentListResponse,
    DocumentDetailsRequest,
    DocumentDetailsResponse,
    DocumentDeleteRequest,
    DocumentDeleteBatchRequest,
    DocumentDeleteResponse,
)
from services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/store")
async def store_document(request: DocumentRequest):
    try:
        result = DocumentService.store_document(request)
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/list", response_model=DocumentListResponse)
async def list_documents(request: DocumentListRequest):
    """
    Lista documentos armazenados no Pinecone para um cliente/agência.

    Filtros disponíveis:
    - `agency_id` (obrigatório): ID da agência.
    - `client_id` (opcional): ID do cliente; se omitido, lista do escopo da agência.
    - `scope`: 'client' | 'agency' | 'global' (padrão: 'client').
    - `doc_type`: filtro por tipo de documento (ex: 'analise', 'brief', 'brand_platform').
    - `limit`: máximo de registros retornados (1–500, padrão: 50).
    """
    try:
        result = DocumentService.list_documents(request)
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/details", response_model=DocumentDetailsResponse)
async def get_document_details(request: DocumentDetailsRequest):
    """
    Retorna metadados completos e texto de um documento pelo seu ID vetorial.

    O `vector_id` é o ID retornado pelo endpoint `/documents/list`.
    """
    try:
        result = DocumentService.get_document_details(request)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=result.get("message"))
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete", response_model=DocumentDeleteResponse)
async def delete_document(request: DocumentDeleteRequest):
    """
    Exclui um documento do Pinecone pelo seu ID vetorial.

    **Atenção:** a exclusão é permanente e irreversível.
    """
    try:
        result = DocumentService.delete_document(request)
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/batch", response_model=DocumentDeleteResponse)
async def delete_documents_batch(request: DocumentDeleteBatchRequest):
    """
    Exclui múltiplos documentos em lote pelo lista de IDs vetoriais.

    **Atenção:** a exclusão é permanente e irreversível.
    """
    try:
        result = DocumentService.delete_documents_batch(request)
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))