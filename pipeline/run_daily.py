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


def historical_series(dates, closes):
    """Daily price, moving averages and Wilder RSI, all based on completed observations."""
    rows = []
    for i, (day, close) in enumerate(zip(dates, closes)):
        # At most ~210 days, so simple rolling calculations are inexpensive.
        rows.append({
            'date': day.isoformat(),
            'price_usd': round(close, 8),
            'sma_50': round(sum(closes[i - 49:i + 1]) / 50, 8) if i >= 49 else None,
            'sma_200': round(sum(closes[i - 199:i + 1]) / 200, 8) if i >= 199 else None,
            'rsi_14': None,
        })
    period = 14
    if len(closes) > period:
        changes = [b - a for a, b in zip(closes, closes[1:])]
        gain = sum(max(c, 0) for c in changes[:period]) / period
        loss = sum(max(-c, 0) for c in changes[:period]) / period
        def value(g, l):
            return 100.0 if l == 0 and g else 50.0 if l == 0 else 100 - 100 / (1 + g / l)
        rows[period]['rsi_14'] = round(value(gain, loss), 3)
        for i in range(period + 1, len(closes)):
            change = changes[i - 1]
            gain = (gain * (period - 1) + max(change, 0)) / period
            loss = (loss * (period - 1) + max(-change, 0)) / period
            rows[i]['rsi_14'] = round(value(gain, loss), 3)
    return rows



def reconstructed_risk_history(dates, closes):
    """Scores from completed daily observations only; no look-ahead data."""
    output = []
    for i in range(199, len(closes)):
        past = closes[:i + 1]
        momentum = macd(past)
        strength = rsi(past)
        vol = volatility_30d(past)
        if momentum is None or strength is None or vol is None:
            continue
        assessment = risk_assessment(past[-1], sma(past, 50), sma(past, 200), momentum, strength, vol)
        output.append({'date': dates[i].isoformat(), 'score': assessment['score'],
                       'level': assessment['level']})
    return output


def opportunity_assessment(price, avg50, avg200, momentum, strength, vol, risk, volume_ratio):
    """Conservative, non-personalized market-condition heuristic; not a trade instruction."""
    if any(v is None for v in (price, avg50, avg200, momentum, strength, vol)):
        return {'signal': 'Hold / Wait', 'agreement': 'Insufficient data',
                'reasons': ['Not enough valid observations to assess market conditions.']}
    histogram = momentum['histogram']
    previous = momentum.get('previous_histogram')
    improving = previous is not None and histogram > previous
    worsening = previous is not None and histogram < previous
    above_both = price > avg50 and price > avg200
    below_both = price < avg50 and price < avg200
    confirmation = [above_both, histogram > 0, improving, 40 <= strength <= 68,
                    vol < 65, volume_ratio is not None and volume_ratio >= 1]
    agreement = f'{sum(confirmation)} of 6 constructive conditions'
    reasons = [f'Price is {"above" if above_both else "not above"} both moving averages.',
               f'MACD histogram is {"positive" if histogram > 0 else "negative"} and {"improving" if improving else "not improving"}.',
               f'RSI is {strength:.1f}; an oversold reading alone is not a buy signal.',
               f'Annualized 30-day volatility is {vol:.1f}%.']
    if volume_ratio is None:
        reasons.append('Volume confirmation unavailable; signal remains conservative.')
    else:
        reasons.append(f'Latest completed daily volume is {volume_ratio:.2f}× its previous 20-observation average.')
    if risk['score'] >= 75 and below_both and histogram < 0 and worsening:
        signal = 'Strong Risk Warning'
    elif risk['score'] >= 65 and below_both and histogram < 0:
        signal = 'Consider Reducing'
    elif sum(confirmation) >= 5 and risk['score'] < 40 and volume_ratio is not None:
        signal = 'Buy Opportunity'
    elif sum(confirmation) >= 4 and risk['score'] < 60 and improving:
        signal = 'Accumulate Cautiously'
    else:
        signal = 'Hold / Wait'
    return {'signal': signal, 'agreement': agreement, 'reasons': reasons,
            'note': 'Market-only indicator. It does not account for holdings, entry price, taxes or time horizon.'}

