"""Value strategy: back a runner only when the model says the price is too generous."""
from dataclasses import dataclass
from typing import List, Mapping

from .model import ProbabilityModel
from .value import expected_value, kelly_fraction, round_stake


@dataclass
class BetIntent:
    market_id: str
    selection_id: str
    price: float
    stake: float
    model_prob: float
    ev_per_dollar: float


@dataclass
class ValueStrategy:
    model: ProbabilityModel
    commission: float = 0.08
    min_edge: float = 0.05        # require at least 5c expected profit per $1
    kelly_multiplier: float = 0.25  # quarter Kelly
    min_odds: float = 1.5
    max_odds: float = 15.0
    max_bets_per_market: int = 1
    flat_stake: float = 0.0       # if set, stake this amount instead of Kelly

    def decide(self, market_id: str, prices: Mapping[str, float], bankroll: float) -> List[BetIntent]:
        probs = self.model.predict(market_id, prices)
        candidates = []
        for sid, price in prices.items():
            p = probs.get(sid)
            if p is None or not price or not (self.min_odds <= price <= self.max_odds):
                continue
            ev = expected_value(p, price, self.commission)
            if ev < self.min_edge:
                continue
            if self.flat_stake:
                stake = self.flat_stake
            else:
                stake = round_stake(bankroll * kelly_fraction(p, price, self.commission) * self.kelly_multiplier)
            if stake > 0:
                candidates.append(BetIntent(market_id, sid, price, stake, p, ev))
        candidates.sort(key=lambda b: b.ev_per_dollar, reverse=True)
        return candidates[: self.max_bets_per_market]
