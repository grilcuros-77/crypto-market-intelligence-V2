'use client';
import { useState } from 'react';
type Point = { date: string; score: number; level: string };
type Coin = { symbol: string; history: Point[] };
const W = 900, H = 250, L = 48, R = 18, T = 20, B = 36;
const colors: Record<string, string> = { BTC: '#7ab5ff', ETH: '#f7c66f', AVAX: '#b9a1ff' };
export default function RiskTrends({ markets }: { markets: Coin[] }) {
  const [range, setRange] = useState(30);
  const [focus, setFocus] = useState('ETH');
  const [hover, setHover] = useState<number | null>(null);
  const selected = markets.find(m => m.symbol === focus) ?? markets[0];
  const points = selected?.history.slice(-range) ?? [];
  const latest = points.length ? points[points.length - 1] : null;
  const index = hover === null ? points.length - 1 : Math.min(points.length - 1, Math.max(0, hover));
  const active = points[index];
  const diff = (days: number) => points.length > days ? (latest!.score - points[points.length - 1 - days].score) : null;
  const x = (i: number) => L + i / Math.max(1, points.length - 1) * (W - L - R);
  const y = (v: number) => T + (100 - v) / 100 * (H - T - B);
  const coords = points.map((p, i) => `${x(i).toFixed(1)},${y(p.score).toFixed(1)}`).join(' ');
  return <section className="panel risk-trends">
    <div className="eyebrow">HISTORICAL RISK · V2.3</div>
    <div className="chart-toolbar">
      <div className="chart-controls" aria-label="Choose asset">{markets.map(m => <button key={m.symbol} className={focus === m.symbol ? 'active' : ''} onClick={() => { setFocus(m.symbol); setHover(null); }}>{m.symbol}</button>)}</div>
      <div className="chart-controls" aria-label="Choose history range">{[30, 90].map(n => <button key={n} className={range === n ? 'active' : ''} onClick={() => { setRange(n); setHover(null); }}>{n}D</button>)}</div>
    </div>
    <div className="chart-heading"><h2>{focus} risk history <span>(0–100)</span></h2><span>{active ? `${active.date} · ${active.score}/100 · ${active.level}` : 'Awaiting reconstructed history'}</span></div>
    {points.length > 1 ? <>
      <div className="risk-summary"><span>Current completed-day score: <b>{latest?.score}/100</b></span><span>7-day change: <b>{diff(7) === null ? '—' : `${diff(7)! > 0 ? '+' : ''}${diff(7)} points`}</b></span><span>30-day change: <b>{diff(30) === null ? '—' : `${diff(30)! > 0 ? '+' : ''}${diff(30)} points`}</b></span></div>
      <div className="risk-chart-wrap"><svg className="risk-chart-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${focus} reconstructed historical risk score`} onPointerLeave={() => setHover(null)} onPointerMove={e => { const svg = e.currentTarget; const rect = svg.getBoundingClientRect(); const px = (e.clientX - rect.left) / rect.width * W; setHover(Math.max(0, Math.min(points.length - 1, Math.round((px - L) / (W - L - R) * (points.length - 1))))); }}>
        {[0,25,50,75,100].map(v => <g key={v}><line x1={L} x2={W-R} y1={y(v)} y2={y(v)} stroke="#34415d" strokeDasharray="4 5"/><text x={L-10} y={y(v)+4} textAnchor="end" fill="#a7b7d4" fontSize="12">{v}</text></g>)}
        {points.length > 1 && [0,.25,.5,.75,1].map((f,i) => { const k=Math.round(f*(points.length-1));return <text key={i} x={x(k)} y={H-8} textAnchor={i===0?'start':i===4?'end':'middle'} fill="#a7b7d4" fontSize="12">{points[k].date.slice(5)}</text>; })}
        <polyline points={coords} fill="none" stroke={colors[focus] ?? '#7ab5ff'} strokeWidth="2.8" strokeLinejoin="round" strokeLinecap="round"/>
        {active && <g><line x1={x(index)} x2={x(index)} y1={T} y2={H-B} stroke="#f0f4ff" strokeDasharray="4 4"/><circle cx={x(index)} cy={y(active.score)} r="5" fill="#fff" stroke={colors[focus] ?? '#7ab5ff'} strokeWidth="2"/></g>}
        <rect x={L} y={T} width={W-L-R} height={H-T-B} fill="transparent"/>
      </svg></div>
      <p className="risk-selected">{active?.date}: <strong>{active?.score}/100</strong> ({active?.level})</p>
    </> : <p className="chart-note">Reconstructed risk history will appear after the next successful daily pipeline run. At least 200 completed observations are needed before a historical score can be calculated.</p>}
    <p className="chart-note">Reconstructed scores use only data available up to each completed UTC observation, with the existing V2.1 risk formula. They are not archived historical recommendations. The latest completed-day score can differ from the live spot-based score shown above. Higher scores mean more risk factors triggered, not a measured probability of loss.</p>
  </section>;
}
