from pocketStudio.services.team_routing import extract_bracket_tags, strip_bracket_tags

def split_candidate_ids(raw_ids: str) -> list[str]:
    return [item.strip().lower() for item in raw_ids.split(",") if item.strip()]

def extract_tags(text: str, prefix: str) -> list[tuple[str, str]]:
    return [(tag.id, tag.message) for tag in extract_bracket_tags(text, prefix)]

def strip_tags(text: str, prefix: str) -> str:
    return strip_bracket_tags(text, prefix)

def get_directed_messages(leader_output: str, member_id: str) -> list[str]:
    lookup = member_id.lower()
    messages: list[str] = []
    for raw_ids, content in extract_tags(leader_output, "@"):
        if lookup in split_candidate_ids(raw_ids):
            messages.append(content)
    return messages