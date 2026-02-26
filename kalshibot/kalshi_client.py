"""
Thin wrapper around the Kalshi REST API v2.
Docs: https://trading-api.kalshi.co/trade-api/v2/docs
"""

import os
import base64
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

PROD_BASE = "https://api.elections.kalshi.com/trade-api/v2"
DEMO_BASE = "https://demo-api.kalshi.co/trade-api/v2"


def _sign_request(method: str, path: str, body: str, key_id: str, private_key_pem: str) -> dict[str, str]:
    """Build Kalshi HMAC-style RSA signature headers."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        raise ImportError(
            "Install 'cryptography' to use RSA-signed requests: pip install cryptography"
        )

    ts_ms = str(int(time.time() * 1000))
    msg = ts_ms + method.upper() + path + body
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode(), password=None, backend=default_backend()
    )
    signature = private_key.sign(msg.encode(), padding.PKCS1v15(), hashes.SHA256())
    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": ts_ms,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
    }


class KalshiClient:
    def __init__(self, api_key_id: Optional[str] = None, api_key_rsa: Optional[str] = None, env: str = "prod"):
        self.base_url = PROD_BASE if env == "prod" else DEMO_BASE
        self.api_key_id = api_key_id or os.environ["KALSHI_API_KEY_ID"]

        rsa_env = api_key_rsa or os.environ.get("KALSHI_API_KEY_RSA", "")
        if os.path.isfile(rsa_env):
            with open(rsa_env) as f:
                self.private_key_pem = f.read()
        else:
            self.private_key_pem = rsa_env

        self._client = httpx.Client(timeout=30)

    def _headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key_id and self.private_key_pem:
            headers.update(_sign_request(method, path, body, self.api_key_id, self.private_key_pem))
        return headers

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        url = self.base_url + path
        r = self._client.get(url, headers=self._headers("GET", path), params=params)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Markets
    # ------------------------------------------------------------------

    def get_markets(
        self,
        status: str = "open",
        limit: int = 1000,
        cursor: Optional[str] = None,
        max_close_ts: Optional[int] = None,
    ) -> dict:
        params: dict = {"status": status, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        if max_close_ts is not None:
            params["max_close_ts"] = max_close_ts
        return self._get("/markets", params=params)

    def iter_markets(self, status: str = "open", max_markets: int = 10000, max_close_ts: Optional[int] = None) -> list[dict]:
        """Page through all markets and return a flat list, capped at max_markets."""
        markets: list[dict] = []
        cursor = None
        page_num = 0
        while True:
            page = self.get_markets(status=status, cursor=cursor, max_close_ts=max_close_ts)
            markets.extend(page.get("markets", []))
            page_num += 1
            cursor = page.get("cursor")
            print(f"  page {page_num} — {len(markets)} markets fetched...", end="\r", flush=True)
            if not cursor or len(markets) >= max_markets:
                break
            time.sleep(0.5)
        print()  # newline after the \r updates
        return markets[:max_markets]

    def get_market(self, ticker: str) -> dict:
        return self._get(f"/markets/{ticker}")

    def get_orderbook(self, ticker: str, depth: int = 10) -> dict:
        return self._get(f"/markets/{ticker}/orderbook", params={"depth": depth})
