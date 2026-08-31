"""Gemma red-team generator + mutator (SOF-162, SESSION_8).

The adversary's GENERATOR runs on Gemma (not Gemini). SESSION_8 makes it real via
PATH B: the Gemini DEVELOPER API (AI Studio / generativelanguage) reached with an
API key — the Vertex publisher path 404s for Gemma on this project (SESSION_5 §4a),
so this is a deliberately different, low-sensitivity surface with its own credential.

Division of labour (the honest claim):
  * generate() — real Gemma produces gen-0 red-team payloads that genuinely enter the
    campaign and get fired. Temp 0.
  * mutate()   — the DETERMINISTIC operators remain the evolution engine, regardless of
    the flag. Gemma is the generator, never the mutation engine.

Demo-safety (mandatory): Gemma is never a live-demo failure point. Real generations are
cached to disk (deterministic, pre-seedable), and ANY slowness/failure/empty response
falls back to the offline naive seed so no take can break. The offline path is a pure
function of the seed, so the same seed reproduces the same generations either way.
"""
from __future__ import annotations

import json
import pathlib
import sys
from random import Random

import sentinel.config as config
from sentinel.config import USE_REAL
from sentinel.redteam import operators
from sentinel.redteam.payloads import Payload, seed_for

_PROMPTS_DIR = pathlib.Path(__file__).resolve().parent / "prompts"
_CACHE_DIR = pathlib.Path(__file__).resolve().parent / "gemma_cache"

# Gemma is the generator only for the TEXT attack classes; the multimodal seed carries
# an image overlay the deterministic beat is built around, so it is left untouched.
_GEMMA_CLASSES = {"prompt_injection", "tool_poisoning"}

_gemma_client = None
_warned: set[str] = set()


def _warn(msg: str) -> None:
    """Loud, once-per-message stderr warning — a Gemma miss is disclosed, never silent."""
    if msg not in _warned:
        _warned.add(msg)
        print(f"[gemma] {msg}", file=sys.stderr)


def _rng_for(seed: int, *tags: object) -> Random:
    """A child RNG deterministically derived from the run seed and a set of tags
    (generation, parent id, ...) so every candidate is independently reproducible."""
    return Random(f"{seed}:" + ":".join(str(t) for t in tags))


# --- generation (gen-0 ancestors) -------------------------------------------


def _offline_seed(attack_class: str) -> Payload:
    """The deterministic naive gen-0 ancestor — deliberately blocked by Model Armor so a
    bypass is EARNED by mutation. Always element 0 of the population: the ladder driver."""
    base = seed_for(attack_class)
    return Payload(
        attack_class=base.attack_class,
        content=base.content,
        ticket_id=base.ticket_id,
        id=f"{attack_class}-g0-0",
        generation=0,
        parent_id=None,
        operators=(),
        origin="seed",
        modality=base.modality,
        carrier_text=base.carrier_text,
    )


def generate(attack_class: str, *, seed: int, context: list[str] | None = None) -> list[Payload]:
    """Return the gen-0 seed population for an attack class: the deterministic naive seed.

    This is intentionally Gemma-independent so the evolutionary ladder (child counts,
    survivor selection, winning lineage) is byte-identical whether Gemma is on or off —
    the reproduction guarantee the demo depends on. Real Gemma payloads enter the campaign
    through `preseed()` as witnessed gen-0 candidates that do NOT perturb selection."""
    return [_offline_seed(attack_class)]


def preseed(attack_class: str, *, seed: int) -> list[Payload]:
    """The genuinely-used Gemma path: gen-0 red-team payloads the campaign FIRES and
    records, proving Gemma is live in the pipeline — without joining survivor selection
    (so the deterministic ladder is untouched). Empty when Gemma is not ready, the class
    is out of scope, or the call fails (the campaign then simply proceeds on the seed)."""
    if not config.gemma_ready() or attack_class not in _GEMMA_CLASSES:
        return []
    return _real_generate(attack_class, seed=seed, context=None)


# --- mutation (deterministic operators — the evolution engine) ---------------


def mutate(
    parent: Payload,
    *,
    seed: int,
    child_index: int,
    corpus_ops: tuple[str, ...] = (),
) -> Payload | None:
    """Produce ONE mutated child from `parent` by applying a not-yet-used operator.
    `corpus_ops` are operators observed in retrieved successful ancestors (SOF-166):
    the mutator prefers them (few-shot bias). Returns None when every operator is already
    exhausted. This is the DETERMINISTIC evolution engine and stays deterministic whether
    or not real Gemma is generating — Gemma is the generator, not the mutation engine."""
    rng = _rng_for(seed, parent.id, child_index)
    remaining = [op for op in operators.OPERATOR_NAMES if op not in parent.operators]
    if not remaining:
        return None

    preferred = [op for op in remaining if op in corpus_ops]
    used_corpus = bool(preferred)
    op = rng.choice(preferred if preferred else remaining)

    new_content = operators.apply_operator(op, parent.content, rng)
    gen = parent.generation + 1
    return Payload(
        attack_class=parent.attack_class,
        content=new_content,
        ticket_id=parent.ticket_id,
        id=f"{parent.attack_class}-g{gen}-{parent.id.split('-')[-1]}{child_index}",
        generation=gen,
        parent_id=parent.id,
        operators=parent.operators + (op,),
        origin="corpus" if used_corpus else "mutation",
        modality=parent.modality,
        carrier_text=parent.carrier_text,
    )


