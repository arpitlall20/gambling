"""Where bets go. PaperBroker records simulated bets; BetfairBroker places real ones."""
import csv
import datetime as dt
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from .strategy import BetIntent


@dataclass
class OpenBet:
    bet_ref: str
    market_id: str
    selection_id: str
    price: float
    stake: float
    placed_at: str


JOURNAL_FIELDS = ["time", "mode", "event", "bet_ref", "market_id", "selection_id",
                  "price", "stake", "model_prob", "ev_per_dollar", "pnl", "note"]


class Journal:
    """Append-only CSV log of every bet decision, placement and settlement."""

    def __init__(self, path: str, mode: str):
        self.path, self.mode = path, mode
        if not os.path.exists(path):
            with open(path, "w", newline="") as f:
                csv.writer(f).writerow(JOURNAL_FIELDS)

    def write(self, event: str, **kw) -> None:
        row = {"time": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "mode": self.mode, "event": event, **kw}
        with open(self.path, "a", newline="") as f:
            csv.DictWriter(f, JOURNAL_FIELDS, extrasaction="ignore").writerow(row)


class PaperBroker:
    """Simulates a fill at the current best back price if enough money is available there."""
    mode = "paper"

    def __init__(self):
        self.open: Dict[str, OpenBet] = {}
        self._n = 0

    def place(self, intent: BetIntent, stake: float, available_size: float) -> Optional[OpenBet]:
        if available_size < stake:
            return None
        self._n += 1
        bet = OpenBet(f"paper-{self._n}", intent.market_id, intent.selection_id, intent.price, stake,
                      dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
        self.open[bet.bet_ref] = bet
        return bet

    def settle(self, client, commission: float) -> List[tuple]:
        """Settle paper bets whose markets have closed. Returns [(bet, pnl)]."""
        if not self.open:
            return []
        by_market: Dict[str, List[OpenBet]] = {}
        for b in self.open.values():
            by_market.setdefault(b.market_id, []).append(b)
        settled = []
        books = client.betting.list_market_book(market_ids=list(by_market))
        for book in books:
            if book.status != "CLOSED":
                continue
            status = {str(r.selection_id): r.status for r in book.runners}
            for b in by_market.get(book.market_id, []):
                s = status.get(b.selection_id)
                if s == "REMOVED":
                    pnl = 0.0
                else:
                    gross = b.stake * (b.price - 1.0) if s == "WINNER" else -b.stake
                    pnl = gross * (1 - commission) if gross > 0 else gross
                settled.append((b, round(pnl, 2)))
                del self.open[b.bet_ref]
        return settled


class BetfairBroker:
    """Places real BACK limit bets that lapse at the off (no in-play exposure)."""
    mode = "live"

    def __init__(self, client):
        from betfairlightweight import filters
        self.client, self.filters = client, filters
        self.open: Dict[str, OpenBet] = {}

    def place(self, intent: BetIntent, stake: float, available_size: float) -> Optional[OpenBet]:
        f = self.filters
        instruction = f.place_instruction(
            order_type="LIMIT", selection_id=int(intent.selection_id), side="BACK",
            limit_order=f.limit_order(size=stake, price=intent.price, persistence_type="LAPSE"))
        result = self.client.betting.place_orders(market_id=intent.market_id, instructions=[instruction],
                                                  customer_strategy_ref="betbot")
        if result.status != "SUCCESS" or not result.place_instruction_reports:
            return None
        report = result.place_instruction_reports[0]
        bet = OpenBet(str(report.bet_id), intent.market_id, intent.selection_id, intent.price, stake,
                      dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
        self.open[bet.bet_ref] = bet
        return bet

    def settle(self, client, commission: float) -> List[tuple]:
        """Use Betfair's own settled records; unmatched stake that lapsed counts as zero."""
        if not self.open:
            return []
        cleared = client.betting.list_cleared_orders(bet_status="SETTLED", bet_ids=list(self.open))
        settled = []
        for o in cleared.orders:
            b = self.open.pop(str(o.bet_id), None)
            if b is None:
                continue
            profit = o.profit or 0.0
            pnl = profit * (1 - commission) if profit > 0 else profit
            settled.append((b, round(pnl, 2)))
        lapsed = client.betting.list_cleared_orders(bet_status="LAPSED", bet_ids=list(self.open))
        for o in lapsed.orders:
            b = self.open.pop(str(o.bet_id), None)
            if b is not None:
                settled.append((b, 0.0))
        return settled
