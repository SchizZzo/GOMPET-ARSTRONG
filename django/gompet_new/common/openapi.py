"""Helpers for readability-focused OpenAPI schema variants."""

from __future__ import annotations

from typing import Dict

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}

_TAG_RULES = [
    ("/users/auth/", "Authentication"),
    ("/users/organization", "Organizations"),
    ("/users/species", "Organizations"),
    ("/users/users", "Users"),
    ("/users/", "Users"),
    ("/animals/", "Animals"),
    ("/litters/", "Litters"),
    ("/posts/", "Posts"),
    ("/articles/", "Articles"),
    ("/common/", "Community"),
]

_VERB_TO_ACTION = {
    "get": "Pobierz",
    "post": "Utworz",
    "put": "Zastap",
    "patch": "Aktualizuj",
    "delete": "Usun",
    "options": "Opcje",
    "head": "Naglowki",
    "trace": "Trace",
}


def _classify_tag(path: str) -> str:
    for prefix, tag in _TAG_RULES:
        if path.startswith(prefix):
            return tag
    return "System"


def _resource_label(path: str) -> str:
    parts = [part for part in path.strip("/").split("/") if part and not part.startswith("{")]
    if not parts:
        return "zasob"
    if len(parts) >= 2:
        label = parts[1]
    else:
        label = parts[0]
    return label.replace("-", " ")


def _shorten_description(description: str, max_len: int = 240) -> str:
    normalized = " ".join((description or "").split())
    if len(normalized) <= max_len:
        return normalized
    cropped = normalized[:max_len].rsplit(" ", 1)[0]
    return f"{cropped}..."


def _build_summary(method: str, path: str) -> str:
    action = _VERB_TO_ACTION.get(method.lower(), method.upper())
    has_lookup = "{" in path and "}" in path
    resource = _resource_label(path)

    if method.lower() == "get":
        action = "Pobierz szczegoly" if has_lookup else "Pobierz liste"
    return f"{action}: {resource}"


def readable_v3_postprocessing_hook(result: Dict, generator, request, public) -> Dict:
    """Normalize tags and operation descriptions for a cleaner Swagger v3 layout."""
    paths = result.get("paths", {})

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(operation, dict):
                continue

            operation["tags"] = [_classify_tag(path)]

            if not operation.get("summary"):
                operation["summary"] = _build_summary(method, path)

            if operation.get("description"):
                operation["description"] = _shorten_description(operation["description"])

    result["paths"] = dict(sorted(paths.items(), key=lambda item: item[0]))
    return result
