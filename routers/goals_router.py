# routers/goals_router.py
from fastapi import APIRouter, HTTPException
from models.goal_suggestions_request import GoalSuggestionsRequest
from models.goal_analysis_request import GoalAnalysisRequest
from services.goals_service import generate_goal_suggestions, generate_goal_analysis

router = APIRouter()

@router.post("/suggestions")
def suggestions(req: GoalSuggestionsRequest):
    try:
        payload = req.model_dump()
        out = generate_goal_suggestions(payload)
        return {"success": True, **out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar sugestões: {str(e)}")

@router.post("/generate-analysis")
def generate_analysis(req: GoalAnalysisRequest):
    try:
        payload = req.model_dump()
        out = generate_goal_analysis(payload)
        return {"success": True, **out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar análise: {str(e)}")
