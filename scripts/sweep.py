"""Train/test sweep of the value strategy on converted data.

Picks settings on the earlier period only, then reports them on the later period,
so the result isn't flattered by tuning on the same data it is judged on.

    python scripts/sweep.py kash_all.csv --split 2025-01-01 --commission 0.08
"""
import argparse
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from betbot.backtest import load_markets, run_backtest  # noqa: E402
from betbot.model import ColumnModel  # noqa: E402
from betbot.risk import RiskLimits, RiskManager  # noqa: E402
from betbot.strategy import ValueStrategy  # noqa: E402

NO_LIMITS = RiskLimits(max_stake_per_bet=1e9, max_daily_loss=1e12, max_open_exposure=1e12,
                       max_bets_per_day=10**9, min_stake=0.0, kill_switch_path="")


def run(markets, model, commission, edge, lo, hi, stake=10.0):
    s = ValueStrategy(model, commission=commission, min_edge=edge, min_odds=lo, max_odds=hi, flat_stake=stake)
    return run_backtest(markets, s, RiskManager(NO_LIMITS), bankroll=0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--split", default="2025-01-01")
    ap.add_argument("--commission", type=float, default=0.08)
    a = ap.parse_args()
    markets = load_markets(a.data)
    split = dt.date.fromisoformat(a.split)
    train = [m for m in markets if m.date < split]
    test = [m for m in markets if m.date >= split]
    model = ColumnModel({m.market_id: m.model_probs for m in markets})
    print(f"{len(train)} train markets, {len(test)} test markets, commission {a.commission:.0%}, $10 flat stakes\n")
    print(f"{'min edge':>8} {'odds':>9} | {'train bets':>10} {'ROI':>8} {'z':>6} | {'test bets':>9} {'ROI':>8} {'z':>6} {'P/L':>10}")
    rows = []
    for lo, hi in [(1.01, 1000), (1.5, 15), (2, 8), (8, 50)]:
        for edge in [0.0, 0.05, 0.1, 0.2, 0.3, 0.5]:
            tr, te = run(train, model, a.commission, edge, lo, hi), run(test, model, a.commission, edge, lo, hi)
            rows.append((tr.roi, edge, lo, hi, tr, te))
            print(f"{edge:>8.2f} {lo:>4}-{hi:<4} | {tr.bets:>10} {tr.roi:>+8.2%} {tr.z_score:>+6.2f} | "
                  f"{te.bets:>9} {te.roi:>+8.2%} {te.z_score:>+6.2f} {te.pnl:>+10.0f}")
    best = max((r for r in rows if r[4].bets >= 500), key=lambda r: r[0])
    _, edge, lo, hi, tr, te = best
    print(f"\nBest on train (500+ bets): min edge {edge}, odds {lo}-{hi}: train ROI {tr.roi:+.2%}")
    print(f"Same settings on unseen test period: {te.bets} bets, ROI {te.roi:+.2%}, z {te.z_score:+.2f}, P/L ${te.pnl:+,.0f}")


if __name__ == "__main__":
    main()
