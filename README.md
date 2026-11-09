# betbot: Betfair Exchange value-betting bot

Backs Australian horse racing WIN markets on the Betfair Exchange only when a model
says the price is better than fair, after commission. It runs in three stages, and
each stage has to show an edge before you move to the next:

1. **Backtest** on historical data.
2. **Paper trade** live markets with no real money, for a few weeks.
3. **Live**, with hard limits. Locked by default.

> Betting is risky. Most models do not beat the market after commission. The
> market-implied baseline model never bets, because it has no edge by design.
> Only bet money you can afford to lose. Help: Gambling Help Online, 1800 858 858.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

## 1. Backtest

Try it on synthetic data first (this only shows how the tool works, not real results):

```bash
python -m betbot sample --out sample.csv --skill 0.8
python -m betbot backtest sample.csv --model column
```

For real testing, build a CSV from Betfair's historical data
(https://historicdata.betfair.com and the Betfair Data Scientists hub), with one row per runner:

| column | meaning |
|---|---|
| market_id | Betfair market id |
| event_date | YYYY-MM-DD |
| selection_id | runner id |
| back_price | best back price you could have taken shortly before the off |
| won | 1 if the runner won |
| model_prob | optional, your model's win probability |

Or pass `--model ratings --ratings ratings.csv` with columns `market_id, selection_id, rated_price`.

Read the **edge z-score**. Below about 2, the profit or loss could easily be luck.

## 2. Paper trade

1. Get an app key (the free delayed key is fine for paper trading):
   https://betfair-datascientists.github.io/api/apiappkey/
2. Create a self-signed certificate for non-interactive login and upload it to your
   Betfair account (Betfair docs: "Non-Interactive (bot) login"). Put `client-2048.crt`
   and `client-2048.key` in `certs/`.
3. Copy `.env.example` to `.env` and fill it in on your own machine. Never share it.

```bash
set -a; source .env; set +a
python -m betbot paper --ratings todays_ratings.csv --bankroll 500
```

Every decision is logged to `paper_journal.csv`. Paper fills assume you got the best
back price shown, so real results will be a little worse.

## 3. Live (locked)

Live needs `BETBOT_LIVE_CONFIRM=yes-real-money` in the environment and a live app key.
Bets are LIMIT BACK orders that lapse at the off, so nothing runs in-play.

## Risk limits (all flags on backtest, paper and live)

| flag | default |
|---|---|
| `--max-stake` | $10 per bet |
| `--max-daily-loss` | $50, then betting stops until tomorrow |
| `--max-exposure` | $100 unsettled at once |
| `--max-bets-per-day` | 50 |
| `--kelly` | 0.25 (quarter Kelly staking) |
| `--min-edge` | 0.05 (5c expected profit per $1) |
| `--commission` | 0.08, set to your actual Betfair rate |

**Kill switch:** create a file called `STOP` in the working directory (`touch STOP`)
and the bot refuses every new bet.

## Layout

- `betbot/value.py` has the expected-value and Kelly maths.
- `betbot/model.py` has the probability models: market-implied baseline, ratings file, and a data column.
- `betbot/strategy.py` picks value bets.
- `betbot/risk.py` holds the hard limits and the kill switch.
- `betbot/backtest.py` replays history with per-market commission.
- `betbot/broker.py` has the paper broker, the live Betfair broker and the CSV journal.
- `betbot/runner.py` runs the paper/live loop over AU horse racing WIN markets.
