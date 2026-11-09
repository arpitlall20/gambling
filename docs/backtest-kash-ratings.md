# Backtest: Betfair "Kash" thoroughbred ratings (Jan 2024 to Oct 2026)

**Verdict: no edge. Do not paper trade or go live with this model.**

## Data

- Betfair Data Scientists' public Kash model results for Australian and NZ thoroughbreds,
  covering 2024, 2025 and Jan–Oct 2026. Each runner has the model's rated price (RP),
  the Betfair Starting Price (BSP) and the result.
- After removing scratchings, unrated runners and dead heats, this leaves 51,840 races.
- Bets are assumed to be taken at BSP. Live, you'd get that with a LIMIT_ON_CLOSE order.
- Commission is 8% on net market winnings, unless a test says otherwise.
- Settings were tuned on 2024 (18,520 races). They were then judged on Jan 2025–Oct 2026
  (33,320 races), which the tuning never saw.

Reproduce:

```bash
python scripts/convert_kash.py kash_all.csv Kash_Model_Results_2024.csv Kash_Model_Results_2025.csv Kash_Model_Results_2026_*.csv
python scripts/sweep.py kash_all.csv --split 2025-01-01 --commission 0.08
```

## Results

**1. The market beats the model.** On log loss (lower is better), BSP prices score 0.2717
and the model scores 0.2793. A model that combines the two, fitted on 2024, puts about
1.0 weight on the market and 0.006 on the model. So the model adds essentially nothing
the closing price doesn't already know.

**2. Value betting against BSP loses.** With $10 flat stakes and one bet per race, the best
2024 setting was a minimum edge of 20% at odds 2–8 (-2.6% ROI on 2024). On the unseen
2025–26 period it lost **-11.0%** (7,293 bets, -$8,006, z = -4.6). Every combination in the
sweep lost money on the test period, from -9% to -14% ROI.

**3. The bot's default Kelly settings would have nearly wiped out a $500 bankroll.**
Running the default bot (quarter Kelly, 5% minimum edge, $10 cap, $50 daily stop) on 2025–26
placed 671 bets and lost $487 (-32% ROI). Kelly staking trusts the model's edge, and here
that edge isn't real. The risk caps limited the damage but couldn't prevent it.

**4. Commission matters.** Backing every runner at BSP lost 2–3% before commission. After
commission, the model's value bets lost about 10%. Even the market-plus-model blend only
reached roughly break-even at 5% commission (+0.2%, 9,351 bets), and it lost at 8%.

## What it would take

- **A model that beats the closing price on log loss.** This is the bar any model has to clear.
- **Earlier prices.** A model may beat early-market prices that later move towards it, even
  when it can't beat BSP. Testing that needs timestamped price history, which means Betfair
  PRO historic stream data. That data is paid; the free CSVs only have prices at the off.
- **Lower commission.** Check your actual Betfair rate, because it decides whether a small
  edge survives.
