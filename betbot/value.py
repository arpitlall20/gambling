"""Expected value and staking maths for back bets on an exchange."""


def implied_probability(odds: float) -> float:
    return 1.0 / odds


def expected_value(p: float, odds: float, commission: float) -> float:
    """Expected profit per $1 staked on a back bet, after commission on winnings."""
    win_profit = (odds - 1.0) * (1.0 - commission)
    return p * win_profit - (1.0 - p)


def kelly_fraction(p: float, odds: float, commission: float) -> float:
    """Full-Kelly fraction of bankroll for a back bet. Never negative."""
    b = (odds - 1.0) * (1.0 - commission)
    if b <= 0:
        return 0.0
    return max(0.0, (p * b - (1.0 - p)) / b)


def round_stake(stake: float) -> float:
    """Betfair stakes are in cents."""
    return round(stake + 1e-9, 2)
