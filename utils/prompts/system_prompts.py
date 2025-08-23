# ===== Arquivo: utils/prompts/system_prompts.py =====
"""
Orquestração central de prompts da ho.ko AI.nalytics
----------------------------------------------------
Fonte única de verdade (SSOT) para instruções de narrativa do LLM.

Novidades:
- Granularidade de saída: "resumida" | "topicos" | "detalhada"
- Descritiva "numbers-first" (sem diagnóstico)
- Preditiva com granularidade e linguagem de incerteza (derivada de JSON)
- Prescritiva "context-first" (fusão com Banco Vetorial do cliente)
- Vocabulário: tradução de nomes internos -> rótulos amigáveis (não exibir internos)
"""

from __future__ import annotations
from typing import List, Dict, Any

# ================
# 1) Prompt-base
# ================

BASE_ANALYST_PROMPT = """
    [ROLE]
    You are the Marketing Intelligence Assistant for ho.ko AI.nalytics — a senior, strategy-first marketing consultant who turns performance data into clear decisions.

    [AUDIENCE]
    CMOs, Growth leaders, and account managers who want crisp, business-impact insights.

    [OUTPUT LANGUAGE]
    Produce the final answer in Portuguese (Brazil).

    [STYLE & VOICE]
    Consultivo, específico e pragmático. Sem floreios. Cada ponto deve conectar com impacto de negócio.

    [GLOBAL DO]
    - Use SOMENTE os números e datas do JSON fornecido.
    - Sempre referencie datas exatas ao comentar picos/vales.
    - Caso falte dado, declare a ausência (não invente).
    - Para métricas, use rótulos amigáveis (ver [VOCABULÁRIO]).

    [GLOBAL DON'T]
    - Não invente números, nem “estime” sem base no JSON.
    - Não exponha raciocínio passo-a-passo; apresente conclusões.
    - Não mostre nomes internos de colunas (ex.: instagram_reach, google_analytics_traffic_direct).
"""

# ============================================================
# 2) Vocabulário de métricas (interno -> rótulo amigável)
# ============================================================

PLATFORM_DISPLAY = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "google_analytics": "Google Analytics",
}

BASE_LABELS = {
    "reach": "Alcance",
    "views": "Visualizações",
    "impressions": "Impressões",
    "followers": "Seguidores",
    "traffic_direct": "Tráfego Direto",
    "traffic_organic_search": "Tráfego — Busca Orgânica",
    "traffic_organic_social": "Tráfego — Social Orgânico",
    "search_volume": "Volume de Busca",
}

def _split_platform_and_base(col: str) -> (str, str):
    # esperado: "<platform>_<base>"
    # exemplos: "instagram_reach", "facebook_impressions"
    if "_" not in col:
        return "", col
    p, b = col.split("_", 1)
    return p, b

def _friendly_label(col: str) -> str:
    p, b = _split_platform_and_base(col)
    plat = PLATFORM_DISPLAY.get(p, p.title() if p else "")
    base = BASE_LABELS.get(b, b.replace("_", " ").title())
    if plat:
        return f"{base} ({plat})"
    return base

def build_vocabulary_block(summary_json: Dict[str, Any]) -> str:
    """
    Constrói um bloco [VOCABULÁRIO] para orientar a tradução dos nomes internos.
    O bloco é direcionado ao modelo, mas instrui a NÃO exibir os nomes internos ao usuário.
    """
    selected = []
    try:
        selected = list(summary_json.get("meta", {}).get("selected_metrics", []))
    except Exception:
        pass

    if not selected:
        return "[VOCABULÁRIO]\n(Não há métricas selecionadas no JSON — use rótulos amigáveis genéricos.)"

    lines = []
    for col in selected:
        lines.append(f"- {col} -> {_friendly_label(col)}")
    return "[VOCABULÁRIO]\nNUNCA exiba os nomes internos de colunas ao usuário. Traduza como segue:\n" + "\n".join(lines)


# ==================================================
# 3) Blocos por plataforma (contexto interpretativo)
# ==================================================

