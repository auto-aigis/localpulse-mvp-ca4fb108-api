import os
import httpx
import json

GATEWAY_URL = os.getenv("AI_GATEWAY_URL", "")
PROJECT_ID = os.getenv("PROJECT_ID", "localpulse")
PROJECT_SECRET = os.getenv("PROJECT_SECRET", "")

GATEWAY_HEADERS = {
    "X-Gateway-Project-Id": PROJECT_ID,
    "X-Gateway-Secret": PROJECT_SECRET,
    "Content-Type": "application/json",
}

async def ai_chat(messages: list[dict], model: str = "sonnet", max_tokens: int = 2048, api_key: str = None) -> str:
    if api_key:
        return await _openai_chat(messages, model, max_tokens, api_key)
    
    if not GATEWAY_URL:
        raise Exception("AI Gateway not configured")
    
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{GATEWAY_URL}/chat/completions",
            headers=GATEWAY_HEADERS,
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
        )
        resp.raise_for_status()
        return resp.json()["content"]

async def _openai_chat(messages: list[dict], model: str, max_tokens: int, api_key: str) -> str:
    import base64
    
    async with httpx.AsyncClient(timeout=60) as client:
        if model in ("sonnet", "haiku", "opus"):
            model = "gpt-4o"
        basic_auth = base64.b64encode(f":{api_key}".encode()).decode()
        headers = {
            "Authorization": f"Basic {basic_auth}",
            "Content-Type": "application/json",
        }
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

async def generate_digest(events: list[dict], taste_profile: dict, feedback: list[dict], max_events: int = 10, api_key: str = None) -> list[dict]:
    liked = [f["event"] for f in feedback if f.get("rating") == "thumbs_up"]
    disliked = [f["event"] for f in feedback if f.get("rating") == "thumbs_down"]
    
    system_prompt = f"""You are LocalPulse, a curated local event discovery service. Your voice is warm, authentic, specific, and editorial.

For each event, write a 2-3 sentence "vibe description" in LocalPulse's voice. DON'T just repeat event details — capture atmosphere, crowd, what makes it special.

User taste profile:
- Event types: {', '.join(taste_profile.get('event_types', []))}
- Social comfort: {taste_profile.get('social_comfort', 'balanced')}
- Budget: {taste_profile.get('budget_range', 'any')}
- Schedule: {', '.join(taste_profile.get('schedule_prefs', []))}
- Neighborhood: {taste_profile.get('neighborhood', 'Austin, TX')}
- Vibe: {taste_profile.get('vibe_description', 'No specific vibe')}

Liked (weight higher): {liked}
Disliked (avoid): {disliked}

Generate exactly {max_events} events with vibe descriptions as JSON: [{"event_id", "title", "event_date", "location", "category", "source_url", "ai_vibe_description"}]"""
    
    user_prompt = f"Events:\n{json.dumps(events[:50])}"
    
    result = await ai_chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ], model="sonnet", max_tokens=4000, api_key=api_key)
    
    try:
        start = result.find("[")
        end = result.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(result[start:end])
    except:
        pass
    
    return []
