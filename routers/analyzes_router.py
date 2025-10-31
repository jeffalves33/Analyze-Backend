# ===== Arquivo: routers/analyzes_router.py =====

from fastapi import APIRouter, HTTPException
from models.analyze_request import AnalyzeRequest
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from services.analyze_service import AnalyzeService

router = APIRouter(prefix="/analyze", tags=["Analyze"])

@router.post("/")
async def analyze(request: AnalyzeRequest):
    try:
        result = AnalyzeService.run_analysis(request)
        return JSONResponse(content=jsonable_encoder(result), status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))