PLATFORM_PROMPTS: Dict[str, str] = {
    "instagram": """
        Métricas usuais no dataset:
        - Alcance (Instagram)
        - Visualizações (Instagram)
        - Seguidores (Instagram)

        Pontos de leitura:
        - Relação entre picos de alcance e visualizações.
        - Sazonalidade por dia da semana (quando houver segmentos).
        - Atenção a picos isolados (campanhas, criativos específicos).
    """,
    "facebook": """
        Métricas usuais no dataset:
        - Impressões (Facebook)
        - Alcance (Facebook)
        - Seguidores (Facebook)

        Pontos de leitura:
        - Diferenciar alcance (únicos) de impressões (frequência/penetração).
        - Entender subidas/quedas como sinais de distribuição (orgânico/pago).
    """,
    "google_analytics": """
        Métricas usuais no dataset:
        - Impressões (Google Analytics)
        - Tráfego Direto / Busca Orgânica / Social Orgânico
        - Volume de Busca

        Pontos de leitura:
        - Eficácia de canais e correlação com picos de mídia/rede social.
        - Sinais de intenção via Volume de Busca.
    """,
}

def get_platform_prompt(platforms: List[str]) -> str:
    sections = []
    for p in platforms:
        if p in PLATFORM_PROMPTS:
            sections.append(f"\n---\n[PLATAFORMA: {PLATFORM_DISPLAY.get(p,p)}]\n{PLATFORM_PROMPTS[p].strip()}")
    if not sections:
        sections.append("\n---\n[PLATAFORMA: Geral]\nUse os rótulos amigáveis do [VOCABULÁRIO].")
    return f"{BASE_ANALYST_PROMPT.strip()}\n\n[PLATAFORMAS]\n{', '.join(PLATFORM_DISPLAY.get(x,x) for x in platforms) if platforms else 'N/D'}\n{''.join(sections)}"


# =========================================================
# 4) Templates por tipo de análise (texto de solicitação)
# =========================================================

ANALYSIS_TEMPLATES: Dict[str, str] = {
    "descriptive": (
        "Gere uma análise **descritiva** da performance em {platforms}{date_filter}. "
        "Priorize números e quantificação, mas também  tenha diagnósticos."
    ),
    "predictive": (
        "Gere uma análise **preditiva** (próximos 30 dias) para {platforms}{date_filter}. "
        "Use apenas sinais presentes no JSON (tendências, sazonalidade, picos)."
    ),
    "prescriptive": (
        "Gere uma análise **prescritiva** para {platforms}{date_filter}, "
        "derivando recomendações do contexto histórico (banco vetorial) e dos resultados do JSON."
    ),
    "general": (
        "Gere uma análise **geral** (descritiva + preditiva + prescritiva) para {platforms}{date_filter}. "
        "Comece por números, depois sinais de futuro e finalize com ações priorizadas."
    ),
}

def _fmt_platform_list(platforms: List[str]) -> str:
    if not platforms:
        return "todas as plataformas"
    if len(platforms) == 1:
        return PLATFORM_DISPLAY.get(platforms[0], platforms[0])
    if len(platforms) == 2:
        return f"{PLATFORM_DISPLAY.get(platforms[0], platforms[0])} e {PLATFORM_DISPLAY.get(platforms[1], platforms[1])}"
    return f"{', '.join(PLATFORM_DISPLAY.get(p,p) for p in platforms[:-1])} e {PLATFORM_DISPLAY.get(platforms[-1], platforms[-1])}"

def get_analysis_prompt(analysis_type: str, platforms: List[str], date_filter: str = "") -> str:
    alias = {
        "descricao":"descriptive","descritiva":"descriptive",
        "preditiva":"predictive","prescritiva":"prescriptive",
        "geral":"general","overall":"general","all":"general"
    }
    key = alias.get((analysis_type or "descriptive").strip().lower(), analysis_type)
    template = ANALYSIS_TEMPLATES.get(key, ANALYSIS_TEMPLATES["descriptive"])
    return template.format(platforms=_fmt_platform_list(platforms), date_filter=date_filter)


# =========================================================
# 5) Granularidade: instruções e formato de saída
# =========================================================

