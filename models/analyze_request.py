# ===== Arquivo: models/analyze_request.py =====

from pydantic import BaseModel
from typing import Optional, List

class AnalyzeRequest(BaseModel):
    agency_id: str
    client_id: str
    platforms: List[str]
    analysis_type: str
    analysis_focus: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    output_format: Optional[str] = "detalhado"
    analysis_query: Optional[str] = None          # pergunta explícita do usuário
    bilingual: Optional[bool] = True              # mantém PT-BR final, com raciocínio interno EN opcional
    granularity: Optional[str] = "detalhada"      # "resumo" | "detalhada"
    voice_profile: Optional[str] = "CMO"          # "CMO" | "HEAD_GROWTH" | "PERFORMANCE_MIDIA"
    decision_mode: Optional[str] = "decision_brief"  # "decision_brief" | "narrativa" | "topicos"
    narrative_style: Optional[str] = "SCQA"       # "SCQA" | "piramide" | "livre"