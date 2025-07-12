# ===== Arquivo: models/analyze_request.py =====

from pydantic import BaseModel
from typing import Optional, List

class AnalyzeRequest(BaseModel):
    client_id: int
    platforms: List[str]
    analysis_type: str  # descriptive, predictive, prescriptive
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    output_format: Optional[str] = "detalhado"
    custom_query: Optional[str] = None