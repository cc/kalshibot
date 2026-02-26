# kalshibot

Daily scanner for undervalued Kalshi markets. Flags open markets with low liquidity and price anomalies as potential betting opportunities.

## How it works

Each run fetches all open Kalshi markets and scores them on a composite anomaly score (0–1) based on:

| Signal | Weight | What it means |
|---|---|---|
| **Wide bid/ask spread** | 40% | Market maker has little conviction; price is uncertain |
| **Low liquidity** | 35% | Thin 24h volume + open interest; easier to move the price |
| **Price skew** | 25% | `yes_bid + no_ask ≠ 100` — internal inconsistency between yes/no books |

Markets above the score threshold (default: 0.5) are printed to a rich table and saved as a JSON report in `output/scan_YYYY-MM-DD.json`.

## Setup

```bash
git clone git@github.com:cc/kalshibot.git
cd kalshibot
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # or: pip install httpx python-dotenv rich cryptography
cp .env.example .env
# fill in your Kalshi API credentials in .env
```

## Kalshi API credentials

1. Go to [kalshi.com/account/api](https://kalshi.com/account/api)
2. Generate an RSA key pair
3. Upload the public key to Kalshi
4. Set `KALSHI_API_KEY_ID` and `KALSHI_API_KEY_RSA` (path to `.pem` file) in `.env`

## Run manually

```bash
python -m kalshibot
```

## Run daily via cron

```bash
# edit crontab
crontab -e

# add this line to run at 8am UTC every day
0 8 * * * /path/to/kalshibot/scripts/daily_scan.sh >> /path/to/kalshibot/output/cron.log 2>&1
```

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `KALSHI_API_KEY_ID` | — | Your Kalshi API key ID |
| `KALSHI_API_KEY_RSA` | — | Path to RSA private key `.pem`, or key content |
| `KALSHI_ENV` | `prod` | `prod` or `demo` |
| `MIN_ANOMALY_SCORE` | `0.5` | Minimum composite score to flag (0–1) |
| `MAX_VOLUME_THRESHOLD` | `500` | 24h volume ceiling for "low liquidity" |
| `MIN_SPREAD_THRESHOLD` | `10` | Minimum bid/ask spread in cents to always flag |
| `OUTPUT_DIR` | `./output` | Directory for JSON scan reports |

## Project layout

```
kalshibot/
├── kalshibot/
│   ├── kalshi_client.py   # Kalshi REST API v2 wrapper
│   ├── analyzer.py        # Anomaly scoring logic
│   ├── reporter.py        # Rich table + JSON output
│   └── cli.py             # Entry point (python -m kalshibot)
├── scripts/
│   └── daily_scan.sh      # Cron-friendly shell wrapper
├── output/                # Scan reports (gitignored)
├── .env.example
└── pyproject.toml
```