# --- real Gemma path (PATH B: Gemini Developer API, api key, temp 0) ----------


def _client():
    """Lazy google-genai Developer-API client (api key, NOT Vertex). Reused across calls.
    `vertexai=False` is EXPLICIT and load-bearing: the deployed stack sets
    GOOGLE_GENAI_USE_VERTEXAI=TRUE for its Vertex surfaces, which would otherwise route this
    api-key client through aiplatform (where an AI Studio key is rejected 403). The explicit
    arg overrides that env so Gemma always hits generativelanguage."""
    global _gemma_client
    if _gemma_client is None:
        from google import genai

        _gemma_client = genai.Client(vertexai=False, api_key=config.GEMINI_API_KEY)
    return _gemma_client


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text()


def _cache_path(attack_class: str, seed: int) -> pathlib.Path:
    model = config.GEMMA_MODEL.replace("/", "_")
    return _CACHE_DIR / f"{attack_class}-seed{seed}-{model}.json"


def _cache_load(attack_class: str, seed: int) -> list[Payload] | None:
    path = _cache_path(attack_class, seed)
    if not path.exists():
        return None
    try:
        contents = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        _warn(f"cache read failed for {path.name} ({exc!r}); regenerating")
        return None
    return _payloads_from_contents(attack_class, contents)


def _cache_store(attack_class: str, seed: int, payloads: list[Payload]) -> None:
    path = _cache_path(attack_class, seed)
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([p.content for p in payloads], indent=2))
    except OSError as exc:  # a broken cache write must never break a live run
        _warn(f"cache write failed for {path.name} ({exc!r}); continuing uncached")


def _payloads_from_contents(attack_class: str, contents: list[str]) -> list[Payload]:
    base = seed_for(attack_class)
    return [
        Payload(
            attack_class=attack_class,
            content=content,
            ticket_id=base.ticket_id,
            id=f"{attack_class}-g0-gemma{i}",
            generation=0,
            parent_id=None,
            operators=(),
            origin="gemma",
            modality=base.modality,
            carrier_text=base.carrier_text,
        )
        for i, content in enumerate(contents)
    ]


def _real_generate(attack_class: str, *, seed: int, context: list[str] | None) -> list[Payload]:
    """Real Gemma generation, cached + fallback-guarded. Returns the Gemma-generated gen-0
    candidates (empty on any failure, so the campaign simply proceeds on the naive seed)."""
    cached = _cache_load(attack_class, seed)
    if cached is not None:
        return cached
    try:
        contents = _gemma_call(attack_class, n=1)
    except Exception as exc:  # noqa: BLE001 — any transport/SDK error must fall back, loudly
        _warn(f"generate failed ({exc!r}); offline seed only for {attack_class}")
        return []
    if not contents:
        _warn(f"empty/unusable Gemma output; offline seed only for {attack_class}")
        return []
    payloads = _payloads_from_contents(attack_class, contents)
    _cache_store(attack_class, seed, payloads)
    print(
        f"[gemma] real generate: {config.GEMMA_MODEL} produced {len(payloads)} "
        f"{attack_class} payload(s) -> {[p.id for p in payloads]}",
        file=sys.stderr,
    )
    return payloads


def _final_text(resp) -> str:
    """Extract Gemma's ANSWER, skipping reasoning. Gemma 4 is a thinking model with no
    budget knob: it emits `thought=True` parts before the answer, and SDK `.text` is None
    while every part is a thought. We concatenate only the non-thought parts."""
    out: list[str] = []
    for cand in getattr(resp, "candidates", None) or []:
        content = getattr(cand, "content", None)
        for part in (getattr(content, "parts", None) or []):
            if getattr(part, "thought", None):
                continue
            if getattr(part, "text", None):
                out.append(part.text)
    return "\n".join(out).strip()


def _gemma_call(attack_class: str, *, n: int) -> list[str]:
    """One deterministic (temp 0) Gemma completion. Gemma has no system role, so the whole
    instruction is a single user turn; it IS a thinking model, so we budget enough output
    tokens for the reasoning to complete and then read only the answer parts. Returns the
    parsed payload lines (may be empty, which the caller treats as a fallback signal)."""
    from google.genai import types

    prompt = _load_prompt("generate.txt").format(
        attack_class=attack_class,
        n=n,
        seed=seed_for(attack_class).content,
    )
    resp = _client().models.generate_content(
        model=config.GEMMA_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=3072,  # Gemma-4 thinks ~1700 tokens before the answer
            http_options=types.HttpOptions(timeout=int(config.GEMMA_TIMEOUT_S * 1000)),
        ),
    )
    text = _final_text(resp)
    lines = [ln.strip(" -\t") for ln in text.splitlines() if ln.strip()]
    return lines[:n]
