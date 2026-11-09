"""Synthetic race data for trying the backtester. NOT real data: results here prove nothing
about real markets. Use Betfair's historical data for real testing."""
import csv
import datetime as dt
import random


def generate(path: str, n_markets: int = 3000, model_skill: float = 0.0,
             overround: float = 1.02, seed: int = 1) -> None:
    """model_skill 0 = model is pure noise around the market; 1 = model knows the true odds."""
    rng = random.Random(seed)
    start = dt.date(2025, 1, 1)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["market_id", "event_date", "selection_id", "back_price", "won", "model_prob"])
        for i in range(n_markets):
            n = rng.randint(6, 12)
            strength = [rng.lognormvariate(0, 0.8) for _ in range(n)]
            true_p = [s / sum(strength) for s in strength]
            # market is a noisy view of the truth, plus the overround
            mkt_raw = [p * rng.lognormvariate(0, 0.15) for p in true_p]
            mkt_p = [p / sum(mkt_raw) * overround for p in mkt_raw]
            # model blends truth and market with its own noise
            mod_raw = [(model_skill * tp + (1 - model_skill) * mp / overround) * rng.lognormvariate(0, 0.05)
                       for tp, mp in zip(true_p, mkt_p)]
            mod_p = [p / sum(mod_raw) for p in mod_raw]
            winner = rng.choices(range(n), weights=true_p)[0]
            date = start + dt.timedelta(days=i // 10)
            for j in range(n):
                price = max(1.01, round(1.0 / mkt_p[j], 2))
                w.writerow([f"1.{100000 + i}", date.isoformat(), 1000 + j, price,
                            int(j == winner), round(mod_p[j], 5)])
