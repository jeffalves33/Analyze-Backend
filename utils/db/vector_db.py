# ===== Arquivo: utils/db/vector_db.py =====

from typing import List, Optional, Dict, Any, Literal
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
import pandas as pd
from datetime import datetime

class VectorDBManager:
    def __init__(self, pinecone_api_key: str, openai_api_key: str):
        self.pinecone_api_key = pinecone_api_key
        self.pc = Pinecone(api_key=pinecone_api_key)
        self.embeddings = OpenAIEmbeddings(api_key=openai_api_key)
        self.main_index_name = "hokoainalytics"
    
    def ingest_brand_platform(self, agency_id: str, text: str, tags: Optional[List[str]] = None):
        """
        Ingesta/atualiza o documento de plataforma de marca da agência.
        'text' deve ser o conteúdo extraído do PDF (faça a extração no seu pipeline).
        """
        self.store_document(
            content=text,
            scope="agency",
            doc_type="brand_platform",
            source="brand_pdf",
            agency_id=agency_id,
            client_id=None,
            tags=(tags or []) + ["voz", "tom", "proposta_valor", "guidelines"],
            author="branding",
            confidentiality="media",
            main_category="brand",
            subcategory="voice"
        )

    def _get_vectorstore(self, namespace: str) -> PineconeVectorStore:
        idx = self._create_or_get_main_index()
        return PineconeVectorStore(index_name=idx, embedding=self.embeddings, namespace=namespace, text_key="text")

    def _assemble_context_block(self, docs: List[Document]) -> str:
        """Concatena conteúdos com pequenas fichas de origem úteis à narrativa."""
        lines = []
        for d in docs:
            md = d.metadata or {}
            badge = f"[{md.get('doc_type','?')} • {md.get('source','?')} • {md.get('created_at','')} • ag:{md.get('agency_id')} cl:{md.get('client_id')}]"
            lines.append(f"{badge}\n{d.page_content.strip()}\n")
        return "\n---\n".join(lines)

    def retrieve_context_for_analysis(
        self,
        query: str,
        scope: Literal["agency", "client"],
        agency_id: str,
        client_id: Optional[str] = None,
        k_total: int = 8
    ) -> str:
        """
        Multi-pass retrieval priorizando:
        1) Voz/objetivos (brand_platform, objetivos, brief)
        2) Análises / relatórios recentes
        3) Fallback geral
        Usa MMR para reduzir redundância (fetch_k > k).
        """
        namespace = self._get_namespace(scope=scope, agency_id=agency_id, client_id=client_id)
        vs = self._get_vectorstore(namespace)

        collected: List[Document] = []

        # Passo 1 — marca/voz/objetivos (foco em agency)
        brand_filter = {
            "$and": [
                {"doc_type": {"$in": ["brand_platform", "objetivos", "brief"]}},
                {"agency_id": {"$eq": agency_id}}
            ]
        }
        top_brand = vs.max_marginal_relevance_search(
            query, k=min(3, k_total), fetch_k=25, lambda_mult=0.5, filter=brand_filter
        )
        collected.extend(top_brand)

        # Passo 2 — análises/relatórios recentes (quando client)
        if client_id:
            report_filter = {
                "$and": [
                    {"doc_type": {"$in": ["analise", "relatorio"]}},
                    {"agency_id": {"$eq": agency_id}},
                    {"client_id": {"$eq": client_id}}
                ]
            }
            k_left = max(0, k_total - len(collected))
            if k_left > 0:
                top_reports = vs.max_marginal_relevance_search(
                    query, k=min(3, k_left), fetch_k=25, lambda_mult=0.5, filter=report_filter
                )
                collected.extend(top_reports)

        # Passo 3 — fallback geral (sem filtro) se ainda faltar contexto
        k_left = max(0, k_total - len(collected))
        if k_left > 0:
            fallback = vs.max_marginal_relevance_search(query, k=k_left, fetch_k=25, lambda_mult=0.5)
            collected.extend(fallback)

        return self._assemble_context_block(collected)

    def _create_or_get_main_index(self) -> str:
        """Cria ou obtém o índice principal do Pinecone"""
        if self.main_index_name not in [index.name for index in self.pc.list_indexes()]:
            self.pc.create_index(
                name=self.main_index_name,
                dimension=1536,  # Dimension for OpenAI embeddings
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
        return self.main_index_name
    
    def _get_namespace(self, scope: Literal["global", "agency", "client"], 
                      agency_id: Optional[str] = None, 
                      client_id: Optional[str] = None) -> str:
        """Gera o namespace baseado no escopo e IDs"""
        if scope == "global":
            return "global"
        elif scope == "agency":
            if not agency_id:
                raise ValueError("agency_id é obrigatório para scope 'agency'")
            return f"agency_{agency_id}"
        elif scope == "client":
            if not agency_id or not client_id:
                raise ValueError("agency_id e client_id são obrigatórios para scope 'client'")
            return f"client_{agency_id}_{client_id}"
        else:
            raise ValueError(f"Scope inválido: {scope}")
    
    def create_or_load_vector_db(self, customer_id:str, client_id: str, force_reload: bool = False) -> PineconeVectorStore:
        """Mantém compatibilidade com código existente - assume scope 'client'"""
        # Para compatibilidade, extrai agency_id do client_id se possível
        # Assumindo formato "agencia_cliente" ou similar
        if "_" in client_id:
            parts = client_id.split("_", 1)
            agency_id = parts[0]
            actual_client_id = parts[1]
        else:
            # Fallback: usa o client_id como agency_id também
            agency_id = client_id
            actual_client_id = client_id

        return self.get_vector_db(scope="client", agency_id=client_id, client_id=customer_id, force_reload=force_reload)
    
    def get_vector_db(self, scope: Literal["global", "agency", "client"], 
                     agency_id: Optional[str] = None, 
                     client_id: Optional[str] = None,
                     force_reload: bool = False) -> PineconeVectorStore:
        """Obtém ou cria vector DB para o escopo especificado"""
        index_name = self._create_or_get_main_index()
        namespace = self._get_namespace(scope, agency_id, client_id)
        
        if force_reload:
            index = self.pc.Index(index_name)
            index.delete(delete_all=True, namespace=namespace)
        
        return PineconeVectorStore(
            index_name=index_name,
            embedding=self.embeddings,
            namespace=namespace
        )
    
    def store_document(
        self, 
        content: str,
        scope: Literal["global", "agency", "client"],
        doc_type: str,
        source: str,
        agency_id: Optional[str] = None,
        client_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        author: Optional[str] = None,
        confidentiality: str = "media",
        context: Optional[Dict[str, Any]] = None,
        main_category: Optional[str] = None,
        subcategory: Optional[str] = None
    ) -> None:
        """Armazena documento no banco vetorial com metadata estruturada e consistente"""

        namespace = self._get_namespace(scope=scope, agency_id=agency_id, client_id=client_id)
        idx = self._create_or_get_main_index()  # mantém sua lógica atual

        # -- METADATA padronizada para habilitar filtros:
        metadata = {
            "scope": scope,                      # "global" | "agency" | "client"
            "doc_type": doc_type,                # ex: "brand_platform", "objetivos", "analise", "relatorio", "brief"
            "source": source,                    # ex: "brand_pdf", "sistema", "upload_usuario"
            "agency_id": agency_id,
            "client_id": client_id,
            "tags": tags or [],
            "author": author or "desconhecido",
            "confidentiality": confidentiality,  # baixa | media | alta
            "main_category": main_category,      # ex: "brand", "performance", "planejamento"
            "subcategory": subcategory,          # ex: "voice", "guidelines", "kpis"
            "created_at": datetime.utcnow().isoformat() + "Z",
            "context": context or {},
        }

        # **Importante**: Pinecone aceita filtros por metadados; manter chaves simples/flat ajuda.
        # Upsert via LangChain:
        vectorstore = PineconeVectorStore(
            index_name=idx, 
            embedding=self.embeddings, 
            namespace=namespace, 
            text_key="text"
        )
        vectorstore.add_texts(texts=[content], metadatas=[metadata])

    def generate_data_summary(self, df: pd.DataFrame, client_id: str, platform: str) -> List[Document]:
        """Gera sumário de dados - atualizado para nova estrutura"""
        # Extrai agency_id do client_id
        if "_" in client_id:
            parts = client_id.split("_", 1)
            agency_id = parts[0]
            actual_client_id = parts[1]
        else:
            agency_id = client_id
            actual_client_id = client_id
        
        summary_texts = []
        
        # Informações básicas do dataset
        info_str = f"Dataset para cliente {actual_client_id} da agência {agency_id} na plataforma {platform} contém {len(df)} linhas e {len(df.columns)} colunas.\n"
        info_str += f"Colunas: {', '.join(df.columns)}\n"
        
        # Tipos de dados
        dtypes_str = "Tipos de dados das colunas:\n"
        for col, dtype in df.dtypes.items():
            dtypes_str += f"- {col}: {dtype}\n"
        
        # Estatísticas básicas para colunas numéricas
        stats_str = "Estatísticas básicas para colunas numéricas:\n"
        numeric_cols = df.select_dtypes(include=['number']).columns
        if not numeric_cols.empty:
            stats = df[numeric_cols].describe().to_string()
            stats_str += stats + "\n"
        
        # Valores ausentes
        missing_str = "Valores ausentes:\n"
        for col in df.columns:
            missing_count = df[col].isna().sum()
            if missing_count > 0:
                missing_str += f"- {col}: {missing_count} valores ausentes ({missing_count/len(df)*100:.2f}%)\n"
        
        # Informações de datas
        date_str = "Period: "
        date_cols = ['data']
        for col in date_cols:
            if col in df.columns:
                try:
                    df[col] = pd.to_datetime(df[col])
                    min_date = df[col].min()
                    max_date = df[col].max()
                    date_str += f"{min_date} até {max_date}\n"
                except:
                    date_str += f"não foi possível converter para datetime\n"
        
        # Cria documentos com nova estrutura de metadata
        base_metadata = {
            "scope": "client",
            "agency_id": agency_id,
            "client_id": actual_client_id,
            "source": platform,
            "timestamp": datetime.now().isoformat(),
            "confidentiality": "media"
        }
        
        documents_data = [
            (info_str, "dataset_info"),
            (dtypes_str, "data_types"),
            (stats_str, "statistics"),
            (missing_str, "missing_values"),
            (date_str, "date_info")
        ]
        
        for content, doc_type in documents_data:
            metadata = base_metadata.copy()
            metadata["doc_type"] = doc_type
            metadata["tags"] = ["dados", "sumario", platform]
            
            summary_texts.append(Document(page_content=content, metadata=metadata))
        
        return summary_texts

    def store_analysis_summary(self, 
                          agency_id: str, 
                          client_id: str, 
                          query: str, 
                          platforms: List[str],
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> None:
        """Armazena resumo conciso da análise realizada"""
        
        # Determina período da análise
        if start_date and end_date:
            period = f"{start_date} até {end_date}"
        elif start_date:
            period = f"a partir de {start_date}"
        elif end_date:
            period = f"até {end_date}"
        else:
            period = "período completo dos dados"
        
        # Cria conteúdo resumido
        content = f"Análise realizada para as plataformas {', '.join(platforms)} no período: {period}. Consulta: {query[:200]}{'...' if len(query) > 200 else ''}"
        
        # Monta metadata completa conforme sua estrutura
        context = {
            "platforms": platforms,
            "query": query[:500] if len(query) > 500 else query,
            "period": period
        }
        
        self.store_document(
            content=content,
            scope="client",
            doc_type="analise",
            source="sistema",
            agency_id=agency_id,
            client_id=client_id,
            tags=["analise", "metricas"] + platforms,
            author="sistema_analise",
            confidentiality="media",
            context=context
        )