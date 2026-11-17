import fs from 'node:fs';
import path from 'node:path';

type Risk = { score: number; level: string; trend: string; factors: string[] };
type Macd = { line: number; signal: number; histogram: number; previous_histogram: number | null };
type Market = {
  symbol: string; price_usd: number; price_eur?: number;
  change_since_last_observation_pct: number;
  rsi_14: number | null; sma_50: number | null; sma_200: number | null;
  macd?: Macd; volatility_30d_annualized_pct?: number;
  risk?: Risk; volume_last_observation_usd: number | null;
  volume_previous_20_average_usd: number | null;
  last_completed_observation_date_utc?: string;
};
type Report = {
  schema_version?: number; generated_at_utc: string; source: string;
  markets: Market[]; analysis: string; disclaimer: string; risk_methodology?: string;
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
      <div><div className="eyebrow">DAILY MARKET MONITOR · V2.1</div><h1>Crypto Market Intelligence</h1><p className="sub">BTC, ETH and AVAX · Independent market analysis · No trading account connection</p></div>
      <div className="stamp">{report ? `Updated ${new Date(report.generated_at_utc).toLocaleString('en-GB', { timeZone: 'Europe/Ljubljana', dateStyle: 'medium', timeStyle: 'short' })} (Slovenia)` : 'Awaiting first report'}</div>
    </header>
    {!report ? <section className="panel"><h2>No report yet</h2><p>The dashboard will populate after the first successful GitHub Actions run.</p></section> : <>
      {report.schema_version !== 2 && <section className="panel notice">V2.1 is deployed. Enhanced risk and EUR data will appear after the next successful daily report.</section>}
      <section className="grid">
        {report.markets.map(m => <article className="coin" key={m.symbol}>
          <div className="coinhead"><span>{m.symbol}</span><span className={m.change_since_last_observation_pct >= 0 ? 'positive' : 'negative'}>{pct(m.change_since_last_observation_pct)}</span></div>
          <div className="price">{money(m.price_usd, 'USD')}</div>
          <div className="eur">{m.price_eur != null ? money(m.price_eur, 'EUR') : 'EUR price pending'}</div>
          {m.risk && <div className="riskrow"><span className="riskpill">{m.risk.trend} trend</span><span className="riskpill">Risk: {m.risk.level} ({m.risk.score}/100)</span></div>}
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
      <section className="panel analysis"><div className="eyebrow">AI MARKET BRIEFING</div><Briefing content={report.analysis} /></section>
      <section className="panel"><div className="eyebrow">DATA & METHODOLOGY</div><p>Source: {report.source}. RSI uses Wilder smoothing; MACD uses EMA (12, 26, 9); moving averages use completed daily USD observations. EUR prices are separate CoinGecko spot quotes.</p>{report.risk_methodology && <p><strong>Risk methodology:</strong> {report.risk_methodology}</p>}<p className="disclaimer">{report.disclaimer}</p></section>
    </>}
    <footer>Crypto Market Intelligence · Public read-only dashboard</footer>
  </main>;
}
