from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BracketTag:
    id: str
    message: str
    start: int
    end: int


def extract_bracket_tags(text: str, prefix: str) -> list[BracketTag]:
    tags: list[BracketTag] = []
    i = 0
    while i < len(text):
        if text[i] != "[" or i + 1 >= len(text) or text[i + 1] != prefix:
            i += 1
            continue
        tag_start = i
        colon_index = text.find(":", i + 2)
        if colon_index == -1:
            i += 1
            continue
        tag_id = text[i + 2 : colon_index].strip()
        if not tag_id or "[" in tag_id or "]" in tag_id:
            i += 1
            continue
        depth = 1
        j = colon_index + 1
        while j < len(text) and depth > 0:
            if text[j] == "[":
                depth += 1
            elif text[j] == "]":
                depth -= 1
            j += 1
        if depth == 0:
            tags.append(BracketTag(id=tag_id, message=text[colon_index + 1 : j - 1].strip(), start=tag_start, end=j))
        i = j
    return tags


def strip_bracket_tags(text: str, prefix: str) -> str:
    tags = extract_bracket_tags(text, prefix)
    if not tags:
        return text
    result = ""
    last_end = 0
    for tag in tags:
        result += text[last_end : tag.start]
        last_end = tag.end
    result += text[last_end:]
    return result.strip()


def convert_tags_to_readable(text: str, from_agent: str | None = None) -> str:
    with_mentions = _convert_prefix_tags(text, "@", f"@{from_agent} -> @" if from_agent else "-> @")
    return _convert_prefix_tags(with_mentions, "#", "#")


def _convert_prefix_tags(text: str, prefix: str, readable_prefix: str) -> str:
    tags = extract_bracket_tags(text, prefix)
    if not tags:
        return text
    result = ""
    last_end = 0
    for tag in tags:
        result += text[last_end : tag.start]
        result += f"{readable_prefix}{tag.id}: {tag.message}"
        last_end = tag.end
    result += text[last_end:]
    return result.strip()
