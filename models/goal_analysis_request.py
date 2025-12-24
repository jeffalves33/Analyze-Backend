# models/goal_analysis_request.py
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class GoalAnalysisRequest(BaseModel):
    agency_id: int
    client_id: int
    goal_id: int

    platform_name: str
    title: str
    descricao: str
    data_inicio: str
    data_fim: str

    kpis: List[Dict[str, Any]] = Field(default_factory=list)

    # opcional: você pode mandar um resumo de métricas reais do período no futuro
    metrics_summary: Optional[Dict[str, Any]] = None
