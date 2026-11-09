"""Settings. Credentials come only from environment variables (or a local .env you never commit)."""
import os
from dataclasses import dataclass

LIVE_CONFIRM_VALUE = "yes-real-money"


@dataclass
class Credentials:
    username: str
    password: str
    app_key: str
    certs_dir: str

    @classmethod
    def from_env(cls) -> "Credentials":
        missing = [k for k in ("BETFAIR_USERNAME", "BETFAIR_PASSWORD", "BETFAIR_APP_KEY") if not os.environ.get(k)]
        if missing:
            raise SystemExit(f"Missing environment variables: {', '.join(missing)}. See README.")
        return cls(os.environ["BETFAIR_USERNAME"], os.environ["BETFAIR_PASSWORD"],
                   os.environ["BETFAIR_APP_KEY"], os.environ.get("BETFAIR_CERTS_DIR", "certs"))


def live_trading_confirmed() -> bool:
    return os.environ.get("BETBOT_LIVE_CONFIRM") == LIVE_CONFIRM_VALUE
