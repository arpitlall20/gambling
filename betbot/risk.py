"""Hard risk limits. Every bet goes through RiskManager.approve before it is placed."""
import datetime as dt
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class RiskLimits:
    max_stake_per_bet: float = 10.0
    max_daily_loss: float = 50.0
    max_open_exposure: float = 100.0
    max_bets_per_day: int = 50
    min_stake: float = 1.0
    kill_switch_path: str = "STOP"  # create this file to halt all betting


@dataclass
class RiskManager:
    limits: RiskLimits
    open_exposure: float = 0.0
    day: Optional[dt.date] = None
    day_pnl: float = 0.0
    day_bets: int = 0
    halted_reason: Optional[str] = field(default=None)

    def _roll_day(self, today: dt.date) -> None:
        if self.day != today:
            self.day, self.day_pnl, self.day_bets = today, 0.0, 0
            if self.halted_reason == "daily loss limit reached":
                self.halted_reason = None

    def approve(self, stake: float, today: dt.date) -> Tuple[float, str]:
        """Return (allowed_stake, reason). allowed_stake is 0 when the bet is refused."""
        self._roll_day(today)
        lim = self.limits
        if lim.kill_switch_path and os.path.exists(lim.kill_switch_path):
            return 0.0, "kill switch file present"
        if self.halted_reason:
            return 0.0, self.halted_reason
        if self.day_bets >= lim.max_bets_per_day:
            return 0.0, "daily bet count limit reached"
        if -self.day_pnl >= lim.max_daily_loss:
            self.halted_reason = "daily loss limit reached"
            return 0.0, self.halted_reason
        stake = min(stake, lim.max_stake_per_bet, lim.max_open_exposure - self.open_exposure,
                    lim.max_daily_loss + self.day_pnl - self.open_exposure)
        stake = round(stake, 2)
        if stake < lim.min_stake:
            return 0.0, "stake below minimum after limits"
        return stake, "ok"

    def record_bet(self, stake: float) -> None:
        self.open_exposure += stake
        self.day_bets += 1

    def record_settlement(self, stake: float, pnl: float) -> None:
        self.open_exposure = max(0.0, self.open_exposure - stake)
        self.day_pnl += pnl
