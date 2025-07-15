# ===== Arquivo: models/analyze_request.py =====

from pydantic import BaseModel
from typing import Optional, List

class AnalyzeRequest(BaseModel):
    agency_id: str
    client_id: str
    platforms: List[str]
    analysis_type: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    output_format: Optional[str] = "detalhado"