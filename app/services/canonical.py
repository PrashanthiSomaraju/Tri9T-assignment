import hashlib
import json
import re


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def content_hash(heading: str, elements: list) -> str:
    """Hash text, element order/kinds and table cell associations, excluding layout.

    Consecutive visual paragraph lines form one canonical text run, so changes
    in line/page wrapping alone do not invalidate an otherwise identical source.
    """
    semantic = []
    for e in elements:
        item = {"kind": e["kind"], "text": normalize(e["text"])}
        if "rows" in e:
            item["rows"] = [[normalize(c) for c in row] for row in e["rows"]]
        if (
            item["kind"] == "paragraph"
            and semantic
            and semantic[-1]["kind"] == "paragraph"
        ):
            semantic[-1]["text"] = normalize(semantic[-1]["text"] + " " + item["text"])
        else:
            semantic.append(item)
    return digest({"heading": normalize(heading), "elements": semantic})
