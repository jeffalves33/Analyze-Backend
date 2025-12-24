# services/goals_service.py
import os
import json
from typing import Dict, Any

from openai import OpenAI

from utils.prompts.goals_prompts import GOAL_SUGGESTIONS_SYSTEM, GOAL_ANALYSIS_SYSTEM

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _call_llm_json(system_prompt: str, user_payload: Dict[str, Any], model: str = None) -> Dict[str, Any]:
    model_name = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
        ],
        temperature=0.4
    )

    text = resp.choices[0].message.content.strip()

    # garante JSON parseável
    try:
        return json.loads(text)
    except Exception:
        # fallback: tenta extrair o primeiro bloco json
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end+1])
        raise

def generate_goal_suggestions(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _call_llm_json(GOAL_SUGGESTIONS_SYSTEM, payload)

def generate_goal_analysis(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _call_llm_json(GOAL_ANALYSIS_SYSTEM, payload)
