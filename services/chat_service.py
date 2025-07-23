# services/chat_service.py
import os
from openai import OpenAI
from utils.db.vector_db import VectorDBManager

class ChatService:
    def __init__(self):
        self.vector_db_manager = VectorDBManager(
            pinecone_api_key=os.getenv("PINECONE_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_chat_response(self, client_id: int, prompt: str, history: list):
        vectordb = self.vector_db_manager.create_or_load_vector_db(str(client_id))

        retriever = vectordb.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 10}
        )

        context_docs = retriever.invoke(prompt)
        context_text = "\n\n".join([doc.page_content for doc in context_docs])

        openai_messages = []

        system_message = f"""
        Você é um assistente especializado em análise de dados de marketing digital para o cliente {client_id}.
        Responda de maneira profissional e direta.

        Contexto relevante:
        {context_text}

        Se não tiver informação suficiente, responda de maneira sincera.
        """
        openai_messages.append({"role": "system", "content": system_message})

        # Limita o histórico às últimas 8 mensagens
        for msg in history[-8:]:
            openai_messages.append({"role": msg["role"], "content": msg["content"]})

        openai_messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=openai_messages,
            temperature=0.2
        )

        return response.choices[0].message.content
