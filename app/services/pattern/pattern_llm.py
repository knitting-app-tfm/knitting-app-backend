import json

from groq import Groq

from app.core.config import settings
from app.models.pattern import CraftType, GaugeUnit, YarnWeight

_LLM_PROMPT = """You are a knitting and crochet pattern parser.
Extract metadata from the pattern text below and return ONLY a JSON object with this exact structure (use null for unknown fields):

{
  "title": "string",
  "craft": "KNITTING" | "CROCHET" | null,
  "sizes": ["string", ...] | null,
  "gauge_stitches": number | null,
  "gauge_rows": number | null,
  "gauge_size": number | null,
  "gauge_unit": "CM" | "INCH" | null,
  "needle_size": "string" | null,
  "yarns": [
    {
      "label": "string" | null,
      "yarn_weight": "LACE" | "FINGERING" | "DK" | "ARAN" | "BULKY" | null,
      "meters_per_unit": number | null,
      "grams_per_unit": number | null,
      "grams_needed": [number, ...] | null,
      "strands": integer
    }
  ]
}

For "grams_needed": return an array with one value per size, in the same order as "sizes".
If the pattern gives a single value (one-size pattern), return a single-element array, e.g. [200].
If the pattern does not specify grams needed for a yarn, return null.

Pattern text:
"""


def get_parsed(client: Groq, text: str) -> tuple[dict, str]:
    if settings.USE_MOCK_LLM:
        return mock_response()
    return call_llm(client, text)


def call_llm(client: Groq, text: str) -> tuple[dict, str]:
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": _LLM_PROMPT + text}],
            response_format={"type": "json_object"},
        )
        json_str = response.choices[0].message.content
        if json_str is None:
            raise ValueError("Empty response from LLM")
        raw = json.loads(json_str)
        parsed = normalize(raw)
        return parsed, json.dumps(parsed, ensure_ascii=False)
    except Exception:
        fallback = {"title": "Unknown", "craft": None, "yarns": []}
        return fallback, json.dumps(fallback)


def mock_response() -> tuple[dict, str]:
    mock = {
        "title": "Mock Knitting Pattern",
        "craft": "KNITTING",
        "sizes": ["S", "M", "L"],
        "gauge_stitches": 22.0,
        "gauge_rows": 30.0,
        "gauge_size": 10.0,
        "gauge_unit": "CM",
        "needle_size": "4mm",
        "yarns": [
            {
                "label": "Main",
                "yarn_weight": "DK",
                "meters_per_unit": 200.0,
                "grams_per_unit": 100.0,
                "grams_needed": [300.0, 350.0, 400.0],
                "strands": 1,
            }
        ],
    }
    json_str = json.dumps(mock, ensure_ascii=False)
    parsed = normalize(mock)
    return parsed, json_str


def normalize(raw: dict) -> dict:
    try:
        raw["craft"] = CraftType(raw.get("craft"))
    except (ValueError, KeyError):
        raw["craft"] = None

    try:
        raw["gauge_unit"] = GaugeUnit(raw.get("gauge_unit"))
    except (ValueError, KeyError):
        raw["gauge_unit"] = None

    for yarn in raw.get("yarns", []):
        try:
            yarn["yarn_weight"] = YarnWeight(yarn.get("yarn_weight"))
        except (ValueError, KeyError):
            yarn["yarn_weight"] = None
        yarn.setdefault("strands", 1)
        gn = yarn.get("grams_needed")
        if gn is not None and not isinstance(gn, list):
            yarn["grams_needed"] = [float(gn)]

    return raw
