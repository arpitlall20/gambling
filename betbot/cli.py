"""Command line: backtest, sample data, paper trading, and (gated) live trading."""
import argparse
import sys

from .config import LIVE_CONFIRM_VALUE, Credentials, live_trading_confirmed
from .model import ColumnModel, MarketImpliedModel, RatingsModel
from .risk import RiskLimits, RiskManager
from .strategy import ValueStrategy


def _add_strategy_args(p):
    p.add_argument("--bankroll", type=float, default=500.0)
    p.add_argument("--commission", type=float, default=0.08, help="your Betfair commission rate (0.08 = 8%%)")
    p.add_argument("--min-edge", type=float, default=0.05, help="min expected profit per $1 to bet")
    p.add_argument("--kelly", type=float, default=0.25, help="fraction of Kelly stake")
    p.add_argument("--flat-stake", type=float, default=0.0, help="bet this fixed amount instead of Kelly")
    p.add_argument("--min-odds", type=float, default=1.5)
    p.add_argument("--max-odds", type=float, default=15.0)
    p.add_argument("--max-stake", type=float, default=10.0)
    p.add_argument("--max-daily-loss", type=float, default=50.0)
    p.add_argument("--max-exposure", type=float, default=100.0)
    p.add_argument("--max-bets-per-day", type=int, default=50)
    p.add_argument("--min-stake", type=float, default=1.0)
    p.add_argument("--kill-switch", default="STOP")


def _build(args, model):
    strategy = ValueStrategy(model, commission=args.commission, min_edge=args.min_edge,
                             kelly_multiplier=args.kelly, flat_stake=args.flat_stake, min_odds=args.min_odds, max_odds=args.max_odds)
    risk = RiskManager(RiskLimits(args.max_stake, args.max_daily_loss, args.max_exposure,
                                  args.max_bets_per_day, args.min_stake, args.kill_switch))
    return strategy, risk


def cmd_backtest(args):
    from .backtest import load_markets, run_backtest
    markets = load_markets(args.data)
    if args.model == "column":
        model = ColumnModel({m.market_id: m.model_probs for m in markets})
    elif args.model == "ratings":
        if not args.ratings:
            sys.exit("--ratings file is required with --model ratings")
        model = RatingsModel(args.ratings)
    else:
        model = MarketImpliedModel()
    strategy, risk = _build(args, model)
    print(f"Backtest over {len(markets)} markets, model={args.model}\n")
    print(run_backtest(markets, strategy, risk, args.bankroll).summary())


def cmd_sample(args):
    from .sample_data import generate
    generate(args.out, n_markets=args.markets, model_skill=args.skill, seed=args.seed)
    print(f"Wrote synthetic data to {args.out} (not real data)")


def cmd_trade(args, live: bool):
    from .broker import BetfairBroker, Journal, PaperBroker
    from .runner import connect, run
    if live and not live_trading_confirmed():
        sys.exit("Live trading is locked. Only after a successful backtest and paper trading period, set "
                 f"BETBOT_LIVE_CONFIRM={LIVE_CONFIRM_VALUE} in your environment and run 'live' again.")
    if not args.ratings:
        sys.exit("--ratings is required: the market-implied model has no edge, so trading it would just pay commission.")
    model = RatingsModel(args.ratings)
    strategy, risk = _build(args, model)
    client = connect(Credentials.from_env())
    broker = BetfairBroker(client) if live else PaperBroker()
    journal = Journal(args.journal, broker.mode)
    try:
        run(client, strategy, risk, broker, journal, args.bankroll,
            bet_window_minutes=args.window, poll_seconds=args.poll, once=args.once)
    finally:
        client.logout()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="betbot", description="Betfair Exchange value-betting bot")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backtest", help="replay historical data")
    b.add_argument("data")
    b.add_argument("--model", choices=["implied", "column", "ratings"], default="column")
    b.add_argument("--ratings")
    _add_strategy_args(b)

    s = sub.add_parser("sample", help="write synthetic demo data")
    s.add_argument("--out", default="sample_races.csv")
    s.add_argument("--markets", type=int, default=3000)
    s.add_argument("--skill", type=float, default=0.0, help="0 = model has no real edge, 1 = model knows the truth")
    s.add_argument("--seed", type=int, default=1)

    for name in ("paper", "live"):
        t = sub.add_parser(name, help=f"{name} trade upcoming AU horse racing WIN markets")
        t.add_argument("--ratings", help="ratings CSV for today's markets")
        t.add_argument("--journal", default=f"{name}_journal.csv")
        t.add_argument("--window", type=int, default=5, help="bet on markets starting within N minutes")
        t.add_argument("--poll", type=int, default=30)
        t.add_argument("--once", action="store_true")
        _add_strategy_args(t)

    args = ap.parse_args(argv)
    if args.cmd == "backtest":
        cmd_backtest(args)
    elif args.cmd == "sample":
        cmd_sample(args)
    else:
        cmd_trade(args, live=args.cmd == "live")


if __name__ == "__main__":
    main()
