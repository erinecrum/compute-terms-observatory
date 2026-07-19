"""Source registry loader.

The registry (`registry.yaml`) maps each provider to the public documents we
archive and compare. It is the single place URLs live. Adding a provider — or a
new document for an existing provider — is a registry edit, not a code change.

Registry shape:

    providers:
      - provider: aws
        provider_name: Amazon Web Services
        documents:
          - doc_type: service_terms
            name: AWS Service Terms
            url: https://aws.amazon.com/service-terms/
            notes: optional free text
          - doc_type: sla
            ...
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import yaml

from .model import DOC_TYPES, FETCH_METHODS, OPENNESS, SEGMENTS, Document


class Registry:
    def __init__(self, documents: List[Document]):
        self._documents = documents

    def documents(self) -> List[Document]:
        return list(self._documents)

    def fetchable(self) -> List[Document]:
        """Only documents with a confirmed URL are fetched. Gap entries
        (not_published / within_service_terms) are coverage records, not fetch
        targets."""
        return [d for d in self._documents if d.is_fetchable]

    def for_provider(self, provider: str) -> List[Document]:
        return [d for d in self._documents if d.provider == provider]

    def providers(self) -> List[str]:
        # Preserve registry order, de-duplicated.
        seen: Dict[str, None] = {}
        for d in self._documents:
            seen.setdefault(d.provider, None)
        return list(seen)

    def provider_names(self) -> Dict[str, str]:
        return {d.provider: d.provider_name for d in self._documents}


def load_registry(path: str | Path = "registry.yaml") -> Registry:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not raw or "providers" not in raw:
        raise ValueError(f"{path}: expected a top-level 'providers:' list")

    documents: List[Document] = []
    seen_slugs: set = set()
    for p in raw["providers"]:
        provider = p["provider"]
        provider_name = p["provider_name"]
        segment = p.get("segment", "hyperscaler")
        if segment not in SEGMENTS:
            raise ValueError(f"{provider}: unknown segment {segment!r}. Valid: {', '.join(SEGMENTS)}")
        parent_company = p.get("parent_company", "")
        openness = p.get("openness", "")
        if openness and openness not in OPENNESS:
            raise ValueError(f"{provider}: unknown openness {openness!r}. Valid: {', '.join(OPENNESS)}")
        if segment == "model_provider" and openness not in OPENNESS:
            raise ValueError(f"{provider}: model_provider entries need openness (closed_api|open_weight).")
        for d in p.get("documents", []):
            doc_type = d["doc_type"]
            if doc_type not in DOC_TYPES:
                raise ValueError(
                    f"{provider}: unknown doc_type {doc_type!r}. "
                    f"Known types: {', '.join(DOC_TYPES)}"
                )
            fetch_method = d.get("fetch_method", "direct")
            if fetch_method not in FETCH_METHODS:
                raise ValueError(
                    f"{provider}/{doc_type}: unknown fetch_method {fetch_method!r}. "
                    f"Valid: {', '.join(FETCH_METHODS)}"
                )
            status = d.get("status", "verified")
            valid_status = ("verified", "unverified", "not_published", "within_service_terms")
            if status not in valid_status:
                raise ValueError(
                    f"{provider}/{doc_type}: unknown status {status!r}. "
                    f"Valid: {', '.join(valid_status)}"
                )
            url = d.get("url", "")
            if status in ("verified", "unverified") and not url:
                raise ValueError(
                    f"{provider}/{doc_type}: status {status!r} requires a url."
                )
            if status in ("not_published", "within_service_terms") and url:
                raise ValueError(
                    f"{provider}/{doc_type}: status {status!r} must not carry a url "
                    f"(it records a coverage gap, not a fetchable document)."
                )
            doc = Document(
                provider=provider,
                provider_name=provider_name,
                doc_type=doc_type,
                name=d["name"],
                url=url,
                slug=d.get("slug", ""),
                notes=d.get("notes", ""),
                status=status,
                segment=segment,
                parent_company=parent_company,
                openness=openness,
                generation=d.get("generation", ""),
                capture_state=d.get("capture_state", ""),
                capture_cause=d.get("capture_cause", ""),
                fetch_method=fetch_method,
            )
            key = (provider, doc.slug)
            if key in seen_slugs:
                raise ValueError(
                    f"{provider}: duplicate slug {doc.slug!r}. Give one document an "
                    f"explicit 'slug:' so its snapshots don't collide."
                )
            seen_slugs.add(key)
            documents.append(doc)
    if not documents:
        raise ValueError(f"{path}: no documents found")
    return Registry(documents)
