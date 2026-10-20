"""Source adapters and canonical listing normalization.

External platforms must be connected through this boundary. The adapter may
return a platform-specific dictionary, but the rest of the product only sees
the canonical fields produced here.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any


DEMO_SOURCE = "piaule-demo"
SELOGER_SOURCE = "seloger"


def _text(value: Any, maximum: int) -> str:
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(value or "")).strip()[:maximum]


def _money(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(0, round(value))
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    return int(digits or 0)


def _number(value: Any) -> float | None:
    try:
        return round(float(value), 1) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def normalize_listing(raw: dict[str, Any], source: str, fetched_at: str | None = None) -> dict[str, Any]:
    """Turn one source payload into a safe, stable canonical listing."""

    source_name = _text(source, 80).lower() or "unknown-source"
    source_listing_id = _text(raw.get("source_listing_id") or raw.get("id"), 180)
    title = _text(raw.get("title"), 180) or "Annonce sans titre"
    city = _text(raw.get("city"), 100) or "Ville non précisée"
    rent = _money(raw.get("monthly_rent_eur") or raw.get("rent"))
    canonical = "|".join(
        [source_name, source_listing_id, title.lower(), city.lower(), str(rent)]
    )
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    listing_id = f"listing-{fingerprint[:20]}"
    return {
        "id": listing_id,
        "source": source_name,
        "source_listing_id": source_listing_id or listing_id,
        "fingerprint": fingerprint,
        "title": title,
        "city": city,
        "monthly_rent_eur": rent,
        "property_type": _text(raw.get("property_type") or raw.get("housing_type"), 40) or "unknown",
        "surface_m2": _number(raw.get("surface_m2") or raw.get("surface")),
        "rooms": int(raw["rooms"]) if str(raw.get("rooms", "")).isdigit() else None,
        "url": _text(raw.get("url"), 1000),
        "risk_level": _text(raw.get("risk_level"), 12).lower() or "unknown",
        "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(),
    }


class DemoListingSource:
    """A deterministic source used to validate the pipeline before live access."""

    name = DEMO_SOURCE
    capabilities = ["READ_LISTINGS", "PROVENANCE"]

    def fetch(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "demo-001",
                "title": "T2 lumineux, Lyon 6e",
                "city": "Lyon",
                "monthly_rent_eur": 890,
                "property_type": "apartment",
                "surface_m2": 43,
                "rooms": 2,
                "url": "https://demo.piaulefiction.local/listings/demo-001",
                "risk_level": "low",
            },
            {
                "id": "demo-002",
                "title": "Studio calme, Bordeaux Chartrons",
                "city": "Bordeaux",
                "monthly_rent_eur": 690,
                "property_type": "studio",
                "surface_m2": 21,
                "rooms": 1,
                "url": "https://demo.piaulefiction.local/listings/demo-002",
                "risk_level": "unknown",
            },
        ]


def demo_listings() -> list[dict[str, Any]]:
    source = DemoListingSource()
    return [normalize_listing(item, source.name) for item in source.fetch()]
