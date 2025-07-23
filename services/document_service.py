# ===== Arquivo: services/document_service.py =====
from utils.advanced_data_analyst import AdvancedDataAnalyst
from models.document_request import DocumentRequest
from typing import Dict, Any

class DocumentService:
    analyst = AdvancedDataAnalyst()

    @classmethod
    def store_document(cls, request: DocumentRequest) -> Dict[str, Any]:
        try:
            # Converte tags de string para lista
            tags_list = [tag.strip() for tag in request.documentTags.split(",")]
            
            # Monta contexto adicional
            context = {
                "customer_name": request.customerName,
                "setor": request.documentSetor,
                "upload_type": request.uploadType,
            }
            
            # Armazena no vector DB
            cls.analyst.vector_db.store_document(
                content=request.documentText,
                scope=request.documentScope,
                doc_type=request.docType,
                source=f"upload_{request.uploadType}",
                agency_id=request.agency_id,
                client_id=request.client_id,
                tags=tags_list,
                author=request.documentAuthor,
                confidentiality=request.confidentiality,
                context=context,
                main_category=request.mainCategory,
                subcategory=request.subcategory
            )
            
            return {
                "status": "success",
                "message": "Documento armazenado com sucesso",
                "document_id": f"{request.client_id}_{request.docType}",
                "stored_at": "vector_db"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Erro ao armazenar documento: {str(e)}"
            }