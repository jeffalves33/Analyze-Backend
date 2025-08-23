from __future__ import annotations

"""
Advanced Data Analyst (refatorado – integração com seus módulos)
---------------------------------------------------------------
- Usa RelationalDBManager (RDS) para buscar dados
- Usa VectorDBManager (Pinecone) para contexto
- Remove execução perigosa; cálculos 100% determinísticos em Pandas
- LLM só narra com base em JSON consolidado
- Prompt com anatomia clara (Papel/Tarefa/Contexto/Raciocínio/Saída/Paradas)
- Corrige import de ChatOpenAI (langchain-community)

Requisitos de ambiente:
- OPENAI_API_KEY definido (se usar narrativa por LLM)
- Dependências de vector db configuradas (Pinecone/OpenAIEmbeddings) para contexto
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import os

import numpy as np
import pandas as pd

# === Integrações do seu projeto ===
from utils.db.relational_db import RelationalDBManager
from utils.db.vector_db import VectorDBManager
from utils.prompts.system_prompts import get_platform_prompt, get_analysis_prompt

# ChatOpenAI (corrigido conforme aviso de depreciação)
try:
    from langchain_community.chat_models import ChatOpenAI  # pip install -U langchain-community
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore


# === Mapeamento canônico por plataforma ===
PLATFORM_SCHEMA = {
    "instagram": {
        # origem -> canônico
        "reach": "reach",
        "views": "views",
        "followers": "followers",
    },
    "facebook": {
        "page_impressions": "impressions",
        "page_impressions_unique": "reach",
        "page_follows": "followers",
    },
    "google_analytics": {
        "impressions": "impressions",
        "traffic_direct": "traffic_direct",
        "traffic_organic_search": "traffic_organic_search",
        "traffic_organic_social": "traffic_organic_social",
        "search_volume": "search_volume",
    },
}
# Métricas priorizadas (agora inclui GA)
PREFERRED_BASES = (
    "reach", "views", "impressions", "followers",
    "traffic_direct", "traffic_organic_search", "traffic_organic_social", "search_volume"
)


# =============================
# Helpers de normalização / core
# =============================

def _safe_prefix_cols(df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Prefixa colunas por plataforma, sem duplicar prefixo e preservando 'data'."""
    out = df.copy()
    ren: Dict[str, str] = {}
    for col in out.columns:
        if col == "data":
            continue
        if not col.startswith(f"{platform}_"):
            ren[col] = f"{platform}_{col}"
    if ren:
        out = out.rename(columns=ren)
    return out

def _normalize_platform_df(df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = df.copy()

    # 2.1) Uniformizar nome da coluna de data
    # Aceite "data" ou "date"; se vier outra, trate aqui.
    if "data" not in out.columns and "date" in out.columns:
        out = out.rename(columns={"date": "data"})

    # 2.2) Remover campos técnicos repetitivos que não serão agregados por dia
    drop_candidates = [c for c in out.columns if c.lower() in {"id_customer", "agency_id", "client_id"}]
    if drop_candidates:
        out = out.drop(columns=drop_candidates, errors="ignore")

    # 2.3) Aplicar mapeamento canônico específico da plataforma
    schema = PLATFORM_SCHEMA.get(platform, {})
    # Apenas colunas reconhecidas são renomeadas; o resto permanece como está
    out = out.rename(columns={orig: canon for orig, canon in schema.items() if orig in out.columns})

    # 2.4) Prefixar com o nome da plataforma, preservando 'data'
    ren = {}
    for col in out.columns:
        if col == "data":
            continue
        if not col.startswith(f"{platform}_"):
            ren[col] = f"{platform}_{col}"
    if ren:
        out = out.rename(columns=ren)

    return out


def _prepare_dates(df: pd.DataFrame, tz: str = "America/Sao_Paulo") -> pd.DataFrame:
    """Garante 'data' em timezone local e normalizada ao dia."""
    out = df.copy()
    # Assume UTC caso venha sem timezone
    out["data"] = pd.to_datetime(out["data"], utc=True, errors="coerce").dt.tz_convert(tz).dt.normalize()
    out = out.sort_values("data").reset_index(drop=True)
    return out


def _basic_kpis(df: pd.DataFrame, cols: List[str]) -> Dict[str, Dict[str, float]]:
    kpis: Dict[str, Dict[str, float]] = {}
    for c in cols:
        if c in df.columns:
            s = df[c].fillna(0)
            kpis[c] = {
                "mean": float(s.mean()),
                "median": float(s.median()),
                "p95": float(s.quantile(0.95)),
                "sum": float(s.sum()),
                "non_zero_days": float((s > 0).sum()),
                "days": float(s.shape[0]),
            }
    return kpis


def _mad_anomalies(df: pd.DataFrame, col: str, zcut: float = 3.0) -> List[Dict[str, Any]]:
    if col not in df.columns:
        return []
    s = df[col].fillna(0)
    med = s.median()
    mad = (s - med).abs().median()
    if mad == 0:
        return []
    z = 0.6745 * (s - med) / mad
    outliers = df.loc[z.abs() >= zcut, ["data", col]].copy()
    return [{"data": str(row["data"].date()), col: float(row[col])} for _, row in outliers.iterrows()]


def _dod_change_mean(df: pd.DataFrame, col: str) -> Optional[float]:
    if col not in df.columns:
        return None
    s = df[col].fillna(0)
    pct = s.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    return float(pct.mean()) if not pct.empty else None


def _weekday_breakdown(df: pd.DataFrame, col: str) -> List[Dict[str, Any]]:
    if col not in df.columns or "data" not in df.columns:
        return []
    tmp = df.copy()
    try:
        tmp["weekday"] = tmp["data"].dt.day_name(locale="pt_BR")
    except Exception:
        wd_map = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}
        tmp["weekday"] = tmp["data"].dt.day_of_week.map(wd_map)
    g = tmp.groupby("weekday")[col].agg(["mean", "sum", "median"]).reset_index()
    records: List[Dict[str, Any]] = []
    for _, row in g.iterrows():
        records.append({
            "weekday": str(row["weekday"]),
            "mean": float(row["mean"]),
            "sum": float(row["sum"]),
            "median": float(row["median"]),
        })
    return records


