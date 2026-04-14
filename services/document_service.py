# ===== Arquivo: services/document_service.py =====
from utils.advanced_data_analyst import AdvancedDataAnalyst
from models.document_request import (
    DocumentRequest,
    DocumentListRequest,
    DocumentDetailsRequest,
    DocumentDeleteRequest,
    DocumentDeleteBatchRequest,
)
from typing import Dict, Any, Optional


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

    # ─── Debug ────────────────────────────────────────────────────────────────

    @classmethod
    def debug_list(
        cls,
        agency_id: str,
        client_id: Optional[str],
        scope: str,
        top_k: int = 100,
    ) -> Dict[str, Any]:
        """
        Diagnóstico: retorna dados brutos do Pinecone sem filtros de metadata.
        Mostra namespace usado, total de vetores encontrados e metadata de cada um.
        """
        try:
            vdb = cls.analyst.vector_db
            namespace = vdb._get_namespace(scope=scope, agency_id=agency_id, client_id=client_id)
            index = vdb.pc.Index(vdb.main_index_name)

            # Query SEM nenhum filtro de metadata
            dummy_vector = [0.0] * 1536
            dummy_vector[0] = 1.0

            raw = index.query(
                vector=dummy_vector,
                top_k=min(top_k, 10_000),
                namespace=namespace,
                include_metadata=True,
                include_values=False,
            )

            vectors_raw = []
            for match in raw.matches:
                md = match.metadata or {}
                vectors_raw.append({
                    "id": match.id,
                    "score": round(match.score, 6) if match.score is not None else None,
                    "metadata_agency_id": md.get("agency_id"),
                    "metadata_agency_id_type": type(md.get("agency_id")).__name__,
                    "metadata_client_id": md.get("client_id"),
                    "metadata_client_id_type": type(md.get("client_id")).__name__,
                    "metadata_doc_type": md.get("doc_type"),
                    "metadata_scope": md.get("scope"),
                    "metadata_source": md.get("source"),
                    "metadata_created_at": md.get("created_at"),
                    "metadata_author": md.get("author"),
                    "all_metadata_keys": list(md.keys()),
                })

            # Estatísticas de consistência de metadata
            agency_id_values = list({v["metadata_agency_id"] for v in vectors_raw})
            client_id_values = list({v["metadata_client_id"] for v in vectors_raw})
            agency_id_types  = list({v["metadata_agency_id_type"] for v in vectors_raw})
            client_id_types  = list({v["metadata_client_id_type"] for v in vectors_raw})

            return {
                "debug": True,
                "namespace_used": namespace,
                "index_name": vdb.main_index_name,
                "query_agency_id": agency_id,
                "query_agency_id_type": type(agency_id).__name__,
                "query_client_id": client_id,
                "query_client_id_type": type(client_id).__name__ if client_id is not None else "NoneType",
                "total_vectors_found": len(vectors_raw),
                "distinct_agency_id_values_in_metadata": agency_id_values,
                "distinct_agency_id_types_in_metadata": agency_id_types,
                "distinct_client_id_values_in_metadata": client_id_values,
                "distinct_client_id_types_in_metadata": client_id_types,
                "vectors": vectors_raw,
            }
        except Exception as e:
            return {"debug": True, "error": str(e), "error_type": type(e).__name__}