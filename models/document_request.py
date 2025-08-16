from pydantic import BaseModel
from typing import Optional, List
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
    
    # Campos opcionais que podem ser úteis
    mainCategory: Optional[str] = None
    subcategory: Optional[str] = None