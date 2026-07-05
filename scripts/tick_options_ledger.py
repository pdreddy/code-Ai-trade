#!/usr/bin/env python3
"""Auto-trade cron entrypoint: ticks the live options paper ledger.

Intended to run on a schedule (see render.yaml's ai-quant-ledger-tick cron
service) against the already-running backend web service, calling the exact
same endpoint a manual "Run ledger tick" click in the UI would. This settles
matured/delisted positions and opens new ones from live signals — real quoted
prices, no modeling, no real broker, no real money. It reuses the backend's
in-memory ledger state, so it only works correctly against the same running
process the UI talks to (see options_forward_ledger.py for why).
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

DEFAULT_BACKEND_URL = "http://localhost:8000/api/v1"
DEFAULT_STYLE = "zero_dte"
DEFAULT_MAX_DTE = "8"
TIMEOUT_SECONDS = 90


def main() -> int:
    base_url = os.environ.get("AI_QUANT_BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")
    style = os.environ.get("AI_QUANT_LEDGER_TICK_STYLE", DEFAULT_STYLE)
    max_dte = os.environ.get("AI_QUANT_LEDGER_TICK_MAX_DTE", DEFAULT_MAX_DTE)
    url = f"{base_url}/options-portfolio/paper-ledger/tick?style={style}&max_dte={max_dte}"

    request = urllib.request.Request(url, method="POST")  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            body = response.read().decode("utf-8")
            print(f"Ledger tick OK: HTTP {response.status}")
            print(body[:4000])
            return 0
    except urllib.error.HTTPError as exc:
        print(f"Ledger tick failed: HTTP {exc.code} {exc.reason}", file=sys.stderr)
        print(exc.read().decode("utf-8", errors="replace")[:2000], file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Ledger tick failed: {exc.reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
