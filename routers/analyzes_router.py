# ===== Arquivo: routers/analyzes_router.py =====

from fastapi import APIRouter
from models.analyze_request import AnalyzeRequest
from fastapi.responses import JSONResponse
from services.analyze_service import AnalyzeService

router = APIRouter(prefix="/analyze", tags=["Analyze"])

@router.post("/")
async def analyze(request: AnalyzeRequest):
    try:
        service_resp = AnalyzeService.run_analysis(request)
        result_text = (service_resp or {}).get("result") or ""
        return JSONResponse(content={"result": result_text}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"message": str(e)}, status_code=500)