"""Paper or live loop over upcoming Australian thoroughbred WIN markets on Betfair."""
import datetime as dt
import time
from typing import Set

from .broker import Journal
from .risk import RiskManager
from .strategy import ValueStrategy

HORSE_RACING = "7"


def connect(creds):
    import betfairlightweight
    client = betfairlightweight.APIClient(creds.username, creds.password, app_key=creds.app_key,
                                          certs=creds.certs_dir, locale="australia")
    client.login()  # certificate login, see README
    return client


def _best_back(runner):
    offers = runner.ex.available_to_back if runner.ex else []
    return (offers[0].price, offers[0].size) if offers else (None, 0.0)


def run(client, strategy: ValueStrategy, risk: RiskManager, broker, journal: Journal,
        bankroll: float, bet_window_minutes: int = 5, poll_seconds: int = 30, once: bool = False) -> None:
    from betfairlightweight import filters
    done: Set[str] = set()
    print(f"Running in {broker.mode.upper()} mode. Create the file '{risk.limits.kill_switch_path}' to stop betting.")
    while True:
        for bet, pnl in broker.settle(client, strategy.commission):
            risk.record_settlement(bet.stake, pnl)
            bankroll += pnl
            journal.write("settled", bet_ref=bet.bet_ref, market_id=bet.market_id,
                          selection_id=bet.selection_id, price=bet.price, stake=bet.stake, pnl=pnl)
            print(f"Settled {bet.bet_ref}: {pnl:+.2f}  bankroll {bankroll:.2f}")

        now = dt.datetime.now(dt.timezone.utc)
        catalogues = client.betting.list_market_catalogue(
            filter=filters.market_filter(
                event_type_ids=[HORSE_RACING], market_countries=["AU"], market_type_codes=["WIN"],
                market_start_time={"from": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                   "to": (now + dt.timedelta(minutes=bet_window_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")}),
            market_projection=["MARKET_START_TIME", "EVENT"], max_results=50)
        market_ids = [c.market_id for c in catalogues if c.market_id not in done]

        if market_ids:
            books = client.betting.list_market_book(
                market_ids=market_ids, price_projection=filters.price_projection(price_data=["EX_BEST_OFFERS"]))
            for book in books:
                if book.status != "OPEN" or book.inplay:
                    continue
                done.add(book.market_id)
                quotes = {str(r.selection_id): _best_back(r) for r in book.runners if r.status == "ACTIVE"}
                prices = {sid: q[0] for sid, q in quotes.items() if q[0]}
                for intent in strategy.decide(book.market_id, prices, bankroll):
                    stake, reason = risk.approve(intent.stake, dt.date.today())
                    common = dict(market_id=intent.market_id, selection_id=intent.selection_id, price=intent.price,
                                  model_prob=round(intent.model_prob, 4), ev_per_dollar=round(intent.ev_per_dollar, 4))
                    if stake <= 0:
                        journal.write("refused", stake=intent.stake, note=reason, **common)
                        continue
                    bet = broker.place(intent, stake, quotes[intent.selection_id][1])
                    if bet is None:
                        journal.write("not_filled", stake=stake, **common)
                        continue
                    risk.record_bet(stake)
                    journal.write("placed", bet_ref=bet.bet_ref, stake=stake, **common)
                    print(f"Placed {bet.bet_ref}: ${stake:.2f} @ {intent.price} on {intent.selection_id} "
                          f"in {intent.market_id} (EV {intent.ev_per_dollar:+.3f}/$)")
        if once:
            return
        time.sleep(poll_seconds)
