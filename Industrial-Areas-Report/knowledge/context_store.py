"""Store and retrieve approved report contexts for cumulative knowledge."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class ContextStore:
    """Persistent store for approved annual report contexts.

    Each approved report becomes a formal context layer that informs
    the next year's analysis. Stored as JSON files under
    ``{base_dir}/{area}/{year}.json``.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            base_dir = Path(__file__).parent / "contexts"
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _area_dir(self, area: str) -> Path:
        d = self.base_dir / area
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_approved_context(
        self, area: str, year: int, context: Dict[str, Any]
    ) -> Path:
        """Save an approved context for *area* / *year*."""
        path = self._area_dir(area) / f"{year}.json"
        payload = {
            "area": area,
            "year": year,
            "approved_at": datetime.now().isoformat(),
            "context": context,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("Saved context for %s/%d → %s", area, year, path)
        return path

    def load_context(self, area: str, year: int) -> Optional[Dict[str, Any]]:
        """Load a single approved context, or None."""
        path = self._area_dir(area) / f"{year}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("context")

    def get_context_chain(self, area: str) -> List[Dict[str, Any]]:
        """Return all approved contexts for *area*, oldest first."""
        area_dir = self._area_dir(area)
        chain = []
        for path in sorted(area_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                chain.append(data)
            except (json.JSONDecodeError, KeyError):
                log.warning("Skipping invalid context file: %s", path)
        return chain

    def get_latest(self, area: str) -> Optional[Dict[str, Any]]:
        """Return the most recent approved context, or None."""
        chain = self.get_context_chain(area)
        if not chain:
            return None
        return chain[-1].get("context")

    def get_changes_since_last(
        self, area: str, current_families: Dict[str, int]
    ) -> Dict[str, Any]:
        """Compare current family indices to the last approved context.

        Returns dict with keys: new_contaminants, worsened, improved, unchanged.
        """
        previous = self.get_latest(area)
        if not previous:
            return {
                "new_contaminants": list(current_families.keys()),
                "worsened": [],
                "improved": [],
                "unchanged": [],
            }

        prev_families = previous.get("family_indices", {})
        new = [f for f in current_families if f not in prev_families]
        worsened = [
            f for f in current_families
            if f in prev_families and current_families[f] > prev_families[f]
        ]
        improved = [
            f for f in current_families
            if f in prev_families and current_families[f] < prev_families[f]
        ]
        unchanged = [
            f for f in current_families
            if f in prev_families and current_families[f] == prev_families[f]
        ]
        return {
            "new_contaminants": new,
            "worsened": worsened,
            "improved": improved,
            "unchanged": unchanged,
        }
