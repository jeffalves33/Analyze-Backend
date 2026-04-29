# ===== Arquivo: main.py =====
from dotenv import load_dotenv
load_dotenv()

import os
from typing import List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.analyzes_router import router as analyzes_router
from routers.chat_router import router as chat_router
from routers.documents_router import router as documents_router
from routers.goals_router import router as goals_router

app = FastAPI(title="Análise de Dados API", version="1.0")

# Configuração de CORS (origens em env, fallback seguro para domínios oficiais)
def parse_origins(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]

default_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://www.hokoainalytics.com",
    "https://hokoainalytics.com",
    "https://www.hokoainalytics.com.br",
    "https://hokoainalytics.com.br",
    "https://front-end-r0ap.onrender.com",
]
allow_origins = parse_origins(os.getenv("ANALYZE_ALLOWED_ORIGINS")) or default_origins

print("[analyze] CORS allow_origins =", allow_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclui as rotas do router
app.include_router(analyzes_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(goals_router, prefix="/goals", tags=["goals"])

# Endpoint de teste
@app.get("/")
async def root():
    return {"message": "API de Análise Online"}