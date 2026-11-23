import fs from 'node:fs';
import path from 'node:path';
import MarketCharts from './market-charts';
import RiskTrends from './risk-trends';

type Risk = { score: number; level: string; trend: string; factors: string[] };
type Macd = { line: number; signal: number; histogram: number; previous_histogram: number | null };
type HistoryPoint = { date: string; price_usd: number; sma_50: number | null; sma_200: number | null; rsi_14: number | null };
type BuyingOpportunity = { score: number | null; label: string; factors: { name: string; points: number; max: number; detail: string }[]; note: string; confirmation_cap_applied?: boolean };
type Opportunity = { signal: string; agreement: string; reasons: string[]; note?: string };
type RiskPoint = { date: string; score: number; level: string };
type Market = {
  symbol: string; price_usd: number; price_eur?: number; history?: HistoryPoint[];
  change_since_last_observation_pct: number;
  rsi_14: number | null; sma_50: number | null; sma_200: number | null;
  macd?: Macd; volatility_30d_annualized_pct?: number;
  risk?: Risk; opportunity?: Opportunity; buying_opportunity?: BuyingOpportunity; risk_history?: RiskPoint[]; volume_last_observation_usd: number | null;
  volume_previous_20_average_usd: number | null;
  last_completed_observation_date_utc?: string;
};
type Report = {
  schema_version?: number; generated_at_utc: string; source: string;
  markets: Market[]; analysis: string; disclaimer: string; risk_methodology?: string; opportunity_methodology?: string; buying_opportunity_methodology?: string;
};

