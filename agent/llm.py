import os, sys, time, json, random, datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

PRIMARY = "gemini-3.5-flash-lite"
FALLBACKS = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.7-flash"]

os.makedirs("runs", exist_ok=True)
LOG = f"runs/{datetime.datetime.now():%Y%m%d_%H%M%S}.jsonl"

RETRYABLE = {429, 500, 502, 503, 504}
DEAD_MODELS = set()    # 404 / 400 / 403 this process (bad name, no access)
QUOTA_DEAD = set()     # daily quota exhausted this process


class AllModelsFailed(RuntimeError):
    """Message always starts with 'all models failed' so retry_failed.py's breaker still matches."""


def _log(entry):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _code(e):
    c = getattr(e, "code", None)
    if isinstance(c, int):
        return c
    s = str(e)
    for k in (429, 503, 500, 502, 504, 404, 403, 401, 400):
        if str(k) in s[:40]:
            return k
    return None


def _is_daily_quota(e):
    """429 whose message says the cap is per day. Backoff is useless, skip the model."""
    s = str(e).lower()          # full message, not truncated
    return "429" in s[:40] and ("per day" in s or "perday" in s)


def _is_bad_key(e):
    s = str(e).lower()
    return "api key not valid" in s or "api_key_invalid" in s or "invalid api key" in s


def _retry_delay(e, attempt):
    """Honor a server-suggested delay if present, else exponential backoff with jitter."""
    s = str(e)
    if "retryDelay" in s:
        try:
            part = s.split("retryDelay")[1]
            digits = "".join(ch for ch in part[:20] if ch.isdigit() or ch == ".")
            if digits:
                return min(float(digits) + 1, 90)
        except Exception:
            pass
    return min(5 * (2 ** attempt), 60) + random.random()


def call(prompt, model=None, retries=3, json_mode=False):
    """Returns (text, model_used). Raises AllModelsFailed('all models failed: ...') with causes."""
    first = model or PRIMARY
    models = [first] + [m for m in FALLBACKS if m != first]
    cfg = types.GenerateContentConfig(response_mime_type="application/json") if json_mode else None
    causes = {}

    for m in models:
        if m in DEAD_MODELS:
            causes[m] = "skipped (dead earlier in this run)"
            continue
        if m in QUOTA_DEAD:
            causes[m] = "daily quota exhausted"
            continue
        for attempt in range(retries):
            try:
                kwargs = {"model": m, "contents": prompt}
                if cfg:
                    kwargs["config"] = cfg
                r = client.models.generate_content(**kwargs)
                text = r.text
                if not text:
                    raise ValueError("empty response (possibly blocked)")
                _log({"model": m, "ok": True, "attempt": attempt, "prompt_chars": len(prompt)})
                return text, m
            except Exception as e:
                code = _code(e)
                msg = f"{type(e).__name__} {code or ''}: {str(e)[:120]}"
                causes[m] = msg
                _log({"model": m, "ok": False, "attempt": attempt, "code": code, "err": str(e)[:300]})

                # 1. bad API key: stop everything
                if _is_bad_key(e):
                    raise AllModelsFailed(f"all models failed: bad GEMINI_API_KEY ({msg})")

                # 2. daily quota: skip model, no sleep
                if _is_daily_quota(e):
                    QUOTA_DEAD.add(m)
                    causes[m] = "daily quota exhausted"
                    print(f"   [{m}] daily quota exhausted, skipping")
                    break

                print(f"   [{m}] attempt {attempt + 1}/{retries}: {msg}")

                # 3. bad model name / no access: skip model
                if code in (400, 403, 404):
                    DEAD_MODELS.add(m)
                    break

                # 4. transient: back off and retry
                if code in RETRYABLE or code is None or isinstance(e, ValueError):
                    if attempt < retries - 1:
                        time.sleep(_retry_delay(e, attempt))
                    continue
                break    # anything else: next model

    # all models out
    if all(m in QUOTA_DEAD for m in models):
        raise AllModelsFailed(
            "all models failed: daily quota exhausted on all models. "
            "Resets ~13:30 IST (midnight Pacific) or enable billing."
        )
    detail = "; ".join(f"{m}: {c}" for m, c in causes.items())
    raise AllModelsFailed(f"all models failed: {detail}")


def quota_dead():
    """True if every configured model is out of daily quota. Callers can use this to stop a batch."""
    return all(m in QUOTA_DEAD for m in [PRIMARY] + FALLBACKS)


if __name__ == "__main__":
    # python -m agent.llm            -> smoke test
    # python -m agent.llm --models   -> list models your key can call
    try:
        if "--models" in sys.argv:
            for mdl in client.models.list():
                print(mdl.name)
        else:
            print(call("Reply with the word ok"))
    except AllModelsFailed as e:
        print(f"FAIL: {e}")
        sys.exit(1)