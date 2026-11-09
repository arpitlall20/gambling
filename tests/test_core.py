import datetime as dt
from types import SimpleNamespace as NS

import pytest

from betbot.backtest import Market, run_backtest
from betbot.broker import Journal, PaperBroker
from betbot.model import ColumnModel, MarketImpliedModel
from betbot.risk import RiskLimits, RiskManager
from betbot.runner import run
from betbot.strategy import ValueStrategy
from betbot.value import expected_value, kelly_fraction

D = dt.date(2026, 1, 1)


def test_expected_value_and_kelly():
    assert expected_value(0.5, 2.0, 0.0) == pytest.approx(0.0)
    assert expected_value(0.5, 2.0, 0.1) == pytest.approx(-0.05)
    assert expected_value(0.6, 2.0, 0.0) == pytest.approx(0.2)
    assert kelly_fraction(0.6, 2.0, 0.0) == pytest.approx(0.2)
    assert kelly_fraction(0.4, 2.0, 0.0) == 0.0


def test_market_implied_model_never_bets():
    s = ValueStrategy(MarketImpliedModel(), commission=0.05, min_edge=0.0)
    assert s.decide("m", {"a": 2.1, "b": 2.1, "c": 10.0}, 1000) == []


def test_strategy_picks_value_runner():
    model = ColumnModel({"m": {"a": 0.6, "b": 0.4}})
    bets = ValueStrategy(model, commission=0.05, min_edge=0.05).decide("m", {"a": 2.2, "b": 2.0}, 1000)
    assert [b.selection_id for b in bets] == ["a"]
    assert bets[0].stake > 0


def test_risk_caps_stake_and_halts_on_daily_loss(tmp_path):
    r = RiskManager(RiskLimits(max_stake_per_bet=10, max_daily_loss=15, max_open_exposure=100,
                               kill_switch_path=str(tmp_path / "STOP")))
    assert r.approve(50, D) == (10, "ok")
    r.record_bet(10); r.record_settlement(10, -10)
    assert r.approve(50, D) == (5, "ok")  # only $5 of loss budget left
    r.record_bet(5); r.record_settlement(5, -5)
    assert r.approve(5, D)[0] == 0
    assert r.approve(5, D + dt.timedelta(days=1)) == (5, "ok")  # resets next day


def test_kill_switch(tmp_path):
    stop = tmp_path / "STOP"
    r = RiskManager(RiskLimits(kill_switch_path=str(stop)))
    stop.write_text("")
    assert r.approve(5, D) == (0.0, "kill switch file present")


def test_backtest_applies_commission(tmp_path):
    m = Market("m", D, {"a": 3.0, "b": 1.5}, {"a"}, {"a": 0.5, "b": 0.5})
    s = ValueStrategy(ColumnModel({"m": m.model_probs}), commission=0.1, min_edge=0.0, kelly_multiplier=1.0)
    risk = RiskManager(RiskLimits(max_stake_per_bet=10, kill_switch_path=str(tmp_path / "STOP")))
    res = run_backtest([m], s, risk, bankroll=1000)
    assert res.bets == 1 and res.turnover == 10
    assert res.pnl == pytest.approx(18.0)  # 20 gross winnings less 10% commission


class FakeBetting:
    def __init__(self):
        self.closed = False

    def list_market_catalogue(self, **kw):
        return [NS(market_id="1.1")]

    def list_market_book(self, market_ids, **kw):
        runners = [NS(selection_id=11, status="WINNER" if self.closed else "ACTIVE",
                      ex=NS(available_to_back=[NS(price=3.0, size=100)])),
                   NS(selection_id=22, status="LOSER" if self.closed else "ACTIVE",
                      ex=NS(available_to_back=[NS(price=1.5, size=100)]))]
        return [NS(market_id="1.1", status="CLOSED" if self.closed else "OPEN", inplay=False, runners=runners)]

    def place_orders(self, **kw):
        raise AssertionError("paper mode must never place real orders")


def test_paper_run_places_and_settles(tmp_path):
    client = NS(betting=FakeBetting())
    s = ValueStrategy(ColumnModel({"1.1": {"11": 0.5, "22": 0.5}}), commission=0.1, min_edge=0.0)
    risk = RiskManager(RiskLimits(max_stake_per_bet=10, kill_switch_path=str(tmp_path / "STOP")))
    broker = PaperBroker()
    journal = Journal(str(tmp_path / "j.csv"), "paper")
    run(client, s, risk, broker, journal, 1000, once=True)
    assert len(broker.open) == 1
    client.betting.closed = True
    run(client, s, risk, broker, journal, 1000, once=True)
    assert broker.open == {}
    text = (tmp_path / "j.csv").read_text()
    assert "placed" in text and "settled" in text and "18.0" in text


def test_live_is_locked_without_confirmation(monkeypatch):
    from betbot.cli import main
    monkeypatch.delenv("BETBOT_LIVE_CONFIRM", raising=False)
    with pytest.raises(SystemExit) as e:
        main(["live", "--ratings", "x.csv"])
    assert "locked" in str(e.value)
