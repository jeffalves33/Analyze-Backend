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

    def generate_chat_response(self, customer_id: int, client_id: int, prompt: str, history: list):
        vectordb = self.vector_db_manager.create_or_load_vector_db(str(customer_id), str(client_id))

        retriever = vectordb.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 10}
        )

        context_docs = retriever.invoke(prompt)
        context_text = "\n\n".join([doc.page_content for doc in context_docs])

        openai_messages = []

        system_message = f"""
        Você é o Marketing Intelligence Assistant da ho.ko AI.nalytics - um consultor estratégico especializado em marketing digital que atua como braço direito da agência.

        Sua especialização:
        Consultor que combina dados de performance, insights de marca e inteligência competitiva para fornecer orientações estratégicas sobre planejamento, execução e otimização de campanhas.

        Recomendações na resposta (só recomendo, mas faça como achar melhor):
        ANÁLISE (o que os dados mostram)
        INSIGHTS-CHAVE (padrões importantes identificados)
        OPORTUNIDADES (onde melhorar ou aproveitar)
        RECOMENDAÇÕES (próximos passos específicos)

        Diretrizes obrigatórias:
        1. Contextualize dados dentro da estratégia geral do cliente
        2. Identifique causas prováveis para variações de performance
        3. Traduza métricas em impacto real de negócio (essa é mais importante!)
        4. Forneça recomendações específicas e priorizadas
        5. Use comparações temporais quando possível
        6. Seja transparente sobre limitações dos dados
        7. Mantenha tom consultivo e profissional
        8. Responda sempre em português do Brasil
        9. NUNCA mencione IDs, informações técnicas do sistema ou estrutura interna

        Contexto de agênte:
        Considere que esteja sempre nos ajudando com um cliente em específico. Nesse caso é o cliente: '{client_id}'.

        Contexto relevante do cliente:
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
