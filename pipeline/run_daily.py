import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "web" / "public" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = ["BTCUSDC", "ETHUSDC", "AVAXUSDC"]
BINANCE = "https://api.binance.com"


def get_json(path, params=None):
    response = requests.get(BINANCE + path, params=params, timeout=20)
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


def market_snapshot(symbol):
    candles = get_json("/api/v3/klines", {"symbol": symbol, "interval": "1d", "limit": 210})
    closes = [float(c[4]) for c in candles[:-1]]  # completed daily candles only
    volumes = [float(c[5]) for c in candles[:-1]]
    ticker = get_json("/api/v3/ticker/price", {"symbol": symbol})
    current = float(ticker["price"])
    previous = closes[-1]
    change_24h = (current / previous - 1) * 100 if previous else 0
    return {
        "symbol": symbol.replace("USDC", ""),
        "pair": symbol,
        "price_usdc": current,
        "change_since_last_close_pct": change_24h,
        "rsi_14": rsi(closes),
        "sma_50": sma(closes, 50),
        "sma_200": sma(closes, 200),
        "volume_last_closed_day": volumes[-1] if volumes else None,
        "volume_previous_20d_average": sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else None,
        "last_completed_daily_candle_close": closes[-1],
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
    markets = [market_snapshot(s) for s in SYMBOLS]
    report = {
        "generated_at_utc": timestamp,
        "source": "Binance public market data",
        "markets": markets,
        "analysis": ai_summary(markets, timestamp),
        "disclaimer": "For information only, not financial advice. Crypto assets are volatile and you can lose your investment."
    }
    latest = REPORT_DIR / "latest.json"
    latest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    dated = REPORT_DIR / f"{now.strftime('%Y-%m-%d')}.json"
    dated.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved {latest} and {dated}")


if __name__ == "__main__":
    main()
