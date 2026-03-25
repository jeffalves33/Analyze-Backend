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

    metrics_summary: Optional[Dict[str, Any]] = None

    platforms: Optional[List[str]] = None
    analysis_type: str = "general"
    analysis_focus: str = "panorama"
    output_format: str = "detalhado"
    analysis_query: Optional[str] = None