function loadReport(): Report | null {
  try {
    return JSON.parse(fs.readFileSync(path.join(process.cwd(), 'public', 'reports', 'latest.json'), 'utf8')) as Report;
  } catch { return null; }
}
function money(value: number, currency: 'USD' | 'EUR') {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: value < 1 ? 4 : 2 }).format(value);
}
function pct(value: number) { return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`; }
function readable(value?: number | null) { return value == null ? '—' : value.toFixed(2); }
function compact(value: number | null) { return value == null ? '—' : new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value); }

// Presentation-only mapping: preserve the deterministic signal from the daily report.
function signalDisplay(signal: string): { label: string; tone: string; interpretation: string } {
  switch (signal) {
    case 'Buy Opportunity': return { label: 'BUY OPPORTUNITY', tone: 'buy', interpretation: 'Constructive conditions are aligned. Consider whether a staged entry fits your risk limits; this is not a guarantee.' };
    case 'Accumulate Cautiously': return { label: 'ACCUMULATE CAUTIOUSLY', tone: 'accumulate', interpretation: 'Some recovery evidence is present. Smaller, staged entries may reduce timing risk.' };
    case 'Consider Reducing': return { label: 'CONSIDER REDUCING', tone: 'reduce', interpretation: 'Downside conditions are elevated. Review exposure and position size before adding risk.' };
    case 'Strong Risk Warning': return { label: 'STRONG RISK WARNING', tone: 'warning', interpretation: 'Multiple downside indicators remain active. Prioritize capital preservation; wait for stronger confirmation before considering new exposure.' };
    default: return { label: 'HOLD / WAIT', tone: 'wait', interpretation: 'Signals are mixed or incomplete. Waiting for clearer evidence may be preferable to acting now.' };
  }
}

// Render a deliberately small, safe Markdown subset without raw HTML or injected markup.
function Inline({ text }: { text: string }) {
  return <>{text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : <span key={i}>{part}</span>
  )}</>;
}
function Briefing({ content }: { content: string }) {
  return <div className="briefing">{content.split(/\n+/).map((raw, i) => {
    const line = raw.trim();
    if (!line) return null;
    if (line.startsWith('### ')) return <h3 key={i}><Inline text={line.slice(4)} /></h3>;
    if (line.startsWith('## ')) return <h3 key={i}><Inline text={line.slice(3)} /></h3>;
    if (line.startsWith('# ')) return <h3 key={i}><Inline text={line.slice(2)} /></h3>;
    if (/^\*\*[^*]+\*\*$/.test(line)) return <h3 key={i}>{line.slice(2, -2)}</h3>;
    if (line.startsWith('- ')) return <p className="bullet" key={i}>• <Inline text={line.slice(2)} /></p>;
    return <p key={i}><Inline text={line} /></p>;
  })}</div>;
}

export default function Home() {
  const report = loadReport();
  return <main className="shell">
    <header className="top">
      <div><div className="eyebrow">DAILY MARKET MONITOR · V2.4</div><h1>Crypto Market Intelligence</h1><p className="sub">BTC, ETH and AVAX · Independent market analysis · No trading account connection</p></div>
      <div className="stamp">{report ? `Updated ${new Date(report.generated_at_utc).toLocaleString('en-GB', { timeZone: 'Europe/Ljubljana', dateStyle: 'medium', timeStyle: 'short' })} (Slovenia)` : 'Awaiting first report'}</div>
    </header>
    {!report ? <section className="panel"><h2>No report yet</h2><p>The dashboard will populate after the first successful GitHub Actions run.</p></section> : <>
      {(report.schema_version ?? 0) < 2 && <section className="panel notice">Enhanced risk and EUR data will appear after the next successful daily report.</section>}
      <section className="grid">
        {report.markets.map(m => <article className="coin" key={m.symbol}>
          <div className="coinhead"><span>{m.symbol}</span><span className={m.change_since_last_observation_pct >= 0 ? 'positive' : 'negative'}>{pct(m.change_since_last_observation_pct)}</span></div>
          <div className="price">{money(m.price_usd, 'USD')}</div>
          <div className="eur">{m.price_eur != null ? money(m.price_eur, 'EUR') : 'EUR price pending'}</div>
          {m.risk && <div className="riskrow"><span className="riskpill">{m.risk.trend} trend</span><span className="riskpill">Risk: {m.risk.level} ({m.risk.score}/100)</span></div>}
          <div className="dual-assessment">
            {m.opportunity && <div className={`opportunity opportunity--${signalDisplay(m.opportunity.signal).tone}`}>
              <div className="opportunity-label">POSITION RISK · HOLDING EXPOSURE</div>
              <div className={`opportunity-badge opportunity-badge--${signalDisplay(m.opportunity.signal).tone}`}>{signalDisplay(m.opportunity.signal).label}</div>
              <p className="opportunity-guidance">{signalDisplay(m.opportunity.signal).interpretation}</p>
              <small>{m.opportunity.agreement}</small>
              <details><summary>Why this assessment?</summary><ul>{m.opportunity.reasons.map((reason, i) => <li key={i}>{reason}</li>)}</ul><p>{m.opportunity.note}</p></details>
            </div>}
            {m.buying_opportunity && <div className="buying-panel">
              <div className="opportunity-label">BUYING OPPORTUNITY · INDEPENDENT SCORE</div>
              <div className="buying-result"><strong>{m.buying_opportunity.score == null ? '—' : `${m.buying_opportunity.score}/100`}</strong><span className={`buying-status buying-status--${m.buying_opportunity.label.toLowerCase().replace(/[^a-z]+/g, '-')}`}>{m.buying_opportunity.label}</span></div>
              <p className="opportunity-guidance">{m.buying_opportunity.label === 'Strong Opportunity' || m.buying_opportunity.label === 'Attractive' ? 'Several entry conditions are constructive; check downside risk before acting.' : m.buying_opportunity.label === 'Potential Accumulation' ? 'Some value or exhaustion evidence exists, but recovery may remain uncertain.' : 'No sufficiently compelling entry setup under these rules.'}</p>
              <details><summary>How was this score calculated?</summary><ul>{m.buying_opportunity.factors.map((f, i) => <li key={i}><strong>{f.name}: {f.points}/{f.max}</strong> — {f.detail}</li>)}</ul>{m.buying_opportunity.confirmation_cap_applied && <p>Score capped at 69 because momentum confirmation is absent.</p>}<p>{m.buying_opportunity.note}</p></details>
            </div>}
          </div>
          <div className="metrics">
            <div><small>RSI (14)</small><b>{readable(m.rsi_14)}</b></div>
            <div><small>SMA 50 (USD)</small><b>{m.sma_50 == null ? '—' : money(m.sma_50, 'USD')}</b></div>
            <div><small>SMA 200 (USD)</small><b>{m.sma_200 == null ? '—' : money(m.sma_200, 'USD')}</b></div>
            <div><small>MACD histogram</small><b>{readable(m.macd?.histogram)}</b></div>
            <div><small>Volatility (30d annualized)</small><b>{m.volatility_30d_annualized_pct == null ? '—' : `${readable(m.volatility_30d_annualized_pct)}%`}</b></div>
            <div><small>Daily volume (USD)</small><b>{compact(m.volume_last_observation_usd)}</b></div>
          </div>
          {m.risk && <details className="factors"><summary>Why this risk score?</summary>{m.risk.factors.length ? <ul>{m.risk.factors.map((factor, i) => <li key={i}>{factor}</li>)}</ul> : <p>No scoring risk factors triggered.</p>}</details>}
        </article>)}
      </section>
      <p className="footnote">Percentage change is since the last completed daily observation, not an exact 24-hour change. Spot prices are indicative.</p>
      <RiskTrends markets={report.markets.map(m => ({symbol: m.symbol, history: m.risk_history ?? []}))} />
      <MarketCharts markets={report.markets.map(m => ({ symbol: m.symbol, history: m.history ?? [] }))} />
      <section className="panel analysis"><div className="eyebrow">AI MARKET BRIEFING</div><Briefing content={report.analysis} /></section>
      <section className="panel"><div className="eyebrow">DATA & METHODOLOGY</div><p>Source: {report.source}. Historical charts show completed UTC daily observations, not live candles; moving averages use USD prices. RSI uses Wilder smoothing; MACD uses EMA (12, 26, 9); moving averages use completed daily USD observations. EUR prices are separate CoinGecko spot quotes.</p>{report.risk_methodology && <p><strong>Risk methodology:</strong> {report.risk_methodology}</p>}{report.buying_opportunity_methodology && <p><strong>Buying opportunity methodology:</strong> {report.buying_opportunity_methodology}</p>}{report.opportunity_methodology && <p><strong>Opportunity methodology:</strong> {report.opportunity_methodology}</p>}<p className="disclaimer">{report.disclaimer}</p></section>
    </>}
    <footer>Crypto Market Intelligence · Public read-only dashboard</footer>
  </main>;
}
