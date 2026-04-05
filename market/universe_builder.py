"""Build and validate market universe for analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd


@dataclass(frozen=True)
class UniverseConstraints:
    """Screening constraints for the market universe."""

    min_avg_volume: float = 1000.0
    min_history_rows: int = 180


class UniverseBuilder:
    """Constructs valid symbol universe from market snapshot and history."""

    def __init__(self, constraints: UniverseConstraints | None = None) -> None:
        self.constraints = constraints or UniverseConstraints()

    def build_symbols(
        self,
        snapshot: pd.DataFrame,
        historical_universe: Dict[str, pd.DataFrame],
    ) -> List[str]:
        """Build list of valid symbols for downstream analysis."""
        if snapshot.empty:
            return []

        symbols: List[str] = []
        snapshot_indexed = snapshot.set_index("symbol", drop=False)
        for symbol, history in historical_universe.items():
            if symbol not in snapshot_indexed.index or history.empty:
                continue
            if len(history) < self.constraints.min_history_rows:
                continue
            avg_volume = float(history["volume"].tail(90).mean())
            if avg_volume < self.constraints.min_avg_volume:
                continue
            symbols.append(symbol)
        return sorted(set(symbols))