# =============================
# Prompt de narrativa (engenharia)
# =============================

def build_narrative_prompt(platforms: List[str],
                           analysis_query: str,
                           context_text: str,
                           summary_json: Dict[str, Any],
                           output_format: str = "detalhado") -> str:
    """Prompt com anatomia clara: Papel, Tarefa, Contexto, Raciocínio, Saída, Paradas."""
    plataformas = ", ".join(platforms)
    return f"""
[PAPEL]
Você é um analista de dados sênior de marketing digital, escrevendo para gestão e performance.

[TAREFA]
Responder à solicitação abaixo COM BASE EXCLUSIVA nos dados calculados (JSON) e no contexto histórico.
Não calcule nada novo. Interprete, contextualize e recomende ações.

[CONTEXTO]
Plataformas: {plataformas}
Histórico relevante (resumo de documentos do cliente/agência):
{context_text}

JSON de métricas e achados (use SOMENTE estes números):
{summary_json}

[INSTRUÇÕES DE RACIOCÍNIO]
1) Não invente números. Se um número não estiver no JSON, diga que não está disponível.
2) Explique tendências (altas/baixas) referindo-se a dias/intervalos presentes no JSON.
3) Aponte anomalias (picos/vales) quando existirem no campo 'anomalies'.
4) Proponha hipóteses plausíveis usando o histórico (context_text) apenas como contexto.
5) Dê recomendações práticas atreladas às métricas observadas (ex.: ajustar criativo X, reforçar horário Y).
6) Seja conciso, claro e em português do Brasil.

[FORMA DE SAÍDA] ({output_format})
- Título curto (1 linha)
- Sumário executivo (3–5 bullets)
- O que aconteceu (tendências + picos/vales, com datas)
- Diagnóstico (hipóteses ancoradas no contexto)
- Recomendações acionáveis (priorizadas)
- Próximos passos e métricas a monitorar

[CONDICOES DE PARADA]
- Não calcule nada fora do JSON.
- Não prometa tarefas futuras: apenas recomende.
- Se faltar dado, explicite a lacuna e siga.
    
[SOLICITACAO]
{analysis_query}
"""


# =============================
# Config/DTOs
# =============================

@dataclass
class AnalysisPayload:
    agency_id: str
    client_id: str
    platforms: List[str]
    analysis_type: str = "descriptive"
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None    # YYYY-MM-DD
    output_format: str = "detalhado"
    analysis_query: Optional[str] = None  # permite sobrescrever a pergunta ao LLM


# =============================
# Classe principal
# =============================

