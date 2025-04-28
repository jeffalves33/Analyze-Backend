# utils/db/vector_db.py
import hashlib
from typing import List, Optional, Dict, Any
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
import pandas as pd

class VectorDBManager:
    def __init__(self, pinecone_api_key: str, openai_api_key: str):
        self.pinecone_api_key = pinecone_api_key
        # Initialize Pinecone
        self.pc = Pinecone(api_key=pinecone_api_key)
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(api_key=openai_api_key)
    
    def _get_client_id_hash(self, client_id: str) -> str:
        return hashlib.md5(str(client_id).encode()).hexdigest()

    def _get_pinecone_index_name(self, client_id: str) -> str:
        return f"client-{self._get_client_id_hash(client_id)[:10]}"
    
    def _create_or_get_pinecone_index(self, client_id: str) -> str:
        index_name = self._get_pinecone_index_name(client_id)
        
        # Check if index exists
        if index_name not in [index.name for index in self.pc.list_indexes()]:
            # Create new index
            self.pc.create_index(
                name=index_name,
                dimension=1536,  # Dimension for OpenAI embeddings
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
        
        return index_name

    def create_or_load_vector_db(self, client_id: str, force_reload: bool = False) -> PineconeVectorStore:
        index_name = self._create_or_get_pinecone_index(client_id)
        
        # If force_reload is True, clear existing index
        if force_reload:
            index = self.pc.Index(index_name)
            index.delete(delete_all=True)
        
        # Converta o client_id para string para usar como namespace
        client_id_str = str(client_id)
        
        # Just load the index since data already exists in vector database
        return PineconeVectorStore(
            index_name=index_name,
            embedding=self.embeddings,
            namespace=client_id_str
        )
    
    def generate_data_summary(self, df: pd.DataFrame, client_id: str, platform: str) -> List[Document]:
        summary_texts = []
        
        # Basic dataframe info
        info_str = f"Dataset para cliente {client_id} na plataforma {platform} contém {len(df)} linhas e {len(df.columns)} colunas.\n"
        info_str += f"Colunas: {', '.join(df.columns)}\n"
        
        # Data types
        dtypes_str = "Tipos de dados das colunas:\n"
        for col, dtype in df.dtypes.items():
            dtypes_str += f"- {col}: {dtype}\n"
        
        # Basic statistics for numeric columns
        stats_str = "Estatísticas básicas para colunas numéricas:\n"
        numeric_cols = df.select_dtypes(include=['number']).columns
        if not numeric_cols.empty:
            stats = df[numeric_cols].describe().to_string()
            stats_str += stats + "\n"
        
        # Missing values
        missing_str = "Valores ausentes:\n"
        for col in df.columns:
            missing_count = df[col].isna().sum()
            if missing_count > 0:
                missing_str += f"- {col}: {missing_count} valores ausentes ({missing_count/len(df)*100:.2f}%)\n"
        
        # Date range if there are date columns
        date_str = "Informações de datas:\n"
        date_cols = ['data']  # Based on your schema
        for col in date_cols:
            if col in df.columns:
                try:
                    df[col] = pd.to_datetime(df[col])
                    min_date = df[col].min()
                    max_date = df[col].max()
                    date_str += f"- {col}: de {min_date} até {max_date}\n"
                except:
                    date_str += f"- {col}: não foi possível converter para datetime\n"
        
        # Create documents
        summary_texts.append(Document(page_content=info_str, metadata={"type": "dataset_info", "client_id": client_id, "platform": platform}))
        summary_texts.append(Document(page_content=dtypes_str, metadata={"type": "data_types", "client_id": client_id, "platform": platform}))
        summary_texts.append(Document(page_content=stats_str, metadata={"type": "statistics", "client_id": client_id, "platform": platform}))
        summary_texts.append(Document(page_content=missing_str, metadata={"type": "missing_values", "client_id": client_id, "platform": platform}))
        summary_texts.append(Document(page_content=date_str, metadata={"type": "date_info", "client_id": client_id, "platform": platform}))
        
        return summary_texts

    def store_analysis_in_vectordb(self, client_id: str, query: str, result: str, platform: str) -> None:
        from datetime import datetime
        
        # Prepare document
        timestamp = datetime.now().isoformat()
        document = Document(
            page_content=f"Consulta: {query}\n\nResultado da Análise: {result}",
            metadata={
                "type": "analysis",
                "client_id": str(client_id),
                "platform": platform,
                "timestamp": timestamp,
                "query": query
            }
        )
        
        # Get the vector DB
        vectordb = self.create_or_load_vector_db(client_id)
        
        # Add the document to Pinecone
        vectordb.add_documents([document])