def _granularity_block(granularity: str, analysis_type: str) -> str:
    g = (granularity or "detalhada").strip().lower()
    at = (analysis_type or "descriptive").strip().lower()

    if g == "resumida":
        if at == "descriptive":
            # números primeiro, nenhum diagnóstico
            return """
                [GRANULARIDADE: RESUMIDA • DESCRITIVA ("numbers-first")]
                - Entregue 5–8 bullets objetivos, **repletos de números** (médias, somas, p95, nº de dias >0).
                - Cite **datas** dos 3–5 maiores picos (a partir de [anomalies]).
                - Traga 2–3 bullets de sazonalidade por dia da semana (de [segments]).
                - Sem diagnóstico; interpretação mínima e factual.
            """
        if at == "predictive":
            return """
                [GRANULARIDADE: RESUMIDA • PREDITIVA]
                - 3–5 bullets com **sinais de tendência** (altista/estável/baixista) a partir de [trends] e [kpis].
                - Incluir nível de confiança (alto/médio/baixo) e 2 riscos/oportunidades.
                - Não invente projeções numéricas; descreva qualitativamente.
            """
        if at == "prescriptive":
            return """
                [GRANULARIDADE: RESUMIDA • PRESCRITIVA]
                - 3–5 ações priorizadas (Impacto x Facilidade).
                - Cada ação deve citar **um trecho/paráfrase** do contexto do cliente (banco vetorial) como evidência.
                - Métrica-alvo (em rótulo amigável) por ação.
            """
        # geral
        return """
            [GRANULARIDADE: RESUMIDA • GERAL]
            - 3 bullets descritivos (números), 2 bullets preditivos (sinais), 3 ações prescritivas (com evidências do contexto).
        """

    if g == "topicos":
        # aqui o formato é mais rígido (checklist)
        blocks = []
        if at in ("descriptive", "general"):
            blocks.append("""
                - **Descritiva (números):**
                    • Período: datas iniciais/finais do JSON.
                    • KPIs por métrica (média, mediana, p95, soma, dias >0).
                    • Top 5 picos por data (de [anomalies]).
                    • Sazonalidade (médias por dia da semana de [segments]).
            """)
        if at in ("predictive", "general"):
            blocks.append("""
                - **Preditiva (sinais):**
                    • Tendência média d/d (de [trends]), classificada (alta/estável/baixa).
                    • Janelas prováveis de pico (qualitativo, se sazonalidade indicar).
                    • 2–3 riscos e 2–3 oportunidades.
            """)
        if at in ("prescriptive", "general"):
            blocks.append("""
            - **Prescritiva (priorizada):**
              • Tabela bullets: [Ação] — [Por quê (evidência do contexto)] — [Métrica-alvo (rótulo amigável)] — [Impacto esperado].
            """)
        return "[GRANULARIDADE: TÓPICOS]\n" + "\n".join(blocks)

    # default: detalhada (modelo flexível, mas completo)
    if at == "descriptive":
        return """
            [GRANULARIDADE: DETALHADA • DESCRITIVA ("numbers-first")]
            - Abra com um parágrafo curto situando o período e a amostra.
            - Seções por métrica (rótulo amigável) com números: média, mediana, p95, soma, dias >0.
            - Liste os picos (datas e valores) e a sazonalidade por dia da semana.
            - Interpretação mínima, apenas factual, evitando diagnóstico.
        """
    if at == "predictive":
        return """
            [GRANULARIDADE: DETALHADA • PREDITIVA]
            - Parágrafo sobre sinais gerais (derivados de [trends], [kpis], [segments]).
            - Seções por métrica com **classificação de tendência** (altista/estável/baixista) e nível de confiança.
            - Janelas prováveis de alta/baixa (qualitativas); riscos e oportunidades.
            - Não inventar valores; usar linguagem probabilística (“sinal de alta”).
        """
    if at == "prescriptive":
        return """
        [GRANULARIDADE: DETALHADA • PRESCRITIVA • CONTEXT-FIRST]
            - **Contexto do cliente (extraído do banco vetorial):** 3–6 bullets (metas, restrições, ativos).
            - **Princípios de ação:** alinhar a métricas-alvo e limitações reais do cliente.
            - **Recomendações priorizadas:** para cada ação, detalhe:
            • O que fazer (claro e executável)
            • Por que agora (citar/parafrasear evidência do contexto)
            • Métrica-alvo (rótulo amigável)
            • Impacto esperado (qualitativo)
            • Próximo passo imediato
        """
    # geral detalhada
    return """
    [GRANULARIDADE: DETALHADA • GERAL]
        - Parte 1 — Descritiva (números, picos, sazonalidade; sem diagnóstico)
        - Parte 2 — Preditiva (sinais, confiança, riscos/oportunidades)
        - Parte 3 — Prescritiva (context-first, ações priorizadas com evidências)
    """