class AdvancedDataAnalyst:
    def __init__(self,
                 vector_db: Optional[VectorDBManager] = None,
                 relational_db: Optional[RelationalDBManager] = None,
                 openai_api_key: Optional[str] = None,
                 pinecone_api_key: Optional[str] = None,
                 ):
        # Injeta dependências reais ou cria com variáveis de ambiente
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.vector_db = vector_db or VectorDBManager(
            pinecone_api_key=pinecone_api_key or os.getenv("PINECONE_API_KEY", ""),
            openai_api_key=self.openai_api_key or ""
        )
        self.rel_db = relational_db or RelationalDBManager()
        self.clients_cache: Dict[str, Dict[str, Any]] = {}

    # --------- Data loading ---------
    def _load_platform_df(self,
                          agency_id: str,
                          client_id: str,
                          platform: str,
                          start_date: Optional[str],
                          end_date: Optional[str]) -> pd.DataFrame:
        """
        Usa RelationalDBManager.get_client_data para obter dados (coluna obrigatória 'data').
        """
        try:
            df = self.rel_db.get_client_data(
                client_id=client_id,
                platform=platform,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception:
            # Se não houver dados, devolve DF vazio com 'data'
            return pd.DataFrame({"data": []})

        if df is None or df.empty:
            return pd.DataFrame({"data": []})

        df = _normalize_platform_df(df, platform)
        df = _prepare_dates(df)        
        return df

    def _merge_platform_dfs(self, dfs: List[pd.DataFrame]) -> pd.DataFrame:
        if not dfs:
            return pd.DataFrame({"data": []})
        merged = dfs[0]
        for add in dfs[1:]:
            merged = pd.merge(merged, add, on="data", how="outer")
        merged = merged.sort_values("data").reset_index(drop=True)
        print("🚀 ~ merged: ", merged)
        return merged

    # --------- Deterministic analytics ---------
    def _compute_summary(self, merged_df: pd.DataFrame, platforms: List[str]) -> Dict[str, Any]:
        all_cols = merged_df.columns.tolist()
        metric_cols = [c for c in all_cols if c != "data"]

        # 4.1) Tente selecionar métricas canônicas por plataforma
        candidatos: List[str] = []
        for base in PREFERRED_BASES:
            for p in platforms:
                pc = f"{p}_{base}"
                if pc in merged_df.columns:
                    candidatos.append(pc)

        # 4.2) Se nada foi encontrado (caso extremo), use todas as métricas disponíveis
        if not candidatos:
            candidatos = metric_cols

        summary: Dict[str, Any] = {
            "period": {
                "start": str(merged_df["data"].min().date()) if not merged_df.empty else None,
                "end": str(merged_df["data"].max().date()) if not merged_df.empty else None,
            },
            "kpis": _basic_kpis(merged_df, candidatos),
            "anomalies": {c: _mad_anomalies(merged_df, c) for c in candidatos},
            "trends": {f"{c}_dod_mean": _dod_change_mean(merged_df, c) for c in candidatos},
            "segments": {f"{c}_by_weekday": _weekday_breakdown(merged_df, c) for c in candidatos},
            "meta": {"platforms": platforms, "columns": all_cols, "selected_metrics": candidatos},
        }
        return summary

    # --------- Narrative (LLM) ---------
    def _make_narrative(self,
                        platforms: List[str],
                        analysis_query: str,
                        context_text: str,
                        summary: Dict[str, Any],
                        output_format: str = "detalhado") -> str:
        prompt = build_narrative_prompt(
            platforms=platforms,
            analysis_query=analysis_query,
            context_text=context_text,
            summary_json=summary,
            output_format=output_format,
        )
        print("🚀 ~ analysus_query: ", analysis_query)
        if ChatOpenAI is None:
            return (
                "[Aviso: ChatOpenAI indisponível no ambiente]\n\n"
                "Resumo JSON:\n" + str(summary) + "\n\n"
                "Solicitação:\n" + analysis_query + "\n\n"
                "(Nesta etapa, um LLM redigiria a narrativa com base no JSON e contexto acima.)"
            )
        llm = ChatOpenAI(model="gpt-4o", temperature=0.3, api_key=self.openai_api_key)
        return llm.invoke(prompt).content  # type: ignore

    # --------- Public API ---------
    def get_client_agent(self,
                         agency_id: str,
                         client_id: str,
                         platforms: List[str],
                         start_date: Optional[str],
                         end_date: Optional[str]) -> Callable[[str], Dict[str, Any]]:
        # 1) Carregar e normalizar DFs por plataforma
        dfs: List[pd.DataFrame] = []
        for p in platforms:
            dfp = self._load_platform_df(agency_id, client_id, p, start_date, end_date)
            if not dfp.empty:
                dfs.append(dfp)
        merged_df = self._merge_platform_dfs(dfs)

        # 2) Computar resumo determinístico
        summary = self._compute_summary(merged_df, platforms)
        print("\n\n🚀 ~ summary: ", summary)

        # 3) Cache por cliente + plataformas + período
        cache_key = f"{client_id}_{'_'.join(platforms)}_{summary['period']['start']}_{summary['period']['end']}"
        self.clients_cache[cache_key] = {
            "df": merged_df,
            "summary": summary,
            "ts": datetime.now().isoformat(),
        }

        # 4) Retornar função de invocação que busca contexto + narra
        def _invoke(analysis_query: str, output_format: str = "detalhado") -> Dict[str, Any]:
            # 4.1) Buscar contexto histórico no Pinecone e incluir prompt de plataforma
            try:
                vectordb = self.vector_db.create_or_load_vector_db(customer_id=client_id, client_id=agency_id)
                retriever = vectordb.as_retriever(search_type="mmr", search_kwargs={"k": 5, "fetch_k": 10})
                print("🚀 ~ retriever: ", retriever)
                if hasattr(retriever, "invoke"):
                    docs = retriever.invoke(analysis_query)
                    print("🚀 ~ 1docs: ", docs)
                else:
                    docs = retriever.get_relevant_documents(analysis_query)  # type: ignore
                    print("🚀 ~ 2docs: ", docs)
                retrieved_text = "\n\n".join([getattr(d, "page_content", str(d)) for d in docs])
                print("🚀 ~ retrieved_text: ", retrieved_text)
            except Exception as e:  # pragma: no cover
                retrieved_text = f"Erro ao buscar contexto histórico: {str(e)}"

            # Prompt específico das plataformas (do seu system_prompts)
            platform_hint = get_platform_prompt(platforms)
            context_text = platform_hint + "\n\n" + retrieved_text if retrieved_text else platform_hint

            # 4.2) Gerar narrativa (LLM apenas redige)
            analysis_text = self._make_narrative(platforms, analysis_query, context_text, summary, output_format)
            return {"summary": summary, "analysis": analysis_text}

        return _invoke

    def run_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa o fluxo completo:
        - Carrega/une dados por plataforma (RDS via RelationalDBManager)
        - Calcula métricas e achados determinísticos (Pandas)
        - Usa LLM só para narrar (sem calcular)
        - Usa VectorDBManager para recuperar contexto
        """
        start_time = datetime.now()

        ap = AnalysisPayload(
            agency_id=str(payload.get("agency_id")),
            client_id=str(payload.get("client_id")),
            platforms=[str(p) for p in payload.get("platforms", [])],
            analysis_type=str(payload.get("analysis_type", "descriptive")),
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
            output_format=str(payload.get("output_format", "detalhado")),
            analysis_query=payload.get("analysis_query"),
        )

        invoke_func = self.get_client_agent(
            agency_id=ap.agency_id,
            client_id=ap.client_id,
            platforms=ap.platforms,
            start_date=ap.start_date,
            end_date=ap.end_date,
        )

        # Se não vier pergunta específica, monta uma a partir dos seus templates
        if not ap.analysis_query:
            date_filter = ""
            if ap.start_date and ap.end_date:
                date_filter = f" no período de {ap.start_date} a {ap.end_date}"
            elif ap.start_date:
                date_filter = f" a partir de {ap.start_date}"
            elif ap.end_date:
                date_filter = f" até {ap.end_date}"
            ap.analysis_query = get_analysis_prompt(ap.analysis_type, ap.platforms, date_filter)

        try:
            result = invoke_func(ap.analysis_query, ap.output_format)
            status = "success"
            error = None
        except Exception as e:  # pragma: no cover
            result = {"summary": None, "analysis": f"Falha na análise: {str(e)}"}
            status = "error"
            error = str(e)

        end_time = datetime.now()
        return {
            "agency_id": ap.agency_id,
            "client_id": ap.client_id,
            "platforms": ap.platforms,
            "analysis_type": ap.analysis_type,
            "query": ap.analysis_query,
            "summary": result.get("summary"),
            "result": result.get("analysis"),
            "execution_time": (end_time - start_time).total_seconds(),
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "error": error,
        }
