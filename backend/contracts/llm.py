"""
LLM Caller — ESPRIT (Llama-3.1-70B) + Groq (8B/70B) with best-model selection.
Uses the same comparison logic as the notebook Phase 5D.
"""
import os
import time
import json
import requests
from openai import OpenAI

# ── Config from environment ───────────────────────────────────────────────────
ESPRIT_API_KEY = os.environ.get(
    'ESPRIT_API_KEY', 'sk-e8d1f52f7bce4a349af80b4080b24205'
)
ESPRIT_BASE_URL = 'https://tokenfactory.esprit.tn/api'
ESPRIT_MODEL = 'hosted_vllm/Llama-3.1-70B-Instruct'

GROQ_API_KEY = os.environ.get(
    'GROQ_API_KEY', ''
)
GROQ_BASE_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODELS = {
    'Llama-3-8B': 'llama-3.1-8b-instant',
    'Llama-3-70B': 'llama-3.3-70b-versatile',
}

# ── Best model metadata (loaded at startup or after comparison) ───────────────
_best_model_meta = None
_BEST_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'best_model.json'
)


def _get_esprit_client():
    return OpenAI(api_key=ESPRIT_API_KEY, base_url=ESPRIT_BASE_URL)


def call_groq_model(model_id, system_prompt, user_message,
                     max_new_tokens=3000, temperature=0.1):
    """Call a Groq model."""
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model_id,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message},
        ],
        'max_tokens': max_new_tokens,
        'temperature': temperature,
        'stream': False,
    }
    t0 = time.time()
    response = requests.post(
        GROQ_BASE_URL, headers=headers, json=payload, timeout=120
    )
    gen_time = round(time.time() - t0, 2)

    if response.status_code == 200:
        content = response.json()['choices'][0]['message']['content'].strip()
        return content, gen_time
    raise Exception(f'Groq {response.status_code}: {response.text[:200]}')


def call_llm(system_prompt, user_message, platform='esprit',
             model_id=None, max_tokens=3000):
    """
    Unified LLM caller. Supports 'esprit' and 'groq' platforms.
    Returns (contract_text, elapsed_seconds, tokens_used).
    """
    if platform == 'esprit':
        model_id = model_id or ESPRIT_MODEL
        client = _get_esprit_client()
        start = time.time()
        resp = client.chat.completions.create(
            model=model_id,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_message},
            ],
            max_tokens=max_tokens,
            temperature=0.1,
        )
        elapsed = round(time.time() - start, 2)
        contract = resp.choices[0].message.content
        tokens = resp.usage.total_tokens if resp.usage else 0
        return contract, elapsed, tokens

    elif platform == 'groq':
        model_id = model_id or 'llama-3.1-8b-instant'
        contract, elapsed = call_groq_model(
            model_id, system_prompt, user_message, max_new_tokens=max_tokens
        )
        return contract, elapsed, 0

    raise ValueError(f'Unknown platform: {platform}')


def get_best_model():
    """
    Get the best model configuration.
    Loads from saved metadata or defaults to ESPRIT 70B.
    """
    global _best_model_meta
    if _best_model_meta:
        return _best_model_meta

    # Try to load saved best model
    if os.path.exists(_BEST_MODEL_PATH):
        try:
            with open(_BEST_MODEL_PATH, 'r') as f:
                _best_model_meta = json.load(f)
                return _best_model_meta
        except Exception:
            pass

    # Default: Groq Llama-3.1-8B
    _best_model_meta = {
        'best_model_label': 'Llama-3.1-8B (Groq)',
        'platform': 'groq',
        'model_id': 'llama-3.1-8b-instant',
        'nlp_version': 'advanced_7_7',
    }
    return _best_model_meta


def save_best_model(meta):
    """Save the best model metadata."""
    global _best_model_meta
    _best_model_meta = meta
    meta['saved_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(_BEST_MODEL_PATH, 'w') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
