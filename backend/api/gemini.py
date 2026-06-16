import os
import json
import re
from typing import Any, Dict, List

import requests

GEMINI_GEN_BASE = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"
GEMINI_EMBED_BASE = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"


def _get_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return key


def _call_gemini_text(prompt_text: str, timeout: int = 30) -> str:
    """Call Gemini with a plain text prompt and return the first text candidate."""
    key = _get_api_key()
    url = f"{GEMINI_GEN_BASE}?key={key}"
    payload = {
        "contents": [
            {"parts": [{"text": prompt_text}]}
        ]
    }
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    # Defensive extraction
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        raise RuntimeError(f"Unexpected Gemini response schema: {e}")


def json_strict_loads(text: str) -> Any:
    """
    Try to parse JSON from LLM text. Strips code fences and surrounding noise.
    Raises ValueError on failure.
    """
    if text is None:
        raise ValueError("Empty LLM response")
    # Strip common code fences ```json ... ``` or ``` ... ```
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    # Find first JSON object or array if extra prose exists
    start_obj = cleaned.find("{")
    start_arr = cleaned.find("[")
    start = min([i for i in [start_obj, start_arr] if i != -1], default=-1)
    if start > 0:
        cleaned = cleaned[start:]
    return json.loads(cleaned)


def build_policy_gate_prompt(company_name: str, user_question: str, context_snippets: List[str] | None = None) -> str:
    snippet_lines = []
    for idx, snippet in enumerate(context_snippets or [], start=1):
        snippet_lines.append(f"[Snippet {idx}]\n{snippet[:2500]}")
    ctx = "\n\nContext snippets (may be empty):\n" + "\n\n".join(snippet_lines)
    return (
        "You are a policy gatekeeper for a company's internal chatbot.\n"
        f"Company: {company_name or 'N/A'}\n"
        + ctx + "\n\n"
        "Task: Determine whether the user's question should be answered under company policy.\n"
        "If the question asks about information that appears in the context snippets, mark it as related.\n"
        "Do not mark a question unrelated just because the relevant text appears later in a long snippet.\n"
        "Return STRICT JSON (no markdown, no comments) with the following schema:\n"
        "{\n"
        "  \"related\": boolean,\n"
        "  \"reason\": string,\n"
        "  \"sanitized_query\": string,\n"
        "  \"policy_tags\": [string]\n"
        "}\n\n"
        "User question: \"" + user_question + "\"\n"
        "If you cannot ensure JSON compliance, output an empty JSON object {}."
    )


def classify_question(company_name: str, user_question: str, context_snippets: List[str] | None = None) -> Dict[str, Any]:
    prompt = build_policy_gate_prompt(company_name, user_question, context_snippets)
    text = _call_gemini_text(prompt)
    data = json_strict_loads(text)
    if not isinstance(data, dict):
        raise ValueError("Classifier response is not a JSON object")
    data.setdefault("related", True)
    data.setdefault("reason", "")
    data.setdefault("sanitized_query", user_question)
    data.setdefault("policy_tags", [])
    return data


def build_answer_prompt(company_name: str, sanitized_query: str, policy_tags: List[str], context_snippets: List[str]) -> str:
    # Number each snippet for better citation
    context_text = "\n\n".join(f"[Snippet {i+1}]\n{s}" for i, s in enumerate(context_snippets))
    
    return (
        "You are a helpful assistant answering questions about company documents.\n"
        f"Company: {company_name or 'N/A'}\n\n"
        "IMPORTANT INSTRUCTIONS:\n"
        "1. Answer ONLY using information from the context snippets below\n"
        "2. Be specific and accurate - quote relevant parts when helpful\n"
        "3. If the context doesn't contain enough information, say 'I don't have enough information in the provided context to answer that'\n"
        "4. Do NOT mention snippet labels such as [Snippet 1] in the answer text shown to the user\n"
        "5. Return your response as STRICT JSON (no markdown, no code blocks) with these exact keys:\n"
        "   - answer: string (your complete answer)\n"
        "   - follow_up_question: string (optional related question user might ask)\n"
        "   - citations: array of objects with {snippet_num: number, text: string}\n\n"
        "CONTEXT:\n" + context_text + "\n\n"
        f"QUESTION: {sanitized_query}\n\n"
        "Return only valid JSON with the answer, follow_up_question, and citations keys."
    )


def answer_question(company_name: str, sanitized_query: str, policy_tags: List[str], context_snippets: List[str]) -> Dict[str, Any]:
    text = _call_gemini_text(build_answer_prompt(company_name, sanitized_query, policy_tags, context_snippets))
    data = json_strict_loads(text)
    if not isinstance(data, dict):
        raise ValueError("Answerer response is not a JSON object")
    data.setdefault("answer", "")
    data.setdefault("follow_up_question", "")
    data.setdefault("citations", [])
    return data


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Return list of embedding vectors for input texts using Gemini Embeddings."""
    key = _get_api_key()
    url = f"{GEMINI_EMBED_BASE}?key={key}"
    embeddings: List[List[float]] = []

    for text in texts:
        payload = {
            "model": "models/gemini-embedding-001",
            "content": {"parts": [{"text": text[:8000]}]},
            "taskType": "RETRIEVAL_DOCUMENT",
            "outputDimensionality": int(os.getenv("EMBEDDING_DIM", "768")),
        }
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code >= 400:
            resp.raise_for_status()

        data = resp.json()
        embedding = data.get("embedding", {}).get("values", [])
        if not embedding:
            raise RuntimeError("Unexpected Gemini embedding response schema")
        embeddings.append(embedding)

    return embeddings
