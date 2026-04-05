"""Market scanner orchestration."""

from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd

from market.universe_builder import UniverseBuilder


class MarketScanner:
    """Creates scan-ready stock universe from raw market data."""

    def __init__(self, universe_builder: UniverseBuilder | None = None) -> None:
        self.universe_builder = universe_builder or UniverseBuilder()

    def scan(
        self,
        snapshot: pd.DataFrame,
        historical_universe: Dict[str, pd.DataFrame],
    ) -> Tuple[List[str], Dict[str, pd.DataFrame]]:
        """Return filtered symbols and matching historical data."""
        symbols = self.universe_builder.build_symbols(snapshot, historical_universe)
        filtered_history = {symbol: historical_universe[symbol] for symbol in symbols if symbol in historical_universe}
        return symbols, filtered_history
