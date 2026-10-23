import hashlib
import json
import re


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def content_hash(heading: str, elements: list) -> str:
    # Exclude layout, confidence, page numbers, warnings and extraction method.
    semantic = [{"kind": e["kind"], "text": normalize(e["text"]), **({"rows": [[normalize(c) for c in r] for r in e["rows"]]} if "rows" in e else {})} for e in elements]
    return digest({"heading": normalize(heading), "elements": semantic})
