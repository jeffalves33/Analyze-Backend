# ===== Arquivo: utils/advanced_data_analyst.py =====

import os
import pandas as pd
import numpy as np
from typing import Dict, Optional, Any, List
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

    def _enhanced_agent_invoke(self, agent, agency_id, client_id, platforms_str, input_query):
        """Invoca o agente com contexto hierárquico aprimorado"""

        # Enhance the query with relevant context
        enhanced_query = f"""
            Você é um analista de dados atuando para o cliente da(s) plataforma(s) {platforms_str}.

            Com base nesse contexto e nos dados atuais, responda à seguinte solicitação:
            {input_query}

            IMPORTANTE:
            1. Responda SEMPRE em português do Brasil.
            2. Use linguagem clara, profissional e orientada à gestão.
            3. Destaque oportunidades e riscos quando possível.
            4. Considere as melhores práticas globais, processos da agência e histórico do cliente.
        """
        print("3. _enhanced_agent_invoke: enhanced_query => ", enhanced_query)
        # Run the agent with the enhanced query
        try:
            result = agent.invoke({"input": enhanced_query})
            print("4. _enhanced_agent_invoke: result => ", result)
            # MODIFICAÇÃO: Armazena apenas resumo conciso da análise
            self.vector_db.store_analysis_summary(
                agency_id=agency_id,
                client_id=client_id,
                query=input_query,
                platforms=platforms_str.split(", ")
            )

            return result
        except Exception as e:
            return {"output": f"Ocorreu um erro durante a análise: {str(e)}"}

    def _create_invoke_function(self, agent, agency_id, client_id, platforms_str):
        """Cria função de invocação simplificada"""
        def invoke_func(input_query):
            return self._enhanced_agent_invoke(agent, agency_id, client_id, platforms_str, input_query)
        return invoke_func

    def get_client_agent(self, agency_id: str, client_id: str, platforms: List[str], 
                       start_date: Optional[str] = None, 
                       end_date: Optional[str] = None, 
                       force_new: bool = False) -> Any:
        """Obtém agente do cliente com suporte à nova arquitetura"""

        platforms_str = ", ".join(platforms)

        # Verifica cache se não for forçar novo
        if not force_new:
            cache_key = f"{client_id}_{platforms_str}"
            if cache_key in self.clients_cache:
                cache_data = self.clients_cache[cache_key]
                return self._create_invoke_function(
                    cache_data["agent_obj"],
                    agency_id,
                    client_id,
                    platforms_str
                )

        # Cria novo agente
        print("\n\n== cria um novo agente ==\n\n")
        dfs = []
        for platform in platforms:
            df = self.relational_db.get_client_data(client_id, platform, start_date, end_date)

            # Prefixa colunas, exceto 'data'
            df = df.rename(columns={col: f"{platform}_{col}" for col in df.columns if col != "data"})
            dfs.append(df)

        # Faz merge dos DataFrames
        merged_df = dfs[0]
        for df in dfs[1:]:
            merged_df = pd.merge(merged_df, df, how='outer', on='data')
        
        # Ordena por data e reorganiza colunas
        merged_df = merged_df.sort_values(by="data").reset_index(drop=True)
        cols = merged_df.columns.tolist()
        cols.insert(0, cols.pop(cols.index('data')))
        merged_df = merged_df[cols]
        # Gera e armazena sumário dos dados
        #summary_docs = self.vector_db.generate_data_summary(merged_df, client_id, platforms_str)

        # Create LLM instance with system prompt
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.2,
            api_key=self.openai_api_key
        )

        # Get platform-specific prompt
        platform_system_prompt = get_platform_prompt(platforms)

        # Create pandas dataframe agent
        agent = create_pandas_dataframe_agent(
            llm=llm,
            df=merged_df,  # Usa merged_df ao invés de df
            agent_type=AgentType.OPENAI_FUNCTIONS,
            verbose=True,
            extra_tools=[PythonAstREPLTool()],
            prefix=platform_system_prompt,
            include_df_in_prompt=True,
            max_iterations=8,
            max_execution_time=60,
            allow_dangerous_code=True
        )

        # Create agent data to store => aqui é onde cria o agent com essas informações e metadata's. preciso de detalhamento
        agent_data = {
            "agent_obj": agent,
            "df": merged_df,
            "timestamp": datetime.now().timestamp(),
            "metadata": {
                "client_id": client_id,
                "agency_id": agency_id,
                "platforms": platforms,
                "row_count": len(merged_df),
                "column_count": len(merged_df.columns)
            }
        }

        # Store in memory cache
        #cache_key = f"{client_id}_{platforms_str}"
        #self.clients_cache[cache_key] = agent_data

        # Return invoke function directly
        return self._create_invoke_function(agent, agency_id, client_id, platforms_str)

    def run_analysis(self, agency_id: str, client_id: str, platforms: List[str], analysis_type: str,
               start_date: Optional[str] = None, end_date: Optional[str] = None,
               output_format: str = "detalhado") -> Dict:

        # Preparar cláusula de filtro de data
        date_filter = ""
        if start_date and end_date:
            date_filter = f" para o período de {start_date} até {end_date}"
        elif start_date:
            date_filter = f" a partir de {start_date}"
        elif end_date:
            date_filter = f" até {end_date}"

        # Preparar consulta com base no tipo de análise  -> aqui que é responsável por retornar a análise
        # inserir agency_id aqui já que o contexto também diz respeito a agência
        query = get_analysis_prompt(analysis_type, platforms, date_filter)
        print("\n\n 1. run_analysis: query => ", query)

        # Obtenha a função de invocação do agente
        invoke_func = self.get_client_agent(agency_id, client_id, platforms, start_date, end_date)

        # Configure custom options
        options = {
            "format": output_format,
            "analysis_type": analysis_type
        }

        # Run the analysis
        try:
            start_time = datetime.now()
            result = invoke_func(query)
            end_time = datetime.now()

            # Package the results
            return {
                "client_id": client_id,
                "platforms": platforms,
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
                "platforms": platforms,
                "analysis_type": analysis_type,
                "query": query,
                "result": f"Falha na análise: {str(e)}",
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e)
            }