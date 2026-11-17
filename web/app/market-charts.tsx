'use client';

import { useState } from 'react';

type Point = { date: string; price_usd: number; sma_50: number | null; sma_200: number | null; rsi_14: number | null };
type Coin = { symbol: string; history: Point[] };
type Key = 'price_usd' | 'sma_50' | 'sma_200' | 'rsi_14';
const WIDTH = 900;
const HEIGHT = 270;
const M = { left: 72, right: 18, top: 20, bottom: 34 };
const formatPrice = (n: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: n < 1 ? 4 : 2 }).format(n);

function Plot({ points, keys, rsi, selectedIndex, onSelect }: {
  points: Point[]; keys: { key: Key; color: string; label: string }[]; rsi?: boolean;
  selectedIndex: number | null; onSelect: (i: number | null) => void;
}) {
  const available = points.flatMap(p => keys.map(k => p[k.key]).filter((v): v is number => typeof v === 'number' && Number.isFinite(v)));
  if (points.length < 2 || available.length === 0) return <p className="chart-empty">Not enough historical observations yet.</p>;
  const rawMin = rsi ? 0 : Math.min(...available);
  const rawMax = rsi ? 100 : Math.max(...available);
  const pad = rsi ? 0 : Math.max((rawMax - rawMin) * .08, rawMax * .005);
  const low = Math.max(0, rawMin - pad);
  const high = rawMax + pad;
  const x = (i: number) => M.left + i / (points.length - 1) * (WIDTH - M.left - M.right);
  const y = (v: number) => M.top + (high - v) / (high - low || 1) * (HEIGHT - M.top - M.bottom);
  const segments = (key: Key) => {
    const output: string[] = [];
    let segment: string[] = [];
    points.forEach((p, i) => {
      const v = p[key];
      if (typeof v === 'number' && Number.isFinite(v)) segment.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`);
      else if (segment.length) { output.push(segment.join(' ')); segment = []; }
    });
    if (segment.length) output.push(segment.join(' '));
    return output;
  };
  const ticks = [0, 1, 2, 3, 4].map(i => low + (high - low) * i / 4);
  const selected = selectedIndex === null ? null : points[Math.max(0, Math.min(points.length - 1, selectedIndex))];
  return <div className="chart-scroll">
    <svg className="history-svg" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={rsi ? 'Historical RSI line chart' : 'Historical USD price and moving average chart'}
      onPointerLeave={() => onSelect(null)} onPointerMove={e => {
        const svg = e.currentTarget;
        const transform = svg.getScreenCTM();
        if (!transform) return;
        const cursor = svg.createSVGPoint();
        cursor.x = e.clientX;
        cursor.y = e.clientY;
        const local = cursor.matrixTransform(transform.inverse());
        if (local.x < M.left || local.x > WIDTH - M.right || local.y < M.top || local.y > HEIGHT - M.bottom) {
          onSelect(null);
          return;
        }
        const index = Math.round((local.x - M.left) / (WIDTH - M.left - M.right) * (points.length - 1));
        onSelect(Math.max(0, Math.min(points.length - 1, index)));
      }}>
      {ticks.map((v, i) => <g key={i}><line x1={M.left} x2={WIDTH - M.right} y1={y(v)} y2={y(v)} stroke="#34415d" strokeDasharray="3 5"/><text x={M.left - 10} y={y(v) + 4} textAnchor="end" fill="#a7b7d4" fontSize="12">{rsi ? v.toFixed(0) : v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toFixed(2)}</text></g>)}
      {rsi && [30, 70].map(v => <line key={v} x1={M.left} x2={WIDTH - M.right} y1={y(v)} y2={y(v)} stroke="#e3b36a" strokeDasharray="6 5" opacity=".8"/>)}
      {[0, .25, .5, .75, 1].map((f, i) => { const idx = Math.round(f * (points.length - 1)); return <text key={i} x={x(idx)} y={HEIGHT - 8} textAnchor={i === 0 ? 'start' : i === 4 ? 'end' : 'middle'} fill="#a7b7d4" fontSize="12">{points[idx].date.slice(5)}</text>; })}
      {keys.map(k => segments(k.key).map((seg, i) => <polyline key={`${k.key}-${i}`} points={seg} fill="none" stroke={k.color} strokeWidth={k.key === 'price_usd' ? 2.7 : 2} strokeLinejoin="round" strokeLinecap="round"/>))}
      {selected && selectedIndex !== null && <g pointerEvents="none"><line x1={x(selectedIndex)} x2={x(selectedIndex)} y1={M.top} y2={HEIGHT - M.bottom} stroke="#e5e7eb" strokeDasharray="4 4" opacity=".65"/>{keys.map(k => { const v = selected[k.key]; return v == null ? null : <circle key={k.key} cx={x(selectedIndex)} cy={y(v)} r="4" fill={k.color} stroke="#111a30" strokeWidth="1.5"/>; })}</g>}
      <rect x={M.left} y={M.top} width={WIDTH - M.left - M.right} height={HEIGHT - M.top - M.bottom} fill="transparent" style={{ cursor: 'crosshair' }} />
    </svg>
  </div>;
}

export default function MarketCharts({ markets }: { markets: Coin[] }) {
  const [symbol, setSymbol] = useState('ETH');
  const [range, setRange] = useState(90);
  const [show50, setShow50] = useState(true);
  const [show200, setShow200] = useState(true);
  const [hover, setHover] = useState<number | null>(null);
  const selected = markets.find(m => m.symbol === symbol) ?? markets[0];
  if (!selected || !markets.some(m => m.history.length > 0)) return <section className="panel charts"><div className="eyebrow">HISTORICAL CHARTS · V2.2</div><p>Charts will become available after the next successful daily report with V2.2 data.</p></section>;
  const points = selected.history.slice(-range);
  const current = points[hover ?? points.length - 1];
  const priceKeys: { key: Key; color: string; label: string }[] = [{ key: 'price_usd', color: '#7ab5ff', label: 'Price' }];
  if (show50) priceKeys.push({ key: 'sma_50', color: '#f7c66f', label: 'SMA 50' });
  if (show200) priceKeys.push({ key: 'sma_200', color: '#a3e0c6', label: 'SMA 200' });
  return <section className="panel charts">
    <div className="eyebrow">HISTORICAL CHARTS · V2.2</div>
    <div className="chart-toolbar"><div className="chart-controls" aria-label="Choose cryptocurrency">{markets.map(m => <button key={m.symbol} className={symbol === m.symbol ? 'active' : ''} onClick={() => { setSymbol(m.symbol); setHover(null); }}>{m.symbol}</button>)}</div>
      <div className="chart-controls" aria-label="Choose date range">{[30, 90, 180].map(days => <button key={days} className={range === days ? 'active' : ''} onClick={() => { setRange(days); setHover(null); }}>{days}D</button>)}</div></div>
    <div className="chart-heading"><h2>{symbol} price history <span>(USD)</span></h2><span>{current?.date ?? '—'} · {current ? formatPrice(current.price_usd) : '—'}</span></div>
    <div className="chart-toggles"><span className="legend"><i style={{ background: '#7ab5ff' }}/>Price</span><label><input type="checkbox" checked={show50} onChange={e => setShow50(e.target.checked)}/><span className="legend"><i style={{ background: '#f7c66f' }}/>SMA 50</span></label><label><input type="checkbox" checked={show200} onChange={e => setShow200(e.target.checked)}/><span className="legend"><i style={{ background: '#a3e0c6' }}/>SMA 200</span></label></div>
    <Plot points={points} keys={priceKeys} selectedIndex={hover} onSelect={setHover}/>
    {hover !== null && current && <div role="status" aria-live="off" style={{ display: 'flex', flexWrap: 'wrap', gap: '12px 22px', padding: '12px 14px', margin: '8px 0 20px', border: '1px solid #34415d', borderRadius: 10, background: '#18243d', color: '#e7efff', fontSize: 13 }}>
      <strong>{current.date}</strong>
      <span>Price: <strong>{formatPrice(current.price_usd)}</strong></span>
      {show50 && <span>SMA 50: <strong>{current.sma_50 == null ? '—' : formatPrice(current.sma_50)}</strong></span>}
      {show200 && <span>SMA 200: <strong>{current.sma_200 == null ? '—' : formatPrice(current.sma_200)}</strong></span>}
      <span>RSI (14): <strong>{current.rsi_14 == null ? '—' : current.rsi_14.toFixed(1)}</strong></span>
    </div>}
    <div className="chart-heading"><h2>Relative Strength Index <span>(RSI 14)</span></h2><span>{current?.rsi_14 == null ? '—' : current.rsi_14.toFixed(1)}</span></div>
    <div className="chart-toggles"><span className="legend"><i style={{ background: '#b9a1ff' }}/>RSI</span><span className="chart-note">Dashed lines: 30 / 70</span></div>
    <Plot points={points} keys={[{ key: 'rsi_14', color: '#b9a1ff', label: 'RSI' }]} rsi selectedIndex={hover} onSelect={setHover}/>
    <p className="chart-note">Historical CoinGecko daily observations in UTC, excluding the incomplete current day. SMA 200 appears only where 200 completed observations are available. Hover to inspect a date. These are sampled market observations, not exchange candlesticks.</p>
  </section>;
}