def buying_opportunity_assessment(price, closes, avg50, avg200, momentum, strength, vol):
    """Independent 0–100 research heuristic. Not a return forecast or trade instruction.

    Prices use the latest spot and completed daily observations. No future data.
    Component maximums: discount 25, selling exhaustion 20, recovery 25,
    weekly trend 20, volatility 10. Scores are not probabilities.
    """
    if (len(closes) < 8 or any(v is None for v in
            (price, avg50, avg200, momentum, strength, vol))):
        return {'score': None, 'label': 'Insufficient Data', 'factors': [],
                'note': 'Insufficient observations to calculate a buying-opportunity score.'}
    discount = (avg200 - price) / avg200 * 100
    discount_points = 25 if discount >= 25 else 18 if discount >= 15 else 10 if discount >= 5 else 3 if discount >= 0 else 0
    exhaustion_points = 20 if strength < 25 else 16 if strength < 35 else 10 if strength < 45 else 4 if strength <= 55 else 0
    hist = momentum['histogram']
    previous = momentum.get('previous_histogram')
    improving = previous is not None and hist > previous
    recovery_points = (10 if improving else 0) + (8 if hist > 0 else 0) + (7 if price > avg50 else 0)
    weekly_change = (closes[-1] / closes[-8] - 1) * 100
    weekly_points = 20 if weekly_change >= 5 else 15 if weekly_change >= 1 else 9 if weekly_change >= -2 else 4 if weekly_change >= -6 else 0
    volatility_points = 10 if vol < 40 else 7 if vol < 65 else 3 if vol < 100 else 0
    raw = discount_points + exhaustion_points + recovery_points + weekly_points + volatility_points
    # A sharp selloff can look cheap and oversold without showing any recovery.
    # Require at least one positive momentum confirmation for the top categories.
    confirmed = improving or hist > 0
    score = min(raw, 69) if not confirmed else raw
    if score >= 85: label = 'Strong Opportunity'
    elif score >= 70: label = 'Attractive'
    elif score >= 50: label = 'Potential Accumulation'
    elif score >= 25: label = 'Wait'
    else: label = 'Unattractive'
    factors = [
        {'name': 'Price vs SMA200', 'points': discount_points, 'max': 25,
         'detail': f'{discount:+.1f}% below the 200-day average (negative means above).'},
        {'name': 'Selling exhaustion (RSI)', 'points': exhaustion_points, 'max': 20,
         'detail': f'RSI {strength:.1f}; oversold can remain oversold.'},
        {'name': 'Recovery confirmation', 'points': recovery_points, 'max': 25,
         'detail': f'MACD histogram {hist:+.4f}; improving: {"yes" if improving else "no"}; above SMA50: {"yes" if price > avg50 else "no"}.'},
        {'name': 'Completed 7-day trend', 'points': weekly_points, 'max': 20,
         'detail': f'{weekly_change:+.1f}% across seven completed daily intervals.'},
        {'name': 'Volatility', 'points': volatility_points, 'max': 10,
         'detail': f'{vol:.1f}% annualized 30-day volatility.'},
    ]
    return {'score': score, 'label': label, 'factors': factors,
            'confirmation_cap_applied': not confirmed and raw > 69,
            'note': 'Independent, unvalidated heuristic; not a return probability. A high opportunity score can coexist with high position risk.'}


def market_snapshot(coin_id, symbol, spot, today):
    data = get_json(f'/coins/{coin_id}/market_chart',
                    {'vs_currency': 'usd', 'days': 330, 'precision': 'full'})
    daily = completed_daily_observations(data['prices'], today)
    volume_daily = dict(completed_daily_observations(data['total_volumes'], today))
    if len(daily) < 290:
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
        'history': historical_series(dates, closes),
        'risk_history': reconstructed_risk_history(dates, closes),
        'buying_opportunity': buying_opportunity_assessment(current, closes, average50, average200, momentum, strength, vol),
        'opportunity': opportunity_assessment(current, average50, average200, momentum, strength, vol, risk,
            volumes[-1] / (sum(previous20) / 20) if len(previous20) == 20 and sum(previous20) > 0 and volumes[-1] is not None else None),
    }


def ai_summary(markets, timestamp):
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise RuntimeError('OPENAI_API_KEY GitHub secret is missing')
    prompt = {
        'timestamp_utc': timestamp,
        'markets': [{k: v for k, v in m.items() if k not in ('history', 'risk_history')} for m in markets],
        'instructions': (
            'Write a concise, cautious market briefing for a beginner following BTC, ETH, AVAX. '
            'Use Markdown with headings: Market overview, ETH and AVAX, Risk watch, What to monitor. '
            'Interpret only the provided data. Explain the computed risk scores and their limitations. '
            'Do not invent news, support/resistance levels, macro events, or forecasts. '
            'Explain position risk separately from the independent buying_opportunity score; they may disagree. Describe the deterministic opportunity labels as market conditions, never personalized buy/sell advice. Do not override their labels. Distinguish a possible oversold bounce from a confirmed recovery. '
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
        'schema_version': 5,
        'generated_at_utc': now.isoformat(timespec='seconds'),
        'source': 'CoinGecko Demo API, aggregated market data',
        'markets': markets,
        'analysis': ai_summary(markets, now.isoformat(timespec='seconds')),
        'buying_opportunity_methodology': 'Independent 0–100 heuristic: discount to SMA200 (25), RSI selling exhaustion (20), MACD/SMA50 recovery confirmation (25), seven-completed-day trend (20), annualized 30-day volatility (10). Without positive MACD or improving MACD, score capped at 69. Bands: 0–24 Unattractive; 25–49 Wait; 50–69 Potential Accumulation; 70–84 Attractive; 85–100 Strong Opportunity. Unvalidated, not a forecast or trade instruction.',
        'opportunity_methodology': 'Rule-based, market-only signal. Constructive conditions: price above both SMAs, positive MACD histogram, improving MACD histogram, RSI 40–68, volatility below 65%, and latest completed volume at least its previous 20-day average. Buy Opportunity requires at least 5/6 and risk below 40; Accumulate Cautiously requires at least 4/6, improving MACD and risk below 60. Downside warnings depend on high risk, price below both SMAs and negative MACD. Missing volume cannot qualify for Buy Opportunity. Signals are not trading instructions.',
        'risk_methodology': 'Heuristic score 0–100: below SMA200 +25; below SMA50 +20; SMA50 below SMA200 +15; negative MACD histogram +15; RSI <35 or >75 +10; annualized 30d volatility ≥40% +5, ≥65% +10, ≥100% +15. Low <25, Moderate 25–49, High 50–74, Extreme ≥75. Not a probability or a prediction.',
        'disclaimer': 'For information only, not financial advice. Crypto assets are volatile. Risk score is a heuristic, not a guarantee. EUR and USD spot prices are indicative.',
    }
    (REPORT_DIR / 'latest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (REPORT_DIR / f'{now:%Y-%m-%d}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Saved daily report for {len(markets)} assets')


if __name__ == '__main__':
    main()
