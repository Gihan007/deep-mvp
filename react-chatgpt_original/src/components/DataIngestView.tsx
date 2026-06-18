import React, { useMemo, useRef, useState } from 'react';
import {
  ingestCsvUnstructured,
  ingestStructuredCompanyIndustrySector,
  ingestStructuredMetrics,
  createAllCompanyTenKRelationships,
  refreshSpecialMetricCacheAll,
  removeCompanyNodes,
  removeMetricNodes,
  removeIndustryNodes,
  removeSectorNodes,
  removeTenKChunkNodes,
  removeTenKChunkNodesByTickerYears,
  removeEmptyTenKChunkNodes,
  removePredictedMetricNodes,
  getNodeCounts,
  computeSpecialMetricRankings,
} from '../api/client';

// Helpers
function byNameIncludes(name: string, needle: string) {
  return name.toLowerCase().includes(needle.toLowerCase());
}

const CIS_KEY_MAP: Array<{ match: string; key: string; label: string }> = [
  { match: 'CompanyBELONG_TOIndustry.csv', key: 'ci', label: 'Company→Industry' },
  { match: 'CompanyCOMPETES_WITHCompany.csv', key: 'cc', label: 'Company COMPETES_WITH Company' },
  { match: 'IndustryBELONG_TOSector.csv', key: 'is', label: 'Industry→Sector' },
  { match: 'NodesCompany.csv', key: 'c', label: 'Nodes Company' },
  { match: 'NodesIndustry.csv', key: 'i', label: 'Nodes Industry' },
  { match: 'NodesSector.csv', key: 's', label: 'Nodes Sector' },
];

// Only mf/mt/vs are supported by backend at present
const METRIC_KEY_MAP: Array<{ match: string; key: string; label: string; supported: boolean }> = [
  { match: 'MasterFinancials', key: 'mf', label: 'MasterFinancials', supported: true },
  { match: 'MultiplesTable', key: 'mt', label: 'MultiplesTable', supported: true },
  { match: 'ValuationSummary', key: 'vs', label: 'ValuationSummary', supported: true },
  { match: 'BalanceSheetExpanded', key: 'bs', label: 'BalanceSheetExpanded (unsupported)', supported: false },
  { match: 'CashFlowExpanded', key: 'cf', label: 'CashFlowExpanded (unsupported)', supported: false },
  { match: 'FinancialStatments', key: 'fs', label: 'FinancialStatments (unsupported)', supported: false },
  { match: 'IncomeStatementExpanded', key: 'is', label: 'IncomeStatementExpanded (unsupported)', supported: false },
];

function extractTickerFromPath(file: File) {
  // Try from filename prefix before first underscore
  const name = file.name;
  const idx = name.indexOf('_');
  if (idx > 0) return name.slice(0, idx);
  // Try from webkitRelativePath folder
  // @ts-ignore
  const rel: string = file.webkitRelativePath || '';
  if (rel) {
    const parts = rel.split('/');
    if (parts.length > 1) return parts[0];
  }
  return '';
}