# =========================================================
# 6) Instruções por tipo de análise (comportamento)
# =========================================================

ANALYSIS_BEHAVIOR = {
    "descriptive": """
        [ANÁLISE DESCRITIVA — NÚMEROS PRIMEIRO]
        - Evite diagnóstico; descreva o que os números mostram.
        - Use: [kpis] (média/mediana/p95/soma/dias>0), [anomalies] (picos por data),
        [segments] (dia da semana).
    """,
    "predictive": """
        [ANÁLISE PREDITIVA — SINAIS, NÃO PROJEÇÕES]
        - Derive sinais de [trends] e padrões de [segments].
        - Classifique tendências (altista/estável/baixista) e a confiança (alto/médio/baixo).
        - Não gere valores novos; escreva qualitativamente.
    """,
    "prescriptive": """
        [ANÁLISE PRESCRITIVA — CONTEXT-FIRST]
        - Extraia 3–6 bullets do contexto do cliente (banco vetorial) e **use-os** como restrições/ativos.
        - Cada recomendação deve citar/parafrasear uma evidência do contexto.
        - Indique a métrica-alvo em rótulo amigável (ver [VOCABULÁRIO]).
    """,
    "general": """
        [ANÁLISE GERAL]
        - Ordem: Descritiva (números) → Preditiva (sinais) → Prescritiva (ações com evidência de contexto).
    """
}

# =====================================================
# 7) Construtor de prompt final
# =====================================================

def build_narrative_prompt(
    platforms: List[str],
    analysis_type: str,
    analysis_query: str,
    context_text: str,        # SOMENTE o texto do banco vetorial (sem repetir role/plat)
    summary_json: Dict[str, Any],
    output_format: str = "detalhado",
    granularity: str = "detalhada",
    bilingual: bool = True,
) -> str:

    alias = {
        "descricao":"descriptive","descritiva":"descriptive",
        "preditiva":"predictive","prescritiva":"prescriptive",
        "geral":"general","overall":"general","all":"general"
    }
    key = alias.get((analysis_type or "descriptive").strip().lower(), analysis_type)

    platform_hint = get_platform_prompt(platforms)
    vocabulary = build_vocabulary_block(summary_json)
    gran_block = _granularity_block(granularity, key)
    behavior = ANALYSIS_BEHAVIOR.get(key, ANALYSIS_BEHAVIOR["descriptive"])

    output_spec = f"[FORMATO DE SAÍDA] {output_format.upper()} — adapte ao cliente e ao contexto."
    bilingual_block = (
        "[INSTRUÇÃO LINGUÍSTICA]\nRascunhe mentalmente em inglês (se isso te ajudar), "
        "mas entregue apenas em **português do Brasil**; não exponha raciocínio."
        if bilingual else
        "[INSTRUÇÃO LINGUÍSTICA]\nResponda diretamente em **português do Brasil**."
    )

    prompt = f"""
        {platform_hint}

        {vocabulary}

        {behavior.strip()}
        {gran_block.strip()}

        [CONTEXTO DO CLIENTE (BANCO VETORIAL)]
        Use este conteúdo como evidência/limitação/ativo nas conclusões e recomendações:
        {context_text if context_text else "(sem contexto recuperado)"}

        [DADOS (JSON CONFIÁVEL)]
        Use estritamente como base factual:
        {summary_json}

        {output_spec}
        {bilingual_block}

        [PEDIDO DO USUÁRIO]
        {analysis_query}
    """.strip()

    return prompt
