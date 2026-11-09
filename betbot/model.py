"""Probability models. A model turns a market's runners into win probabilities.

The market-implied model has no edge by design: it is the baseline that any
real model must beat in the backtest before it is trusted with money.
"""
import csv
from typing import Dict, Mapping, Protocol


class ProbabilityModel(Protocol):
    def predict(self, market_id: str, prices: Mapping[str, float]) -> Dict[str, float]:
        """prices: selection_id -> best back price. Returns selection_id -> probability."""
        ...


def _normalise(raw: Dict[str, float]) -> Dict[str, float]:
    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()} if total > 0 else {}


class MarketImpliedModel:
    """Probabilities from the market's own prices, with the overround removed."""

    def predict(self, market_id, prices):
        return _normalise({sid: 1.0 / p for sid, p in prices.items() if p and p > 1.0})


class RatingsModel:
    """Probabilities from a ratings file of rated prices.

    CSV columns: market_id, selection_id, rated_price (for example the free
    Betfair Hub ratings for Australian racing, or your own model's output).
    Runners without a rating are skipped.
    """

    def __init__(self, path: str):
        self.rated: Dict[str, Dict[str, float]] = {}
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                price = float(row["rated_price"])
                if price > 1.0:
                    self.rated.setdefault(str(row["market_id"]), {})[str(row["selection_id"])] = price

    def predict(self, market_id, prices):
        rated = self.rated.get(str(market_id), {})
        return _normalise({sid: 1.0 / rp for sid, rp in rated.items()})


class ColumnModel:
    """Probabilities supplied directly in backtest data (column model_prob)."""

    def __init__(self, probs: Dict[str, Dict[str, float]]):
        self.probs = probs

    def predict(self, market_id, prices):
        return dict(self.probs.get(str(market_id), {}))