export default function DataIngestView() {
  // Ingest controls
  const [mode, setMode] = useState<
    'csv_unstructured' | 'csv_structured_company_industry_sector_data' | 'csv_structured_metrics_data' | 'create_all_company_tenk_relationships' | 'update_special_metric_cache_node' | 'update_special_metric_ranking_cache_node'
  >('csv_unstructured');
  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<string>('');
  const [running, setRunning] = useState(false);

  // Metrics-specific
  const [tickerOverrides, setTickerOverrides] = useState<Record<string, string>>({});

  // Removal controls
  const [removalMode, setRemovalMode] = useState<
    'none' | 'remove_company' | 'remove_metric' | 'remove_predicted_metric' | 'remove_industry' | 'remove_sector' | 'remove_tenk_all' | 'remove_tenk_specific' | 'remove_tenk_empty'
  >('none');
  const [minProps, setMinProps] = useState<number>(6);

  // Read controls
  const [readMode, setReadMode] = useState<'none' | 'node_counts'>('none');
  const [readStatus, setReadStatus] = useState<string>('');
  const [readRunning, setReadRunning] = useState(false);
  const [nodeCounts, setNodeCounts] = useState<Array<{ node_name: string; count: number }>>([]);
  type SpecificRow = { ticker: string; yearsText: string };
  const [specificRows, setSpecificRows] = useState<SpecificRow[]>([{ ticker: '', yearsText: '' }]);
  const [removalStatus, setRemovalStatus] = useState<string>('');
  const [removalRunning, setRemovalRunning] = useState(false);

  const inputRef = useRef<HTMLInputElement | null>(null);

  const onPickFolder = () => {
    inputRef.current?.click();
  };

  const onFilesSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const list = Array.from(e.target.files || []);
    if (!list.length) return;
    setFiles(prev => [...prev, ...list]);
    e.currentTarget.value = '';
  };

  const removeFile = (idx: number) => setFiles(prev => prev.filter((_, i) => i !== idx));
  const clearAll = () => {
    setFiles([]);
    setStatus('');
  };

  // Build previews/mappings per ingest mode
  const cisPairs = useMemo(() => {
    if (mode !== 'csv_structured_company_industry_sector_data') return [] as Array<{ file: File; key: string; label: string }>;
    const out: Array<{ file: File; key: string; label: string }> = [];
    for (const f of files) {
      const matched = CIS_KEY_MAP.find(m => byNameIncludes(f.name, m.match));
      if (matched) out.push({ file: f, key: matched.key, label: matched.label });
    }
    return out;
  }, [mode, files]);

  const metricTriples = useMemo(() => {
    if (mode !== 'csv_structured_metrics_data') return [] as Array<{ file: File; key: string; ticker: string; supported: boolean; label: string }>;
    const out: Array<{ file: File; key: string; ticker: string; supported: boolean; label: string }> = [];
    for (const f of files) {
      const map = METRIC_KEY_MAP.find(m => byNameIncludes(f.name, m.match));
      if (!map) continue;
      const origTicker = extractTickerFromPath(f);
      const override = tickerOverrides[f.name];
      const ticker = (override ?? origTicker).toUpperCase();
      out.push({ file: f, key: map.key, ticker, supported: map.supported, label: map.label });
    }
    return out;
  }, [mode, files, tickerOverrides]);

  const unstructuredCsvs = useMemo(() => {
    if (mode !== 'csv_unstructured') return [] as File[];
    return files.filter(f => f.name.toLowerCase().endsWith('.csv'));
  }, [mode, files]);

  const onSubmit = async () => {
    if (running) return;
    setRunning(true);
    setStatus('');

    try {
      if (mode === 'csv_structured_company_industry_sector_data') {
        if (cisPairs.length === 0) {
          setStatus('No recognized CIS files selected.');
          return;
        }
        const cisFiles = cisPairs.map(p => p.file);
        const keys = cisPairs.map(p => p.key);
        const res = await ingestStructuredCompanyIndustrySector(cisFiles, keys);
        setStatus(`Structured CIS ingest done: ${res?.message || 'ok'}`);
      } else if (mode === 'csv_unstructured') {
        if (unstructuredCsvs.length === 0) {
          setStatus('No CSV files selected.');
          return;
        }
        let ok = 0, fail = 0;
        for (const f of unstructuredCsvs) {
          try {
            await ingestCsvUnstructured(f);
            ok += 1;
            setStatus(`Ingested ${ok}/${unstructuredCsvs.length} (fail ${fail})`);
          } catch (e) {
            fail += 1;
            setStatus(`Ingested ${ok}/${unstructuredCsvs.length} (fail ${fail})`);
          }
        }
        setStatus(`Unstructured ingest complete. Success ${ok}, Failed ${fail}`);
      } else if (mode === 'csv_structured_metrics_data') {
        if (metricTriples.length === 0) {
          setStatus('No recognized metrics files selected.');
          return;
        }
        let ok = 0, fail = 0, skipped = 0;
        for (const t of metricTriples) {
          if (!t.supported) { skipped += 1; continue; }
          if (!t.ticker) { fail += 1; continue; }
          try {
            await ingestStructuredMetrics(t.file, t.key, t.ticker);
            ok += 1;
            setStatus(`Metrics ${ok} ok, ${fail} failed, ${skipped} skipped`);
          } catch (e) {
            fail += 1;
            setStatus(`Metrics ${ok} ok, ${fail} failed, ${skipped} skipped`);
          }
        }
        setStatus(`Structured metrics ingest complete. Success ${ok}, Failed ${fail}, Skipped ${skipped}`);
      } else if (mode === 'create_all_company_tenk_relationships') {
        const res = await createAllCompanyTenKRelationships();
        setStatus(res?.message || 'Relationships creation requested');
      } else if (mode === 'update_special_metric_cache_node') {
        const res = await refreshSpecialMetricCacheAll();
        const upd = res?.updated_count ?? 0;
        const fail = res?.failed_count ?? 0;
        const total = res?.tickers_count ?? 'n/a';
        setStatus(`SpecialMetricCache refresh: updated ${upd}/${total}, failed ${fail}`);
      } else if (mode === 'update_special_metric_ranking_cache_node') {
        const res = await computeSpecialMetricRankings();
        const successCount = res?.count ?? 0;
        const rejectedCount = Array.isArray(res?.rejected) ? res.rejected.length : (res?.rejected_count ?? 0);
        setStatus(`SpecialMetricRankingCache updated: success ${successCount}, rejected ${rejectedCount}`);
      }
    } catch (e: any) {
      setStatus(`Error: ${e?.message || e}`);
    } finally {
      setRunning(false);
    }
  };

  // Removal handlers
  const addSpecificRow = () => setSpecificRows(prev => [...prev, { ticker: '', yearsText: '' }]);
  const removeSpecificRow = (idx: number) => setSpecificRows(prev => prev.filter((_, i) => i !== idx));
  const updateSpecificRow = (idx: number, patch: Partial<SpecificRow>) =>
    setSpecificRows(prev => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));

  const onRunRemoval = async () => {
    if (removalRunning) return;
    setRemovalRunning(true);
    setRemovalStatus('');
    try {
      if (removalMode === 'remove_company') {
        const res = await removeCompanyNodes();
        setRemovalStatus(`${res.message} (deleted: ${res.nodes_deleted ?? 'n/a'})`);
      } else if (removalMode === 'remove_metric') {
        const res = await removeMetricNodes();
        setRemovalStatus(`${res.message} (deleted: ${res.nodes_deleted ?? 'n/a'})`);
      } else if (removalMode === 'remove_predicted_metric') {
        const res = await removePredictedMetricNodes();
        setRemovalStatus(`${res.message} (deleted: ${res.nodes_deleted ?? 'n/a'})`);
      } else if (removalMode === 'remove_industry') {
        const res = await removeIndustryNodes();
        setRemovalStatus(`${res.message} (deleted: ${res.nodes_deleted ?? 'n/a'})`);
      } else if (removalMode === 'remove_sector') {
        const res = await removeSectorNodes();
        setRemovalStatus(`${res.message} (deleted: ${res.nodes_deleted ?? 'n/a'})`);
      } else if (removalMode === 'remove_tenk_all') {
        const res = await removeTenKChunkNodes();
        setRemovalStatus(`${res.message} (deleted: ${res.nodes_deleted ?? 'n/a'})`);
      } else if (removalMode === 'remove_tenk_specific') {
        // Build payload
        const items = specificRows
          .map(r => ({
            ticker: (r.ticker || '').trim().toUpperCase(),
            years: (r.yearsText || '')
              .split(/[\,\s]+/)
              .map(s => s.trim())
              .filter(Boolean)
              .map(n => parseInt(n, 10))
              .filter(n => !Number.isNaN(n)),
          }))
          .filter(it => it.ticker && it.years.length);
        if (!items.length) {
          setRemovalStatus('Please add at least one ticker with years.');
          return;
        }
        const res = await removeTenKChunkNodesByTickerYears(items);
        setRemovalStatus(`${res.message} (deleted: ${res.nodes_deleted ?? 'n/a'})`);
      } else if (removalMode === 'remove_tenk_empty') {
        const res = await removeEmptyTenKChunkNodes(minProps || 0);
        const deleted = res.deleted_count ?? 'n/a';
        const valid = res.valid_tenkchunk_count ?? 'n/a';
        setRemovalStatus(`${res.message} (deleted: ${deleted}, valid remaining: ${valid})`);
      } else {
        setRemovalStatus('Select a remove action first.');
      }
    } catch (e: any) {
      setRemovalStatus(`Error: ${e?.message || e}`);
    } finally {
      setRemovalRunning(false);
    }
  };

  return (
    <div className="chat-view">
      <div className="chat-header">
        <div className="title">Manage Neo4j</div>
      </div>

      <div className="composer" style={{ borderTop: 'none' }}>
        {/* Ingest section */}
        <div className="section" style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 12, boxShadow: '0 6px 16px var(--shadow)', marginBottom: 12, overflow: 'hidden' }}>
          <div className="section-title">Data ingest to Neo4j</div>
          <div style={{ padding: 12 }}>
        <div className="field">
          <label className="label">Data ingest to Neo4j</label>
          <select className="input" value={mode} onChange={e => setMode(e.target.value as any)}>
            <option value="csv_unstructured">csv_unstructured (10K data)</option>
            <option value="csv_structured_company_industry_sector_data">csv_structured_company_industry_sector_data</option>
            <option value="csv_structured_metrics_data">csv_structured_metrics_data</option>
            <option value="create_all_company_tenk_relationships">create_all_company_tenk_relationships</option>
            <option value="update_special_metric_cache_node">update_SpecilMetricCache_node</option>
            <option value="update_special_metric_ranking_cache_node">update_SpecialMetricRankingCache_node</option>
          </select>
        </div>

        {!(mode === 'create_all_company_tenk_relationships' || mode === 'update_special_metric_cache_node' || mode === 'update_special_metric_ranking_cache_node') && (
          <div className="field">
            <label className="label">Select folder (accepts nested folders)</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                ref={inputRef}
                type="file"
                multiple
                //@ts-ignore
                webkitdirectory="true"
                //@ts-ignore
                directory="true"
                style={{ display: 'none' }}
                onChange={onFilesSelected}
                accept={mode === 'csv_unstructured' ? '.csv' : undefined}
              />
              <button className="btn" onClick={onPickFolder}>Choose folder…</button>
              <button className="btn" onClick={clearAll}>Clear</button>
            </div>
          </div>
        )}

        {/* Ingest lists per mode */}
        {mode === 'csv_structured_company_industry_sector_data' && (
          <div className="field">
            <label className="label">Detected files (mapped to required keys)</label>
            {cisPairs.length === 0 ? (
              <div className="muted">No recognized files yet. Expected any of: {CIS_KEY_MAP.map(m => m.match).join(', ')}</div>
            ) : (
              <ul className="path-list">
                {cisPairs.map((p, idx) => (
                  <li key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <code>{p.file.name}</code>
                    <span className="meta-pill">key: {p.key}</span>
                    <span className="meta-pill">{p.label}</span>
                    <button className="icon-button" onClick={() => removeFile(files.indexOf(p.file))}>✖</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {mode === 'csv_unstructured' && (
          <div className="field">
            <label className="label">Selected CSV files</label>
            {unstructuredCsvs.length === 0 ? (
              <div className="muted">No CSVs selected.</div>
            ) : (
              <ul className="path-list">
                {unstructuredCsvs.map((f, idx) => (
                  <li key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <code>{f.name}</code>
                    <button className="icon-button" onClick={() => removeFile(files.indexOf(f))}>✖</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {mode === 'csv_structured_metrics_data' && (
          <div className="field">
            <label className="label">Detected metric files (mf/mt/vs supported)</label>
            {metricTriples.length === 0 ? (
              <div className="muted">No recognized metrics files yet. Supported patterns include: MasterFinancials, MultiplesTable, ValuationSummary.</div>
            ) : (
              <ul className="path-list">
                {metricTriples.map((t, idx) => (
                  <li key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <code>{t.file.name}</code>
                    <span className="meta-pill">key: {t.key}{!t.supported ? ' (unsupported)' : ''}</span>
                    <label className="label" style={{ margin: 0 }}>Ticker:</label>
                    <input
                      className="input"
                      style={{ maxWidth: 120 }}
                      value={tickerOverrides[t.file.name] ?? t.ticker}
                      onChange={e => setTickerOverrides(prev => ({ ...prev, [t.file.name]: e.target.value }))}
                    />
                    <button className="icon-button" onClick={() => removeFile(files.indexOf(t.file))}>✖</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
          <button className="btn primary" style={{ minWidth: 160, height: 36, whiteSpace: 'nowrap' }} onClick={onSubmit} disabled={running}>
            {mode === 'create_all_company_tenk_relationships'
              ? 'Create relationships'
              : mode === 'update_special_metric_cache_node'
              ? 'Update SpecialMetricCache'
              : mode === 'update_special_metric_ranking_cache_node'
              ? 'Update SpecialMetricRankingCache'
              : running
              ? 'Submitting…'
              : 'Submit'}
          </button>
          {status && <span className="muted">{status}</span>}
        </div>
          </div>
        </div>

        {/* Read section moved to second */}
        <div className="section" style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 12, boxShadow: '0 6px 16px var(--shadow)', marginTop: 12, overflow: 'hidden' }}>
          <div className="section-title">Read Neo4j</div>
          <div style={{ padding: 12 }}>
            <div className="field">
              <label className="label">Action</label>
              <select
                className="input"
                value={readMode}
                onChange={e => {
                  const v = e.target.value as any;
                  setReadMode(v);
                  // Clear previous results/status when action changes
                  setReadStatus('');
                  setNodeCounts([]);
                }}
              >
                <option value="none">Select action…</option>
                <option value="node_counts">Get node counts</option>
              </select>
            </div>

            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
              <button
                className="btn primary"
                style={{ minWidth: 160, height: 36, whiteSpace: 'nowrap' }}
                onClick={async () => {
                  if (readRunning) return;
                  setReadRunning(true);
                  setReadStatus('');
                  setNodeCounts([]);
                  try {
                    if (readMode === 'node_counts') {
                      const rows = await getNodeCounts();
                      setNodeCounts(rows);
                      setReadStatus(`Fetched ${rows.length} label counts`);
                    } else {
                      setReadStatus('Select a read action first.');
                    }
                  } catch (e: any) {
                    setReadStatus(`Error: ${e?.message || e}`);
                  } finally {
                    setReadRunning(false);
                  }
                }}
                disabled={readRunning || readMode === 'none'}
              >
                {readRunning ? 'Running…' : 'Run'}
              </button>
              {readStatus && <span className="muted">{readStatus}</span>}
            </div>

            {nodeCounts.length > 0 && (
              <div className="field" style={{ marginTop: 8 }}>
                <label className="label">Node counts</label>
                <div style={{ overflow: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 10 }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid var(--border)' }}>Node label</th>
                        <th style={{ textAlign: 'right', padding: '8px 10px', borderBottom: '1px solid var(--border)' }}>Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {nodeCounts.map((r, i) => (
                        <tr key={i}>
                          <td style={{ padding: '8px 10px', borderBottom: '1px dashed var(--border)' }}>{r.node_name}</td>
                          <td style={{ padding: '8px 10px', textAlign: 'right', borderBottom: '1px dashed var(--border)' }}>{r.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Remove section moved to third */}
        <div className="section" style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 12, boxShadow: '0 6px 16px var(--shadow)', marginTop: 12, overflow: 'hidden' }}>
          <div className="section-title">Remove Neo4j Nodes</div>
          <div style={{ padding: 12 }}>

        {/* Removal section */}
        <div className="field">
          <label className="label">Action</label>
          <select className="input" value={removalMode} onChange={e => setRemovalMode(e.target.value as any)}>
            <option value="none">Select action…</option>
            <option value="remove_company">Remove Company nodes</option>
            <option value="remove_metric">Remove Metric nodes</option>
            <option value="remove_predicted_metric">Remove PredictedMetric nodes</option>
            <option value="remove_industry">Remove Industry nodes</option>
            <option value="remove_sector">Remove Sector nodes</option>
            <option value="remove_tenk_all">Remove TenKChunk nodes (ALL)</option>
            <option value="remove_tenk_specific">Remove TenKChunk nodes (specific ticker + years)</option>
            <option value="remove_tenk_empty">Remove TenKChunk empty nodes (min props)</option>
          </select>
        </div>

        {removalMode === 'remove_tenk_specific' && (
          <div className="field">
            <label className="label">Specify tickers and years</label>
            <ul className="path-list">
              {specificRows.map((row, idx) => (
                <li key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <label className="label" style={{ margin: 0 }}>Ticker</label>
                  <input
                    className="input"
                    style={{ maxWidth: 120 }}
                    value={row.ticker}
                    onChange={e => updateSpecificRow(idx, { ticker: e.target.value })}
                    placeholder="WMT"
                  />
                  <label className="label" style={{ margin: 0 }}>Years (comma/space separated)</label>
                  <input
                    className="input"
                    style={{ maxWidth: 260 }}
                    value={row.yearsText}
                    onChange={e => updateSpecificRow(idx, { yearsText: e.target.value })}
                    placeholder="2011, 2012, 2023"
                  />
                  <button className="icon-button" onClick={() => removeSpecificRow(idx)}>✖</button>
                </li>
              ))}
            </ul>
            <button className="btn" onClick={addSpecificRow}>+ Add row</button>
          </div>
        )}

        {removalMode === 'remove_tenk_empty' && (
          <div className="field">
            <label className="label">Minimum properties (excluding ticker/year)</label>
            <input
              className="input"
              style={{ maxWidth: 140 }}
              type="number"
              min={0}
              value={minProps}
              onChange={e => setMinProps(parseInt(e.target.value || '0', 10))}
            />
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
          <button className="btn danger" style={{ minWidth: 160, height: 36, whiteSpace: 'nowrap' }} onClick={onRunRemoval} disabled={removalRunning || removalMode === 'none'}>
            {removalRunning ? 'Running…' : 'Run removal'}
          </button>
          {removalStatus && <span className="muted">{removalStatus}</span>}
        </div>
          </div>
        </div>
      </div>
    </div>
  );
}
