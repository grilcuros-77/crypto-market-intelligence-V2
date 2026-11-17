"""Daily market snapshot: deterministic indicators and risk scoring, AI commentary."""
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / 'web' / 'public' / 'reports'
REPORT_DIR.mkdir(parents=True, exist_ok=True)
COINS = {'bitcoin': 'BTC', 'ethereum': 'ETH', 'avalanche-2': 'AVAX'}
BASE_URL = 'https://api.coingecko.com/api/v3'


def get_json(path, params=None):
    key = os.environ.get('COINGECKO_API_KEY')
    if not key:
        raise RuntimeError('COINGECKO_API_KEY GitHub secret is missing')
    response = requests.get(BASE_URL + path, params=params,
                            headers={'x-cg-demo-api-key': key, 'accept': 'application/json'}, timeout=30)
    if response.status_code == 429:
        raise RuntimeError('CoinGecko rate limit (429); retry later')
    response.raise_for_status()
    return response.json()


def sma(values, period):
    return sum(values[-period:]) / period if len(values) >= period else None


def rsi(values, period=14):
    """Wilder RSI, seeded with the first period of price changes."""
    if len(values) <= period:
        return None
    changes = [b - a for a, b in zip(values, values[1:])]
    gain = sum(max(c, 0) for c in changes[:period]) / period
    loss = sum(max(-c, 0) for c in changes[:period]) / period
    for c in changes[period:]:
        gain = (gain * (period - 1) + max(c, 0)) / period
        loss = (loss * (period - 1) + max(-c, 0)) / period
    if loss == 0:
        return 100.0 if gain else 50.0
    return 100 - 100 / (1 + gain / loss)


def ema_series(values, period):
    """EMA seeded with a simple average; unavailable points are None."""
    output = [None] * len(values)
    if len(values) < period:
        return output
    ema = sum(values[:period]) / period
    output[period - 1] = ema
    weight = 2 / (period + 1)
    for i in range(period, len(values)):
        ema = values[i] * weight + ema * (1 - weight)
        output[i] = ema
    return output


def macd(values):
    fast, slow = ema_series(values, 12), ema_series(values, 26)
    line = [a - b for a, b in zip(fast, slow) if a is not None and b is not None]
    signal = ema_series(line, 9)
    if not line or signal[-1] is None:
        return None
    return {'line': line[-1], 'signal': signal[-1], 'histogram': line[-1] - signal[-1],
            'previous_histogram': line[-2] - signal[-2] if len(line) >= 2 and signal[-2] is not None else None}


def volatility_30d(values):
    if len(values) < 31:
        return None
    returns = [math.log(values[i] / values[i - 1]) for i in range(len(values) - 30, len(values))]
    avg = sum(returns) / len(returns)
    variance = sum((x - avg) ** 2 for x in returns) / len(returns)
    return math.sqrt(variance) * math.sqrt(365) * 100


def risk_assessment(price, avg50, avg200, momentum, rsi_value, vol):
    """Transparent 0–100 market-risk heuristic, not a forecast or safety guarantee."""
    score, factors = 0, []
    if price < avg200:
        score += 25
        factors.append('Price below 200-day average (+25)')
    if price < avg50:
        score += 20
        factors.append('Price below 50-day average (+20)')
    if avg50 < avg200:
        score += 15
        factors.append('50-day average below 200-day average (+15)')
    if momentum['histogram'] < 0:
        score += 15
        factors.append('Negative MACD histogram (+15)')
    if rsi_value < 35 or rsi_value > 75:
        score += 10
        factors.append('RSI in extreme zone (+10)')
    if vol >= 100:
        score += 15
        factors.append('30-day annualized volatility ≥100% (+15)')
    elif vol >= 65:
        score += 10
        factors.append('30-day annualized volatility ≥65% (+10)')
    elif vol >= 40:
        score += 5
        factors.append('30-day annualized volatility ≥40% (+5)')
    level = 'Low' if score < 25 else 'Moderate' if score < 50 else 'High' if score < 75 else 'Extreme'
    trend = 'Bearish' if price < avg50 and price < avg200 else 'Bullish' if price > avg50 and price > avg200 else 'Mixed'
    return {'score': score, 'level': level, 'trend': trend, 'factors': factors}


def completed_daily_observations(points, today):
    """One point per UTC date; remove the current incomplete UTC date."""
    by_day = {}
    for timestamp_ms, value in points:
        day = datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).date()
        if day < today:
            by_day[day] = float(value)
    return sorted(by_day.items())


