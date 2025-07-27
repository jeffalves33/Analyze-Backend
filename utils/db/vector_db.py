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
    
    def store_document(self, 
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
                  subcategory: Optional[str] = None) -> None:
        """Armazena documento no banco vetorial com metadata estruturada"""

        # Validações
        if not content or content.strip() == "":
            raise ValueError("Conteúdo do documento não pode estar vazio")
        if scope in ["agency", "client"] and not agency_id:
            raise ValueError("agency_id é obrigatório para scope 'agency' ou 'client'")
        if scope == "client" and not client_id:
            raise ValueError("client_id é obrigatório para scope 'client'")
        
        # Monta metadata
        metadata = {
            "scope": scope,
            "doc_type": doc_type,
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "confidentiality": confidentiality
        }
        
        # Adiciona IDs conforme escopo
        if scope in ["agency", "client"]:
            metadata["agency_id"] = agency_id
        if scope == "client":
            metadata["client_id"] = client_id
            
        # Adiciona campos opcionais
        if tags:
            metadata["tags"] = tags
        if author:
            metadata["author"] = author
        if context:
            # MODIFICAÇÃO: Adiciona context como campos separados na metadata
            for key, value in context.items():
                metadata[f"context_{key}"] = str(value)
        if main_category:
            metadata["main_category"] = main_category
        if subcategory:
            metadata["subcategory"] = subcategory
        
        # Cria documento
        document = Document(page_content=content, metadata=metadata)
        
        # Obtém vector DB do escopo correto
        vectordb = self.get_vector_db(scope, agency_id, client_id)
        
        # Adiciona documento
        vectordb.add_documents([document])
    
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