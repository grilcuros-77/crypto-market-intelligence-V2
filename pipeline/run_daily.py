import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "web" / "public" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

COINS = {"bitcoin": "BTC", "ethereum": "ETH", "avalanche-2": "AVAX"}
BASE_URL = "https://api.coingecko.com/api/v3"


def get_json(path, params=None):
    key = os.environ.get("COINGECKO_API_KEY")
    if not key:
        raise RuntimeError("COINGECKO_API_KEY GitHub secret is missing")
    response = requests.get(
        BASE_URL + path,
        params=params,
        headers={"x-cg-demo-api-key": key, "accept": "application/json"},
        timeout=30,
    )
    if response.status_code == 429:
        raise RuntimeError("CoinGecko rate limit (429); retry later")
    response.raise_for_status()
    return response.json()


def sma(values, period):
    return sum(values[-period:]) / period if len(values) >= period else None


def rsi(values, period=14):
    if len(values) <= period:
        return None
    gains, losses = [], []
    for i in range(1, period + 1):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period + 1, len(values)):
        change = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0)) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def market_snapshot(coin_id, symbol, spot):
    data = get_json(
        f"/coins/{coin_id}/market_chart",
        {"vs_currency": "usd", "days": 210, "precision": "full"},
    )
    prices = data["prices"]
    volumes = data["total_volumes"]
    # CoinGecko provides daily snapshots for ranges >90 days. Exclude the
    # most recent (potentially partial) observation when it is today's date.
    today = datetime.now(timezone.utc).date()
    daily = [
        (datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date(), float(value))
        for ts, value in prices
    ]
    daily = [(day, price) for day, price in daily if day < today]
    if len(daily) < 200:
        raise RuntimeError(f"Insufficient daily history for {symbol}: {len(daily)}")
    closes = [price for _, price in daily]
    last_close = closes[-1]
    # Total volume is reported in USD by CoinGecko.
    volume_values = [float(v) for _, v in volumes]
    current = float(spot[coin_id]["usd"])
    change = (current / last_close - 1) * 100
    return {
        "symbol": symbol,
        "price_usd": current,
        "change_since_last_observation_pct": change,
        "rsi_14": rsi(closes),
        "sma_50": sma(closes, 50),
        "sma_200": sma(closes, 200),
        "volume_last_observation_usd": volume_values[-1] if volume_values else None,
        "volume_previous_20_average_usd": (
            sum(volume_values[-21:-1]) / 20 if len(volume_values) >= 21 else None
        ),
    }


def ai_summary(markets, timestamp):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "AI commentary is not configured yet. Add the OPENAI_API_KEY GitHub Actions secret and run the workflow again."
    model = os.environ.get("OPENAI_MODEL") or "gpt-4.1-mini"
    prompt = {
        "timestamp_utc": timestamp,
        "markets": markets,
        "instructions": (
            "Write a concise, cautious crypto market briefing for a beginner investor. "
            "Focus on BTC, ETH and AVAX. Explain bullish/bearish signals in plain language. "
            "Do not predict prices, give certainty, or issue buy/sell instructions. "
            "Mention conflicting indicators and risks. Distinguish observations from interpretation. "
            "Use headings: Market overview, ETH and AVAX, Risk watch, What to monitor. "
            "Use only the supplied data; do not invent news or macro events."
        )
    }
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "input": json.dumps(prompt), "max_output_tokens": 900},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    texts = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                texts.append(content.get("text", ""))
    return "\n".join(texts).strip() or "AI commentary was not returned."


def main():
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat(timespec="seconds")
    spot = get_json("/simple/price", {
        "ids": ",".join(COINS),
        "vs_currencies": "usd",
    })
    markets = [market_snapshot(coin_id, symbol, spot) for coin_id, symbol in COINS.items()]
    report = {
        "generated_at_utc": timestamp,
        "source": "CoinGecko public market data (USD)",
        "markets": markets,
        "analysis": ai_summary(markets, timestamp),
        "disclaimer": "For information only, not financial advice. Crypto assets are volatile and you can lose your investment. Prices are in USD, not USDC or EUR."
    }
    latest = REPORT_DIR / "latest.json"
    latest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    dated = REPORT_DIR / f"{now.strftime('%Y-%m-%d')}.json"
    dated.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved {latest} and {dated}")


if __name__ == "__main__":
    main()
