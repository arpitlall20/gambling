"""Convert Betfair Data Scientists 'Kash' model results CSVs into betbot backtest format.

Download the monthly/yearly files from https://betfair-datascientists.github.io/data/dataListing/
(Aus & NZ Thoroughbred Predictions Model results), then:

    python scripts/convert_kash.py out.csv Kash_Model_Results_2025.csv ...

Price used is WIN_BSP (Betfair Starting Price). In live trading you can only get BSP
if it beats your minimum by placing a LIMIT_ON_CLOSE order, which is what this mimics.
model_prob is the model's rated price (RP) turned into a probability and normalised
over the runners that started.
"""
import csv
import datetime as dt
import sys
from collections import OrderedDict


def parse_date(text):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text.strip()[:10], fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date {text!r}")


def convert(out_path, in_paths):
    markets = OrderedDict()
    for path in in_paths:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                try:
                    bsp, rp = float(r["WIN_BSP"] or 0), float(r["RP"] or 0)
                except ValueError:
                    continue
                if bsp <= 1.0 or rp <= 1.0:
                    continue  # scratched or unrated
                date = parse_date(r["Date"])
                markets.setdefault(r["Market"], []).append((date, r["Selection"], bsp, int(float(r["WIN_RESULT"] or 0)), 1 / rp))
    n = 0
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["market_id", "event_date", "selection_id", "back_price", "won", "model_prob"])
        for mid, runners in markets.items():
            total = sum(r[4] for r in runners)
            if sum(r[3] for r in runners) != 1:
                continue  # skip dead heats / abandoned races
            for date, sid, bsp, won, raw in runners:
                w.writerow([mid, date, sid, bsp, won, round(raw / total, 6)])
            n += 1
    print(f"Wrote {n} markets to {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    convert(sys.argv[1], sys.argv[2:])
