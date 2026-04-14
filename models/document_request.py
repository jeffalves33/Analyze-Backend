from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from enum import Enum


class DocumentScope(str, Enum):
    global_scope = "global"
    agency = "agency"
    client = "client"


class UploadType(str, Enum):
    text = "text"
    pdf = "pdf"
    txt = "txt"
    csv = "csv"


class DocumentRequest(BaseModel):
    documentScope: DocumentScope
    docType: str
    confidentiality: str
    documentAuthor: str
    documentSetor: str
    documentTags: str
    uploadType: UploadType
    agency_id: str
    documentText: str
    client_id: str
    customerName: str

    mainCategory: Optional[str] = None
    subcategory: Optional[str] = None


# ─── Listagem ────────────────────────────────────────────────────────────────

class DocumentListRequest(BaseModel):
    agency_id: str
    client_id: Optional[str] = None
    scope: DocumentScope = DocumentScope.client
    doc_type: Optional[str] = Field(None, description="Filtrar por tipo de documento (ex: 'analise', 'brief')")
    limit: int = Field(50, ge=1, le=500, description="Máximo de documentos retornados")


class DocumentItem(BaseModel):
    id: str
    doc_type: Optional[str] = None
    source: Optional[str] = None
    author: Optional[str] = None
    agency_id: Optional[str] = None
    client_id: Optional[str] = None
    scope: Optional[str] = None
    tags: List[str] = []
    main_category: Optional[str] = None
    subcategory: Optional[str] = None
    confidentiality: Optional[str] = None
    created_at: Optional[str] = None
    ctx_customer_name: Optional[str] = None


class DocumentListResponse(BaseModel):
    status: str
    total: int
    documents: List[DocumentItem]


# ─── Detalhes ─────────────────────────────────────────────────────────────────

class DocumentDetailsRequest(BaseModel):
    vector_id: str
    agency_id: str
    client_id: Optional[str] = None
    scope: DocumentScope = DocumentScope.client


class DocumentDetailsResponse(BaseModel):
    status: str
    document: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


# ─── Exclusão ────────────────────────────────────────────────────────────────

class DocumentDeleteRequest(BaseModel):
    vector_id: str
    agency_id: str
    client_id: Optional[str] = None
    scope: DocumentScope = DocumentScope.client


class DocumentDeleteBatchRequest(BaseModel):
    vector_ids: List[str] = Field(..., min_length=1, description="Lista de IDs a excluir")
    agency_id: str
    client_id: Optional[str] = None
    scope: DocumentScope = DocumentScope.client


class DocumentDeleteResponse(BaseModel):
    status: str
    deleted_count: int
    message: str