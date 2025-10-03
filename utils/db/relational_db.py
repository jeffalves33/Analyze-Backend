# utils/db/relational_db.py
import pandas as pd
from sqlalchemy import create_engine, text
from typing import Dict, Optional, Any
import base64
import pickle

class RelationalDBManager:
    def __init__(self, connection_string=None):
        # Inicializar conexão com o banco de dados
        self.connection_string = connection_string or self._get_default_connection_string()
        try:
            self.db_engine = create_engine(self.connection_string)
        except Exception as e:
            print(f"Erro ao conectar ao RDS: {e}")
            raise e
            
        # Mapeamentos de colunas de plataforma
        self.platform_columns = {
            'google_analytics': [
                'traffic_direct', 'search_volume', 'impressions', 
                'traffic_organic_search', 'traffic_organic_social', 'data'
            ],
            'facebook': [
                'page_impressions', 'page_impressions_unique', 
                'page_follows', 'data'
            ],
            'instagram': [
                'reach', 'views', 'followers', 'data'
            ],
            'linkedin': [
                'impressions', 'followers', 'data'
            ]
        }
    
    def _get_default_connection_string(self) -> str:
        return "postgresql://postgres:HokoAI2024@db-hokoainalytics.cviwa0kqeims.us-east-1.rds.amazonaws.com:5432/postgres"
    
    def get_client_data(self, client_id: str, platform: str, 
                       start_date: Optional[str] = None, 
                       end_date: Optional[str] = None) -> pd.DataFrame:
        # Get columns for the platform
        if platform not in self.platform_columns:
            raise ValueError(f"Platform '{platform}' not supported. Available platforms: {list(self.platform_columns.keys())}")
        
        columns = self.platform_columns[platform]
        columns_str = ", ".join(columns)
        
        # Crie a consulta SQL com parâmetros apropriados
        query = f"""
        SELECT {columns_str}
        FROM {platform}
        WHERE id_customer = :client_id
        """
        
        # Adicione filtros de data, se fornecidos
        params = {"client_id": client_id}
        if start_date:
            query += " AND data >= :start_date"
            params["start_date"] = start_date
        if end_date:
            query += " AND data <= :end_date"
            params["end_date"] = end_date
            
        # Execute the query and return as DataFrame
        try:
            with self.db_engine.connect() as connection:
                df = pd.read_sql(text(query), connection, params=params)
                
            if df.empty:
                raise ValueError(f"No data found for client {client_id} on platform {platform} for the specified date range")
                
            return df
        except Exception as e:
            raise Exception(f"Database error when fetching data for client {client_id}: {str(e)}")
    
    def get_client_agent(self, client_id: str, platform: str) -> Optional[Any]:
        try:
            query = """
            SELECT agent_data 
            FROM customer 
            WHERE id_customer = :client_id
            """
            
            with self.db_engine.connect() as connection:
                result = connection.execute(text(query), {"client_id": client_id}).fetchone()
                
            if result and result[0]:
                # Deserialize the stored agent
                agent_data = base64.b64decode(result[0])
                loaded_data = pickle.loads(agent_data)
                
                # Check if it has platform-specific data
                if platform in loaded_data:
                    return loaded_data[platform]
                    
            return None
        except Exception as e:
            print(f"Error retrieving agent from database: {str(e)}")
            return None
    
    def store_client_agent(self, client_id: str, platform: str, agent_data: Dict) -> bool:
        try:
            # Check if we have existing data
            existing_data = {}
            
            query = """
            SELECT agent_data 
            FROM customer 
            WHERE id_customer = :client_id
            """
            
            with self.db_engine.connect() as connection:
                result = connection.execute(text(query), {"client_id": client_id}).fetchone()
                
            if result and result[0]:
                # Deserialize the stored agent
                existing_data = pickle.loads(base64.b64decode(result[0]))

            # Create a copy without the agent_obj that can't be pickled
            serializable_agent_data = {
                # Não inclua agent_obj
                "df": agent_data["df"],
                "timestamp": agent_data["timestamp"],
                "metadata": agent_data["metadata"]
                # Não inclua retriever também
            }
            
            # Update with the new platform data
            existing_data[platform] = serializable_agent_data
            
            # Serialize the updated data
            serialized_agent = base64.b64encode(pickle.dumps(existing_data))
            
            # Primeiro, verificamos se a coluna agent_data existe
            with self.db_engine.connect() as connection:
                # Iniciar transação
                with connection.begin():
                    # Verificar se a coluna agent_data existe e, se não existir, criá-la
                    alter_table_query = """
                    ALTER TABLE customer ADD COLUMN IF NOT EXISTS agent_data BYTEA;
                    """
                    connection.execute(text(alter_table_query))
                    
                    # Verificar se o cliente existe
                    check_query = "SELECT 1 FROM customer WHERE id_customer = :client_id"
                    exists = connection.execute(text(check_query), {"client_id": client_id}).fetchone() is not None
                    
                    if exists:
                        # Atualizar registro existente
                        update_query = """
                        UPDATE customer 
                        SET agent_data = :agent_data, 
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE id_customer = :client_id
                        """
                        connection.execute(text(update_query), {
                            "client_id": client_id,
                            "agent_data": serialized_agent
                        })
                    else:
                        # Inserir novo registro
                        insert_query = """
                        INSERT INTO customer (id_customer, agent_data, created_at, updated_at) 
                        VALUES (:client_id, :agent_data, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """
                        try:
                            connection.execute(text(insert_query), {
                                "client_id": client_id,
                                "agent_data": serialized_agent
                            })
                        except Exception as e:
                            # Se falhar, pode ser porque há colunas obrigatórias faltando
                            print(f"Erro ao inserir no banco: {e}")
                            # Tente com todos os campos necessários
                            full_insert_query = """
                            INSERT INTO customer (id_customer, agent_data, created_at, updated_at, email, name, id_user) 
                            VALUES (:client_id, :agent_data, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 
                                    'temp@example.com', 'Temporary Name', 1)
                            """
                            connection.execute(text(full_insert_query), {
                                "client_id": client_id,
                                "agent_data": serialized_agent
                            })
                        
            return True
        except Exception as e:
            print(f"Error storing agent in database: {str(e)}")
            return False