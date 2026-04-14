# ===== Arquivo: services/document_service.py =====
from utils.advanced_data_analyst import AdvancedDataAnalyst
from models.document_request import (
    DocumentRequest,
    DocumentListRequest,
    DocumentDetailsRequest,
    DocumentDeleteRequest,
    DocumentDeleteBatchRequest,
)
from typing import Dict, Any


class DocumentService:
    analyst = AdvancedDataAnalyst()

    @classmethod
    def store_document(cls, request: DocumentRequest) -> Dict[str, Any]:
        try:
            tags_list = [tag.strip() for tag in request.documentTags.split(",")]

            context = {
                "customer_name": request.customerName,
                "setor": request.documentSetor,
                "upload_type": request.uploadType,
            }

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
                subcategory=request.subcategory,
            )

            return {
                "status": "success",
                "message": "Documento armazenado com sucesso",
                "document_id": f"{request.client_id}_{request.docType}",
                "stored_at": "vector_db",
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Erro ao armazenar documento: {str(e)}",
            }

    # ─── Listagem ─────────────────────────────────────────────────────────────

    @classmethod
    def list_documents(cls, request: DocumentListRequest) -> Dict[str, Any]:
        try:
            documents = cls.analyst.vector_db.list_documents(
                agency_id=request.agency_id,
                client_id=request.client_id,
                scope=request.scope.value,
                doc_type=request.doc_type,
                limit=request.limit,
            )
            return {
                "status": "success",
                "total": len(documents),
                "documents": documents,
            }
        except Exception as e:
            return {
                "status": "error",
                "total": 0,
                "documents": [],
                "message": f"Erro ao listar documentos: {str(e)}",
            }

    # ─── Detalhes ─────────────────────────────────────────────────────────────

    @classmethod
    def get_document_details(cls, request: DocumentDetailsRequest) -> Dict[str, Any]:
        try:
            doc = cls.analyst.vector_db.get_document_details(
                vector_id=request.vector_id,
                agency_id=request.agency_id,
                client_id=request.client_id,
                scope=request.scope.value,
            )
            if doc is None:
                return {
                    "status": "not_found",
                    "document": None,
                    "message": f"Documento '{request.vector_id}' não encontrado no namespace.",
                }
            return {"status": "success", "document": doc}
        except Exception as e:
            return {
                "status": "error",
                "document": None,
                "message": f"Erro ao buscar detalhes: {str(e)}",
            }

    # ─── Exclusão ─────────────────────────────────────────────────────────────

    @classmethod
    def delete_document(cls, request: DocumentDeleteRequest) -> Dict[str, Any]:
        try:
            cls.analyst.vector_db.delete_document(
                vector_id=request.vector_id,
                agency_id=request.agency_id,
                client_id=request.client_id,
                scope=request.scope.value,
            )
            return {
                "status": "success",
                "deleted_count": 1,
                "message": f"Documento '{request.vector_id}' excluído com sucesso.",
            }
        except Exception as e:
            return {
                "status": "error",
                "deleted_count": 0,
                "message": f"Erro ao excluir documento: {str(e)}",
            }

    @classmethod
    def delete_documents_batch(cls, request: DocumentDeleteBatchRequest) -> Dict[str, Any]:
        try:
            result = cls.analyst.vector_db.delete_documents_batch(
                vector_ids=request.vector_ids,
                agency_id=request.agency_id,
                client_id=request.client_id,
                scope=request.scope.value,
            )
            return {
                "status": "success",
                "deleted_count": result["deleted_count"],
                "message": f"{result['deleted_count']} documento(s) excluído(s) com sucesso.",
            }
        except Exception as e:
            return {
                "status": "error",
                "deleted_count": 0,
                "message": f"Erro ao excluir documentos em lote: {str(e)}",
            }