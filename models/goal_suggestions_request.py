# models/goal_suggestions_request.py
from pydantic import BaseModel, Field
from typing import Optional

class GoalSuggestionsRequest(BaseModel):
    agency_id: int = Field(..., description="ID do usuário/agência no seu sistema")
    client_id: int = Field(..., description="ID do customer/cliente no seu sistema")
    platform_name: str = Field(..., description="instagram/facebook/linkedin/ga4")
    context: Optional[str] = Field(None, description="Contexto opcional (negócio, público, etc.)")
