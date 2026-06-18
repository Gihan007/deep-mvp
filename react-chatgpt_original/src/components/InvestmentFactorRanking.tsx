import React, { useEffect, useMemo, useState } from 'react';
import {
  listSectors,
  listIndustriesBySector,
  listCompaniesByIndustry,
  listAllCompanies,
  listCompanies,
  getInvestmentFactorRankingTable,
  getSpecialMetricRankingFromCacheAll,
  getSpecialMetricRankingFromCacheByDate,
} from '../api/client';
import type { Sector, Industry, Company, InvestmentFactorResponse, InvestmentFactorRow } from '../api/types';

// Selection modes for base company scope
// all: use ALL_TICKERS shortcut (hide other inputs)
// sector: prefill all companies in a selected sector
// industry: prefill all companies in selected sector+industry
// manual: bucket built only from manual direct additions

type SelectionMode = 'all' | 'sector' | 'industry' | 'manual' | 'all_cache' | 'all_cache_by_date';

export default function InvestmentFactorRanking() {
  // Scope mode
  const [selectionMode, setSelectionMode] = useState<SelectionMode>('manual');

  // Dropdown state
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [industries, setIndustries] = useState<Industry[]>([]);
  const [selectedSector, setSelectedSector] = useState<string>('');
  const [selectedIndustry, setSelectedIndustry] = useState<string>('');

  // Company lookup
  const [allCompanies, setAllCompanies] = useState<Company[]>([]);
  const [industryCompanies, setIndustryCompanies] = useState<Company[]>([]);

  // Ticker bucket
  const [tickerBucket, setTickerBucket] = useState<string[]>([]);

  // Direct select like ReportView
  const [directQuery, setDirectQuery] = useState<string>('');
  const [directOpen, setDirectOpen] = useState<boolean>(false);
  // Cache date for historical SpecialMetricRankingCache fetch (YYYY-MM-DD)
  const [cacheDate, setCacheDate] = useState<string>('');

  // Results
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<InvestmentFactorResponse | null>(null);

  // Load sector list and all companies for typeahead
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const secs = await listSectors();
        const comps = await listAllCompanies();
        if (!mounted) return;
        setSectors(secs || []);
        setAllCompanies(comps || []);
      } catch (e) {
        console.warn('Failed initial load', e);
      }
    })();
    return () => { mounted = false; };
  }, []);

  // On mode change, update bucket visibility/contents
  useEffect(() => {
    if (selectionMode === 'all' || selectionMode === 'all_cache' || selectionMode === 'all_cache_by_date') {
      setTickerBucket([]);
    } else if (selectionMode === 'manual') {
      // keep current manual selections; do nothing
    } else if (selectionMode === 'sector') {
      // if already have a sector, compute its companies
      if (selectedSector) {
        computeSectorTickers(selectedSector);
      } else {
        setTickerBucket([]);
      }
    } else if (selectionMode === 'industry') {
      // industry mode will react to selectedIndustry effect below
      if (!selectedIndustry) setTickerBucket([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectionMode]);

  // On sector changed, load industries and reset deeper selections
  useEffect(() => {
    let mounted = true;
    if (!selectedSector) {
      setIndustries([]);
      setSelectedIndustry('');
      setIndustryCompanies([]);
      if (selectionMode === 'sector') setTickerBucket([]);
      return;
    }
    (async () => {
      try {
        const inds = await listIndustriesBySector({ sectorName: selectedSector });
        if (!mounted) return;
        setIndustries(inds || []);
        setSelectedIndustry('');
        setIndustryCompanies([]);
        if (selectionMode === 'sector') {
          await computeSectorTickers(selectedSector);
        }
      } catch (e) {
        console.warn('Failed to load industries', e);
      }
    })();
    return () => { mounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSector]);

  // On industry changed, load companies and prefill bucket (industry mode)
  useEffect(() => {
    let mounted = true;
    if (!selectedIndustry) {
      setIndustryCompanies([]);
      if (selectionMode === 'industry') setTickerBucket([]);
      return;
    }
    (async () => {
      try {
        const comps = await listCompaniesByIndustry({ industryName: selectedIndustry });
        if (!mounted) return;
        setIndustryCompanies(comps || []);
        if (selectionMode === 'industry') {
                const base = (comps || []).map(c => (c.ticker || '').trim().toUpperCase()).filter(Boolean);
                setTickerBucket(prev => {
                  const prevExtras = prev.filter(t => !base.includes(t));
                  return Array.from(new Set([...base, ...prevExtras]));
                });
        }
      } catch (e) {
        console.warn('Failed to load companies for industry', e);
      }
    })();
    return () => { mounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIndustry]);

  // Helper to compute all sector companies by aggregating all industries under the sector
  const computeSectorTickers = async (sectorName: string) => {
    try {
      const inds = await listIndustriesBySector({ sectorName });
      const tickersSet = new Set<string>();
      // fetch companies for each industry in parallel
      await Promise.all(
        (inds || []).map(async ind => {
          const comps = await listCompaniesByIndustry({ industryName: ind.industryName || '' });
          (comps || []).forEach(c => {
            const t = (c.ticker || '').trim().toUpperCase();
            if (t) tickersSet.add(t);
          });
        })
      );
      const base = Array.from(tickersSet);
      setTickerBucket(prev => {
        const prevExtras = prev.filter(t => !base.includes(t));
        return Array.from(new Set([...base, ...prevExtras]));
      });
    } catch (e) {
      console.warn('Failed computeSectorTickers', e);
      setTickerBucket(prev => prev);
    }
  };

  const companySuggestions = useMemo(() => {
    const q = directQuery.trim().toLowerCase();
    if (!q) return allCompanies;
    return allCompanies.filter(c => {
      const name = (c.companyName || '').toLowerCase();
      const tick = (c.ticker || '').toLowerCase();
      return name.includes(q) || tick.includes(q);
    });
  }, [allCompanies, directQuery]);

  const addTicker = (tickerOrLabel: string) => {
    if (selectionMode === 'all') return; // not applicable
    // Accept either ticker or "Name(TICKER)" pattern
    const m = tickerOrLabel.match(/^(.*?)\s*\(([^)]+)\)\s*$/);
    const t = (m ? m[2] : tickerOrLabel).trim().toUpperCase();
    if (!t) return;
    setTickerBucket(prev => (prev.includes(t) ? prev : [...prev, t]));
  };

  const removeTicker = (t: string) => {
    if (selectionMode === 'all') return;
    setTickerBucket(prev => prev.filter(x => x !== t));
  };

  const clearBucket = () => {
    if (selectionMode === 'all') return;
    setTickerBucket([]);
  };

  const canGenerate =
    selectionMode === 'all' ||
    selectionMode === 'all_cache' ||
    (selectionMode === 'all_cache_by_date' && !!cacheDate) ||
    tickerBucket.length > 0;

  const handleGenerate = async () => {
    if (!canGenerate) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      let tickersToUse: string[] = tickerBucket;
      if (selectionMode === 'all') {
        // Fetch all companies then map to tickers
        const comps = await listCompanies();
        tickersToUse = Array.from(new Set((comps || []).map(c => (c.ticker || '').trim().toUpperCase()).filter(Boolean)));
        if (tickersToUse.length === 0) {
          throw new Error('No companies with tickers found');
        }
        const data: InvestmentFactorResponse = await getInvestmentFactorRankingTable(tickersToUse);
        setResult(data);
        return;
      } else if (selectionMode === 'all_cache') {
        const res = await getSpecialMetricRankingFromCacheAll();
        const ranking = Array.isArray(res?.Ranking) ? res.Ranking : [];
        const formatted = ranking.map((r: any) => ({
          'Overall Rank': r.overall_rank,
          'Ticker': r.ticker,
          'ROIC 5Y Avg': typeof r.roic_5y_avg === 'number' && typeof r.roic_rank === 'number' ? `${r.roic_5y_avg.toFixed(4)} (${r.roic_rank})` : 'N/A',
          'Earnings Yield': typeof r.earnings_yield === 'number' && typeof r.earnings_yield_rank === 'number' ? `${r.earnings_yield.toFixed(4)} (${r.earnings_yield_rank})` : 'N/A',
          'Intrinsic to Market Cap': typeof r.intrinsic_to_mc === 'number' && typeof r.intrinsic_to_mc_rank === 'number' ? `${r.intrinsic_to_mc.toFixed(4)} (${r.intrinsic_to_mc_rank})` : 'N/A',
        }));
        setResult({ table: formatted, rejected: [] });
        return;
      } else if (selectionMode === 'all_cache_by_date') {
        if (!cacheDate) {
          throw new Error('Please select a cache date');
        }
        const res = await getSpecialMetricRankingFromCacheByDate(cacheDate);
        const ranking = Array.isArray(res?.Ranking) ? res.Ranking : [];
        const formatted = ranking.map((r: any) => ({
          'Overall Rank': r.overall_rank,
          'Ticker': r.ticker,
          'ROIC 5Y Avg': typeof r.roic_5y_avg === 'number' && typeof r.roic_rank === 'number' ? `${r.roic_5y_avg.toFixed(4)} (${r.roic_rank})` : 'N/A',
          'Earnings Yield': typeof r.earnings_yield === 'number' && typeof r.earnings_yield_rank === 'number' ? `${r.earnings_yield.toFixed(4)} (${r.earnings_yield_rank})` : 'N/A',
          'Intrinsic to Market Cap': typeof r.intrinsic_to_mc === 'number' && typeof r.intrinsic_to_mc_rank === 'number' ? `${r.intrinsic_to_mc.toFixed(4)} (${r.intrinsic_to_mc_rank})` : 'N/A',
        }));
        setResult({ table: formatted, rejected: [] });
        return;
      }
      const data: InvestmentFactorResponse = await getInvestmentFactorRankingTable(tickersToUse);
      setResult(data);
    } catch (e: any) {
      console.error('Ranking table fetch failed', e);
      setError(e?.message || 'Failed to fetch ranking table');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-view">
      <div className="chat-header">
        <div className="title">Investment Factor Ranking</div>
      </div>

      {/* Controls */}
      <div className="composer">
        <div className="form-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
          {/* Selection mode */}
          <div className="field" style={{ minWidth: 220 }}>
            <label className="label">Selection mode</label>
            <select className="input" value={selectionMode} onChange={e => setSelectionMode(e.target.value as SelectionMode)}>
              <option value="all">Use all companies</option>
              <option value="all_cache">Use all companies with SpecialMetricRankingCache node</option>
              <option value="all_cache_by_date">Use all companies with SpecialMetricRankingCache (by date)</option>
              <option value="sector">All companies in a sector</option>
              <option value="industry">All companies in sector → industry</option>
              <option value="manual">Manual selection (direct)</option>
            </select>
          </div>
          {selectionMode === 'all_cache_by_date' && (
            <div className="field" style={{ minWidth: 220 }}>
              <label className="label">Cache date (YYYY-MM-DD)</label>
              <input className="input" type="date" value={cacheDate} onChange={e => setCacheDate(e.target.value)} />
            </div>
          )}

          {/* Sector / Industry inputs based on mode */}
          {selectionMode !== 'all' && selectionMode !== 'manual' && selectionMode !== 'all_cache' && selectionMode !== 'all_cache_by_date' && (
            <>
              <div className="field" style={{ minWidth: 220 }}>
                <label className="label">Sector</label>
                <select className="input" value={selectedSector} onChange={e => setSelectedSector(e.target.value)}>
                  <option value="">Select sector</option>
                  {sectors.map((s, i) => (
                    <option key={i} value={s.sectorName || ''}>{s.sectorName || s.sectorId || '(unnamed)'}</option>
                  ))}
                </select>
              </div>

              {selectionMode === 'industry' && (
                <div className="field" style={{ minWidth: 220 }}>
                  <label className="label">Industry</label>
                  <select className="input" value={selectedIndustry} onChange={e => setSelectedIndustry(e.target.value)}>
                    <option value="">Select industry</option>
                    {industries.map((ind, i) => (
                      <option key={i} value={ind.industryName || ''}>{ind.industryName || ind.industryId || '(unnamed)'}</option>
                    ))}
                  </select>
                </div>
              )}
            </>
          )}

          {/* Direct select always visible for sector/industry/manual (hidden for all) */}
          {selectionMode !== 'all' && selectionMode !== 'all_cache' && selectionMode !== 'all_cache_by_date' && (
            <div className="field" style={{ minWidth: 260, position: 'relative' }}>
              <label className="label">Company (direct select)</label>
              <input
                className="input"
                placeholder="Type company name or ticker"
                value={directQuery}
                onChange={e => { setDirectQuery(e.target.value); setDirectOpen(true); }}
                onFocus={() => setDirectOpen(true)}
                onBlur={() => setTimeout(() => setDirectOpen(false), 150)}
              />
              {directQuery && (
                <button
                  type="button"
                  className="icon-button"
                  title="Clear"
                  onClick={() => setDirectQuery('')}
                  style={{ position: 'absolute', right: 34, top: 30 }}
                >
                  ✖
                </button>
              )}
              <button
                type="button"
                className="btn"
                onClick={() => addTicker(directQuery)}
                style={{ position: 'absolute', right: 0, top: 26 }}
                title="Add ticker"
              >
                Add
              </button>
              {directOpen && companySuggestions.length > 0 && (
                <div className="dropdown" style={{ position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 10, background: '#1f2937', color: '#e5e7eb', border: '1px solid #374151', borderRadius: 4, maxHeight: 220, overflowY: 'auto', boxShadow: '0 2px 12px rgba(0,0,0,0.32)', marginTop: 4 }}>
                  {companySuggestions.map((c, i) => {
                    const label = `${c.companyName || ''}${c.ticker ? `(${c.ticker})` : ''}`;
                    return (
                      <button
                        key={i}
                        type="button"
                        className="session-button"
                        style={{ width: '100%', textAlign: 'left', padding: '6px 10px', background: 'transparent', color: '#e5e7eb', borderBottom: '1px solid #374151' }}
                        onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = '#374151'; }}
                        onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; }}
                        onClick={() => { setDirectQuery(label); setDirectOpen(false); }}
                        title={label}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Ticker bucket */}
          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <label className="label">Tickers bucket</label>
            {selectionMode === 'all' || selectionMode === 'all_cache' || selectionMode === 'all_cache_by_date' ? (
              <div className="muted">
                All companies will be used. {selectionMode === 'all_cache' ? '(from SpecialMetricRankingCache)' : selectionMode === 'all_cache_by_date' ? `(from SpecialMetricRankingCache on ${cacheDate || 'selected date'})` : ''}
              </div>
            ) : tickerBucket.length === 0 ? (
              <div className="muted">No tickers selected. Choose a selection mode and/or add via direct select.</div>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {tickerBucket.map(t => (
                  <span key={t} className="tag">
                    {t}
                    <button className="icon-button" onClick={() => removeTicker(t)} title="Remove" style={{ marginLeft: 6 }}>✖</button>
                  </span>
                ))}
              </div>
            )}
            <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
              <button className="btn" onClick={clearBucket} disabled={selectionMode === 'all' || selectionMode === 'all_cache' || selectionMode === 'all_cache_by_date'} title={(selectionMode === 'all' || selectionMode === 'all_cache' || selectionMode === 'all_cache_by_date') ? 'Disabled in Use all companies mode' : undefined}>Clear bucket</button>
              <button className="btn primary" disabled={!canGenerate || loading} onClick={handleGenerate}>
                {loading ? 'Generating…' : 'Generate ranking table'}
              </button>
            </div>
          </div>
        </div>

        {error && <div className="error" style={{ marginTop: 12 }}>{error}</div>}

        {/* Results */}
        {result && (
          <div style={{ marginTop: 16 }}>
            <h3 style={{ margin: '8px 0' }}>Ranking Table</h3>
            <div style={{ overflowX: 'auto', position: 'relative' }}>
              <style>{`
                .table.pandas-like { width: 100%; border-collapse: collapse; font-size: 14px; color: #e5e7eb; }
                .table.pandas-like th, .table.pandas-like td { border: 1px solid #374151; padding: 8px 10px; }
                .table.pandas-like thead th { position: sticky; top: 0; background: #111827; color: #e5e7eb; z-index: 1; }
                .table.pandas-like tbody tr:nth-child(odd) { background: #0f172a; }
                .table.pandas-like tbody tr:nth-child(even) { background: #111827; }
                .table.pandas-like tbody tr:hover { background: #1f2937; }
                .table.pandas-like td.num, .table.pandas-like th.num { text-align: right; font-variant-numeric: tabular-nums; }
                .table.pandas-like td.center, .table.pandas-like th.center { text-align: center; }
              `}</style>
              <table className="table pandas-like" role="table" aria-label="Investment factor ranking table">
                <thead>
                  <tr>
                    <th className="center">Overall Rank</th>
                    <th>Ticker</th>
                    <th className="num">ROIC 5Y Avg</th>
                    <th className="num">Earnings Yield</th>
                    <th className="num">Intrinsic to Market Cap</th>
                  </tr>
                </thead>
                <tbody>
                  {result.table.map((row: InvestmentFactorRow, idx: number) => (
                    <tr key={idx}>
                      <td className="center">{row['Overall Rank']}</td>
                      <td>{row['Ticker']}</td>
                      <td className="num">{row['ROIC 5Y Avg']}</td>
                      <td className="num">{row['Earnings Yield']}</td>
                      <td className="num">{row['Intrinsic to Market Cap']}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {result.rejected && result.rejected.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <h4 style={{ margin: '8px 0' }}>Rejected tickers</h4>
                <div style={{ overflowX: 'auto' }}>
                  <table className="table pandas-like" role="table" aria-label="Rejected tickers">
                    <thead>
                      <tr>
                        <th>Ticker</th>
                        <th>Reasons</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.rejected.map((r, i) => (
                        <tr key={i}>
                          <td>{r.ticker}</td>
                          <td>{Object.entries(r.reasons || {}).map(([k, v]) => `${k}: ${v}`).join(', ')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
