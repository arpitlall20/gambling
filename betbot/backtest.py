"""Replay historical markets through the strategy and risk limits, settling after commission.

Input CSV columns (one row per runner):
    market_id, event_date (YYYY-MM-DD), selection_id, back_price, won (1/0)
    optional: model_prob (used with --model column)
Markets are replayed in event_date order. back_price should be the price you could
realistically have taken (for example the best back price a few minutes before the off),
not the starting price after the fact.
"""
import csv
import datetime as dt
import math
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List

from .risk import RiskManager
from .strategy import ValueStrategy


@dataclass
class Market:
    market_id: str
    date: dt.date
    prices: Dict[str, float] = field(default_factory=dict)
    winners: set = field(default_factory=set)
    model_probs: Dict[str, float] = field(default_factory=dict)


def load_markets(path: str) -> List[Market]:
    markets: "OrderedDict[str, Market]" = OrderedDict()
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            mid = str(row["market_id"])
            m = markets.get(mid)
            if m is None:
                m = markets[mid] = Market(mid, dt.date.fromisoformat(row["event_date"][:10]))
            sid = str(row["selection_id"])
            price = float(row["back_price"] or 0)
            if price > 1.0:
                m.prices[sid] = price
            if str(row.get("won", "0")).strip() in ("1", "true", "True", "WINNER"):
                m.winners.add(sid)
            if row.get("model_prob"):
                m.model_probs[sid] = float(row["model_prob"])
    return sorted(markets.values(), key=lambda m: m.date)


@dataclass
class BacktestResult:
    bets: int = 0
    wins: int = 0
    turnover: float = 0.0
    pnl: float = 0.0
    commission_paid: float = 0.0
    max_drawdown: float = 0.0
    final_bankroll: float = 0.0
    refused: Dict[str, int] = field(default_factory=dict)
    returns: List[float] = field(default_factory=list)  # profit per $1 for each bet

    @property
    def roi(self) -> float:
        return self.pnl / self.turnover if self.turnover else 0.0

    @property
    def z_score(self) -> float:
        n = len(self.returns)
        if n < 2:
            return 0.0
        mean = sum(self.returns) / n
        var = sum((r - mean) ** 2 for r in self.returns) / (n - 1)
        return mean / math.sqrt(var / n) if var > 0 else 0.0

    def summary(self) -> str:
        lines = [
            f"Bets placed:        {self.bets}",
            f"Win rate:           {self.wins / self.bets:.1%}" if self.bets else "Win rate:           n/a",
            f"Turnover:           ${self.turnover:,.2f}",
            f"Commission paid:    ${self.commission_paid:,.2f}",
            f"Profit/loss:        ${self.pnl:,.2f}",
            f"ROI on turnover:    {self.roi:+.2%}",
            f"Max drawdown:       ${self.max_drawdown:,.2f}",
            f"Final bankroll:     ${self.final_bankroll:,.2f}",
            f"Edge z-score:       {self.z_score:+.2f}  (below ~2 means the result could easily be luck)",
        ]
        if self.refused:
            lines.append("Bets refused by risk limits: " + ", ".join(f"{k}: {v}" for k, v in self.refused.items()))
        return "\n".join(lines)


def run_backtest(markets: List[Market], strategy: ValueStrategy, risk: RiskManager,
                 bankroll: float) -> BacktestResult:
    res = BacktestResult()
    peak = bankroll
    for m in markets:
        if not m.prices:
            continue
        intents = strategy.decide(m.market_id, m.prices, bankroll)
        market_net, placed = 0.0, []
        for b in intents:
            stake, reason = risk.approve(b.stake, m.date)
            if stake <= 0:
                res.refused[reason] = res.refused.get(reason, 0) + 1
                continue
            risk.record_bet(stake)
            won = b.selection_id in m.winners
            gross = stake * (b.price - 1.0) if won else -stake
            market_net += gross
            placed.append((stake, gross, won))
        if not placed:
            continue
        # Betfair charges commission on net winnings per market.
        commission = market_net * strategy.commission if market_net > 0 else 0.0
        for stake, gross, won in placed:
            share = commission * (gross / market_net) if market_net > 0 and gross > 0 else 0.0
            net = gross - share
            risk.record_settlement(stake, net)
            res.bets += 1
            res.wins += int(won)
            res.turnover += stake
            res.returns.append(net / stake)
        res.commission_paid += commission
        res.pnl += market_net - commission
        bankroll += market_net - commission
        peak = max(peak, bankroll)
        res.max_drawdown = max(res.max_drawdown, peak - bankroll)
    res.final_bankroll = bankroll
    return res
