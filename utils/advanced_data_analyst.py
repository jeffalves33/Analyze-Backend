import os
import pandas as pd
import numpy as np
from typing import Dict, Optional, Any
from datetime import datetime

# LangChain imports
from langchain.agents.agent_types import AgentType
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_experimental.tools import PythonAstREPLTool
from langchain_openai import ChatOpenAI

# utils/advanced_data_analyst.py
from utils.db.relational_db import RelationalDBManager
from utils.db.vector_db import VectorDBManager
from utils.prompts.system_prompts import get_platform_prompt, get_analysis_prompt


class AdvancedDataAnalyst:
    
    def __init__(self, openai_api_key: str = None, pinecone_api_key: str = None, db_connection_string: str = None):
        # Carregar configurações
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        self.pinecone_api_key = pinecone_api_key or os.getenv('PINECONE_API_KEY')
        
        # Inicializar gerenciadores de banco de dados
        self.relational_db = RelationalDBManager(db_connection_string)
        self.vector_db = VectorDBManager(self.pinecone_api_key, self.openai_api_key)
        
        # Cache para armazenar agentes em memória
        self.clients_cache = {}
            
    def _enhanced_agent_invoke(self, agent, retriever, client_id, platform, input_query, custom_options=None):
        # Primeiro, obtenha o contexto relevante do banco de dados vetorial
        context_docs = retriever.get_relevant_documents(input_query)
        context_text = "\n\n".join([doc.page_content for doc in context_docs])
        
        # Enhance the query with relevant context
        enhanced_query = f"""
        Informações de contexto de análises anteriores e resumos de dados:
        {context_text}
        
        Plataforma analisada: {platform}
        
        Com base no contexto acima e no conjunto de dados, responda à seguinte solicitação:
        {input_query}
        
        IMPORTANTE:
        1. Responda SEMPRE em português do Brasil, não em inglês.
        """

        # Add custom options if provided
        if custom_options and "format" in custom_options:
            enhanced_query += f"\nFormate sua resposta como {custom_options['format']}."

        # Run the agent with the enhanced query
        try:
            result = agent.invoke({"input": enhanced_query})

            # Store the query and result in the vector database for future reference
            self.vector_db.store_analysis_in_vectordb(client_id, input_query, result.get("output", ""), platform)

            return result
        except Exception as e:
            return {"output": f"Ocorreu um erro durante a análise: {str(e)}"}

    def _create_invoke_function(self, agent, retriever, client_id, platform):
        def invoke_func(input_query, custom_options=None):
            return self._enhanced_agent_invoke(agent, retriever, client_id, platform, input_query, custom_options)
        return invoke_func

    def get_client_agent(self, client_id: str, platform: str, 
                       start_date: Optional[str] = None, 
                       end_date: Optional[str] = None, 
                       force_new: bool = False) -> Any:
        # Verifique se devemos criar um novo agente
        if not force_new:
            # Primeira verificação no cache de memória
            cache_key = f"{client_id}_{platform}"
            if cache_key in self.clients_cache:
                cache_data = self.clients_cache[cache_key]
                return self._create_invoke_function(
                    cache_data["agent_obj"], 
                    cache_data["retriever"], 
                    client_id,
                    platform
                )

            # Tenta buscar agent_data no banco
            # stored_agent = self.relational_db.get_client_agent(client_id, platform)
            # if stored_agent:
            #     self.clients_cache[cache_key] = stored_agent
            #     return self._create_invoke_function(
            #         stored_agent["agent_obj"], 
            #         stored_agent["retriever"], 
            #         client_id,
            #         platform
            #     )


        # Se precisarmos criar um novo agente
        # Obtenha dados do cliente do banco de dados com filtragem de data
        df = self.relational_db.get_client_data(client_id, platform, start_date, end_date)

        # Set up vector database
        vectordb = self.vector_db.create_or_load_vector_db(client_id)
        retriever = vectordb.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 10}
        )

        # Create LLM instance with system prompt
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.2,
            api_key=self.openai_api_key
        )

        # Get platform-specific prompt
        platform_system_prompt = get_platform_prompt(platform)

        # Create pandas dataframe agent
        agent = create_pandas_dataframe_agent(
            llm=llm,
            df=df,
            agent_type=AgentType.OPENAI_FUNCTIONS,
            verbose=True,
            extra_tools=[PythonAstREPLTool()],
            prefix=platform_system_prompt,
            include_df_in_prompt=True,
            max_iterations=8,
            max_execution_time=60,
            allow_dangerous_code=True
        )

        # Create agent data to store
        agent_data = {
            "agent_obj": agent,
            "retriever": retriever,
            "df": df,
            "timestamp": datetime.now().timestamp(),
            "metadata": {
                "client_id": client_id,
                "platform": platform,
                "row_count": len(df),
                "column_count": len(df.columns)
            }
        }

        # Store in memory cache
        cache_key = f"{client_id}_{platform}"
        self.clients_cache[cache_key] = agent_data

        # Store in database
        #self.relational_db.store_client_agent(client_id, platform, agent_data)

        # Return invoke function directly
        return self._create_invoke_function(agent, retriever, client_id, platform)

    def run_analysis(self, client_id: str, platform: str, analysis_type: str, 
               custom_query: Optional[str] = None,
               start_date: Optional[str] = None, end_date: Optional[str] = None,
               output_format: str = "detalhado") -> Dict:
        from datetime import datetime

        # Preparar cláusula de filtro de data
        date_filter = ""
        if start_date and end_date:
            date_filter = f" para o período de {start_date} até {end_date}"
        elif start_date:
            date_filter = f" a partir de {start_date}"
        elif end_date:
            date_filter = f" até {end_date}"

        # Preparar consulta com base no tipo de análise
        if custom_query:
            query = custom_query
        else:
            # Obter análise de prompts do módulo importado
            query = get_analysis_prompt(analysis_type, platform, date_filter)

        # Obtenha a função de invocação do agente
        invoke_func = self.get_client_agent(client_id, platform, start_date, end_date)

        # Configure custom options
        options = {
            "format": output_format
        }

        # Run the analysis
        try:
            start_time = datetime.now()
            result = invoke_func(query, options)
            end_time = datetime.now()

            # Package the results
            return {
                "client_id": client_id,
                "platform": platform,
                "analysis_type": analysis_type,
                "query": query,
                "result": result.get("output", "Nenhum resultado gerado"),
                "execution_time": (end_time - start_time).total_seconds(),
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            }
        except Exception as e:
            return {
                "client_id": client_id,
                "platform": platform,
                "analysis_type": analysis_type,
                "query": query,
                "result": f"Falha na análise: {str(e)}",
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e)
            }

