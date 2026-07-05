import io
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import tick_options_ledger  # noqa: E402


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def test_main_posts_to_the_tick_endpoint_with_configured_style_and_dte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float | None = None) -> _FakeResponse:
        captured["url"] = request.full_url  # type: ignore[attr-defined]
        captured["method"] = request.method  # type: ignore[attr-defined]
        return _FakeResponse(b'{"open_positions": []}')

    monkeypatch.setenv("AI_QUANT_BACKEND_URL", "https://example.test/api/v1")
    monkeypatch.setenv("AI_QUANT_LEDGER_TICK_STYLE", "weekly")
    monkeypatch.setenv("AI_QUANT_LEDGER_TICK_MAX_DTE", "5")
    monkeypatch.setattr(tick_options_ledger.urllib.request, "urlopen", fake_urlopen)

    exit_code = tick_options_ledger.main()

    assert exit_code == 0
    assert captured["method"] == "POST"
    assert captured["url"] == (
        "https://example.test/api/v1/options-portfolio/paper-ledger/tick"
        "?style=weekly&max_dte=5"
    )


def test_main_returns_nonzero_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: object, timeout: float | None = None) -> _FakeResponse:
        raise HTTPError(
            "https://example.test",
            500,
            "Internal Server Error",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(b"boom"),
        )

    monkeypatch.setenv("AI_QUANT_BACKEND_URL", "https://example.test/api/v1")
    monkeypatch.setattr(tick_options_ledger.urllib.request, "urlopen", fake_urlopen)

    assert tick_options_ledger.main() == 1