def market_snapshot(coin_id, symbol, spot, today):
    data = get_json(f'/coins/{coin_id}/market_chart',
                    {'vs_currency': 'usd', 'days': 210, 'precision': 'full'})
    daily = completed_daily_observations(data['prices'], today)
    volume_daily = dict(completed_daily_observations(data['total_volumes'], today))
    if len(daily) < 200:
        raise RuntimeError(f'Insufficient daily history for {symbol}: {len(daily)}')
    dates = [day for day, _ in daily]
    closes = [price for _, price in daily]
    if any(price <= 0 for price in closes):
        raise RuntimeError(f'Invalid price history for {symbol}')
    current = float(spot[coin_id]['usd'])
    current_eur = float(spot[coin_id]['eur'])
    average50, average200 = sma(closes, 50), sma(closes, 200)
    momentum = macd(closes)
    strength = rsi(closes)
    vol = volatility_30d(closes)
    risk = risk_assessment(current, average50, average200, momentum, strength, vol)
    volumes = [volume_daily.get(day) for day in dates]
    previous20 = [v for v in volumes[-21:-1] if v is not None]
    return {
        'symbol': symbol,
        'price_usd': current,
        'price_eur': current_eur,
        'change_since_last_observation_pct': (current / closes[-1] - 1) * 100,
        'change_label': 'Since last completed daily observation (not 24h change)',
        'rsi_14': strength,
        'sma_50': average50,
        'sma_200': average200,
        'macd': momentum,
        'volatility_30d_annualized_pct': vol,
        'risk': risk,
        'volume_last_observation_usd': volumes[-1],
        'volume_previous_20_average_usd': sum(previous20) / len(previous20) if len(previous20) == 20 else None,
        'last_completed_observation_date_utc': dates[-1].isoformat(),
    }


def ai_summary(markets, timestamp):
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise RuntimeError('OPENAI_API_KEY GitHub secret is missing')
    prompt = {
        'timestamp_utc': timestamp,
        'markets': markets,
        'instructions': (
            'Write a concise, cautious market briefing for a beginner following BTC, ETH, AVAX. '
            'Use Markdown with headings: Market overview, ETH and AVAX, Risk watch, What to monitor. '
            'Interpret only the provided data. Explain the computed risk scores and their limitations. '
            'Do not invent news, support/resistance levels, macro events, or forecasts. '
            'Do not recommend trades. Distinguish a possible oversold bounce from a confirmed recovery. '
            'All change figures compare with last completed daily observation, not exactly 24 hours. '
            'All prices are spot snapshots in USD and EUR, not exchange-specific executable prices.'
        ),
    }
    response = requests.post('https://api.openai.com/v1/responses',
                             headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                             json={'model': os.environ.get('OPENAI_MODEL') or 'gpt-4.1-mini',
                                   'input': json.dumps(prompt), 'max_output_tokens': 1100}, timeout=60)
    response.raise_for_status()
    data = response.json()
    texts = [content.get('text', '') for item in data.get('output', [])
             for content in item.get('content', []) if content.get('type') == 'output_text']
    return '\n'.join(texts).strip() or 'AI commentary was not returned.'


def main():
    now = datetime.now(timezone.utc)
    spot = get_json('/simple/price', {'ids': ','.join(COINS), 'vs_currencies': 'usd,eur'})
    markets = [market_snapshot(coin_id, symbol, spot, now.date()) for coin_id, symbol in COINS.items()]
    report = {
        'schema_version': 2,
        'generated_at_utc': now.isoformat(timespec='seconds'),
        'source': 'CoinGecko Demo API, aggregated market data',
        'markets': markets,
        'analysis': ai_summary(markets, now.isoformat(timespec='seconds')),
        'risk_methodology': 'Heuristic score 0–100: below SMA200 +25; below SMA50 +20; SMA50 below SMA200 +15; negative MACD histogram +15; RSI <35 or >75 +10; annualized 30d volatility ≥40% +5, ≥65% +10, ≥100% +15. Low <25, Moderate 25–49, High 50–74, Extreme ≥75. Not a probability or a prediction.',
        'disclaimer': 'For information only, not financial advice. Crypto assets are volatile. Risk score is a heuristic, not a guarantee. EUR and USD spot prices are indicative.',
    }
    (REPORT_DIR / 'latest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (REPORT_DIR / f'{now:%Y-%m-%d}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Saved daily report for {len(markets)} assets')


if __name__ == '__main__':
    main()
