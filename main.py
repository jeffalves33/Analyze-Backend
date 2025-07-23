# ===== Arquivo: main.py =====
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.analyzes_router import router as analyzes_router
from routers.chat_router import router as chat_router
from routers.documents_router import router as documents_router

app = FastAPI(title="Análise de Dados API", version="1.0")

# Configuração de CORS para permitir acesso do seu frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.hokoainalytics.com.br"],  # Deixe '*' para testes locais
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclui as rotas do router
app.include_router(analyzes_router)
app.include_router(chat_router)
app.include_router(documents_router)


# Endpoint de teste
@app.get("/")
async def root():
    return {"message": "API de Análise Online"}