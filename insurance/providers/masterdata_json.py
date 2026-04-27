from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.conf import settings


logger = logging.getLogger(__name__)


def normalize_masterdata_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().upper()
    text = text.replace("&", "AND")
    return re.sub(r"[^A-Z0-9]+", "", text)


class MissingMasterdataError(FileNotFoundError):
    """Raised when precompiled provider masterdata JSON is not available."""


class ProviderJsonMasterdata:
    def __init__(self, provider_code: str, json_root: Path):
        self.provider_code = provider_code.upper()
        self.json_root = Path(json_root)

    @lru_cache(maxsize=None)
    def _load_json(self, dataset: str) -> dict[str, Any]:
        path = self.json_root / f"{dataset}.json"
        if not path.exists():
            raise MissingMasterdataError(
                f"Missing {self.provider_code} masterdata JSON '{path.name}'. "
                "Run 'python manage.py build_provider_masterdata'."
            )
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def metadata(self, dataset: str) -> dict[str, Any]:
        return dict(self._load_json(dataset).get("metadata") or {})

    def records(self, dataset: str) -> list[dict[str, str]]:
        return list(self._load_json(dataset).get("records") or [])

    def require_records(self, dataset: str, *, fallback_loader=None) -> list[dict[str, str]]:
        try:
            return self.records(dataset)
        except MissingMasterdataError:
            if settings.DEBUG and fallback_loader is not None:
                logger.warning(
                    "%s masterdata JSON for '%s' is missing; using Excel fallback because DEBUG=True.",
                    self.provider_code,
                    dataset,
                )
                return list(fallback_loader(dataset))
            raise

