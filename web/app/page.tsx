import fs from 'node:fs';
import path from 'node:path';

type Market = {
  symbol: string; price_usd: number; change_since_last_observation_pct: number;
  rsi_14: number | null; sma_50: number | null; sma_200: number | null;
  volume_last_observation_usd: number | null; volume_previous_20_average_usd: number | null;
};
type Report = {
  generated_at_utc: string; source: string; markets: Market[];
  analysis: string; disclaimer: string;
};

function loadReport(): Report | null {
  try {
    const file = path.join(process.cwd(), 'public', 'reports', 'latest.json');
    return JSON.parse(fs.readFileSync(file, 'utf8')) as Report;
  } catch { return null; }
}
function money(value: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: value < 1 ? 4 : 2 }).format(value);
}
function pct(value: number) { return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`; }
function readable(value: number | null) { return value === null ? '—' : value.toFixed(2); }

export default function Home() {
  const report = loadReport();
  return <main className="shell">
    <header className="top">
      <div><div className="eyebrow">DAILY MARKET MONITOR</div><h1>Crypto Market Intelligence</h1><p className="sub">A data-led view of BTC, ETH and AVAX (USD prices). No trading or exchange account connection.</p></div>
      <div className="stamp">{report ? `Updated ${new Date(report.generated_at_utc).toLocaleString()}` : 'Awaiting first report'}</div>
    </header>
    {!report ? <section className="panel"><h2>No report yet</h2><p>The dashboard will populate after the first successful GitHub Actions run.</p></section> :
    <>
      <section className="grid">
        {report.markets.map(m => <article className="coin" key={m.symbol}>
          <div className="coinhead"><span>{m.symbol}</span><span className={m.change_since_last_observation_pct >= 0 ? 'positive' : 'negative'}>{pct(m.change_since_last_observation_pct)}</span></div>
          <div className="price">{money(m.price_usd)}</div>
          <div className="metrics">
            <div><small>RSI (14)</small><b>{readable(m.rsi_14)}</b></div>
            <div><small>SMA 50</small><b>{m.sma_50 === null ? '—' : money(m.sma_50)}</b></div>
            <div><small>SMA 200</small><b>{m.sma_200 === null ? '—' : money(m.sma_200)}</b></div>
          </div>
          <div className="volume">Daily volume (USD): {m.volume_last_observation_usd === null ? '—' : Math.round(m.volume_last_observation_usd).toLocaleString()}</div>
        </article>)}
      </section>
      <section className="panel analysis"><div className="eyebrow">AI MARKET BRIEFING</div><div className="prose">{report.analysis}</div></section>
      <section className="panel"><div className="eyebrow">DATA & METHODOLOGY</div><p>Market prices and completed daily candles from {report.source}. RSI (14), SMA (50) and SMA (200) are calculated by the pipeline. Percentage change compares the current price with the most recent completed daily observation. Values are quoted in USD, not USDC.</p><p className="disclaimer">{report.disclaimer}</p></section>
    </>}
    <footer>Crypto Market Intelligence · Public read-only dashboard</footer>
  </main>;
}
