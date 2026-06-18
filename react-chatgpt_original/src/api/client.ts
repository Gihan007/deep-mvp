import axios from 'axios';
import type {
  ChatQARequest,
  ChatQAResponse,
  SessionsResponse,
  SessionResponse,
  DeleteResponse,
  StreamDoneEvent,
  ReportRequest,
  Sector,
  Industry,
  Company,
  GraphCypherResponse,
} from './types';

// Axios instance (no baseURL needed because Vite proxy forwards /api -> http://localhost:8080)
const http = axios.create({
  headers: {
    'Content-Type': 'application/json',
  },
});

// POST /api/qa_bot (standard)
export async function sendChat(payload: ChatQARequest) {
  const { data } = await http.post<ChatQAResponse>('/api/qa_bot', payload);
  return data;
}

// POST /api/deep_qa_bot (deep search)
export async function sendDeepChat(payload: ChatQARequest) {
  const { data } = await http.post<ChatQAResponse>('/api/deep_qa_bot', payload);
  return data;
}

// GET /api/sessions
export async function listSessions() {
  const { data } = await http.get<SessionsResponse>('/api/sessions');
  return data;
}

// GET /api/sessions/{id}
export async function getSession(sessionId: string) {
  const { data } = await http.get<SessionResponse>(`/api/sessions/${encodeURIComponent(sessionId)}`);
  return data;
}

// DELETE /api/sessions/{id}
export async function deleteSession(sessionId: string) {
  const { data } = await http.delete<DeleteResponse>(`/api/sessions/${encodeURIComponent(sessionId)}`);
  return data;
}

// DELETE /api/sessions
export async function clearAllSessions() {
  const { data } = await http.delete<DeleteResponse>('/api/sessions');
  return data;
}

// Report tab: session APIs backed by /api/sessions_report
export async function listReportSessions() {
  const { data } = await http.get<SessionsResponse>('/api/sessions_report');
  return data;
}

export async function getReportSession(sessionId: string) {
  const { data } = await http.get<SessionResponse>(`/api/sessions_report/${encodeURIComponent(sessionId)}`);
  return data;
}

export async function deleteReportSession(sessionId: string) {
  const { data } = await http.delete<DeleteResponse>(`/api/sessions_report/${encodeURIComponent(sessionId)}`);
  return data;
}

export async function clearAllReportSessions() {
  const { data } = await http.delete<DeleteResponse>('/api/sessions_report');
  return data;
}

/* Graph update sessions (Neo4j) */
export async function listGraphUpdateSessions() {
  const { data } = await http.get<SessionsResponse>('/api/sessions_update_neo4j');
  return data;
}
export async function getGraphUpdateSession(sessionId: string) {
  const { data } = await http.get<SessionResponse>(`/api/sessions_update_neo4j/${encodeURIComponent(sessionId)}`);
  return data;
}
export async function deleteGraphUpdateSession(sessionId: string) {
  // Note: backend route has a typo: sessions_upate_neo4j
  const { data } = await http.delete<DeleteResponse>(`/api/sessions_upate_neo4j/${encodeURIComponent(sessionId)}`);
  return data;
}
export async function clearAllGraphUpdateSessions() {
  const { data } = await http.delete<DeleteResponse>('/api/sessions_update_neo4j');
  return data;
}

/**
 * Stream chat via SSE from POST /api/qa_bot_stream.
 * Calls handlers.onToken for each assistant text chunk.
 * Resolves when stream ends or is aborted.
 */
export async function streamChat(
  payload: ChatQARequest,
  handlers: {
    onToken: (text: string) => void;
    onFinal?: (evt: StreamDoneEvent) => void;
    onDone?: () => void;
    onError?: (err: any) => void;
    signal?: AbortSignal;
  }
) {
  const res = await fetch('/api/qa_bot_stream', {
    method: 'POST',
    headers: {
      'Accept': 'text/event-stream',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal: handlers.signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Streaming request failed: ${res.status} ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line
      const frames = buffer.split('\n\n');
      buffer = frames.pop() || '';

      for (const frame of frames) {
        // Extract the combined "data:" payload (ignore other SSE fields)
        let dataPayload = '';
        const lines = frame.split('\n');
        for (const l of lines) {
          if (l.startsWith('data:')) {
            const part = l.slice(5).trim();
            dataPayload += (dataPayload ? '\n' : '') + part;
          }
        }
        if (!dataPayload) continue;

        // Server emits JSON events; we only care about token/done/error
        try {
          const evt = JSON.parse(dataPayload);
          if (evt.type === 'token' && evt.content) {
            handlers.onToken(evt.content);
          } else if (evt.type === 'done') {
            if (handlers.onFinal) handlers.onFinal(evt);
            if (handlers.onDone) handlers.onDone();
          } else if (evt.type === 'error') {
            if (handlers.onError) handlers.onError(evt.error || 'stream error');
          }
        } catch {
          // Ignore non-JSON data frames
        }
      }
    }
    if (handlers.onDone) handlers.onDone();
  } catch (err: any) {
    if (err?.name === 'AbortError') {
      // aborted by caller
      return;
    }
    if (handlers.onError) handlers.onError(err);
  } finally {
    try { reader.releaseLock(); } catch {}
  }
}

/* ============== Graph Update (Neo4j) endpoints ============== */
export async function sendGraphUpdate(payload: { question: string; session_id?: string | null }) {
  const { data } = await http.post<ChatQAResponse>('/api/update_graph/execute', payload);
  return data;
}

export async function streamGraphUpdate(
  payload: { question: string; session_id?: string | null },
  handlers: {
    onToken: (text: string) => void;
    onFinal?: (evt: any) => void;
    onDone?: () => void;
    onError?: (err: any) => void;
    signal?: AbortSignal;
  }
) {
  const res = await fetch('/api/update_graph/stream', {
    method: 'POST',
    headers: {
      'Accept': 'text/event-stream',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal: handlers.signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Streaming request failed: ${res.status} ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const frames = buffer.split('\n\n');
      buffer = frames.pop() || '';

      for (const frame of frames) {
        let dataPayload = '';
        const lines = frame.split('\n');
        for (const l of lines) {
          if (l.startsWith('data:')) {
            const part = l.slice(5).trim();
            dataPayload += (dataPayload ? '\n' : '') + part;
          }
        }
        if (!dataPayload) continue;

        try {
          const evt = JSON.parse(dataPayload);
          if (evt.type === 'token' && evt.content) {
            handlers.onToken(evt.content);
          } else if (evt.type === 'done') {
            if (handlers.onFinal) handlers.onFinal(evt);
            if (handlers.onDone) handlers.onDone();
          } else if (evt.type === 'error') {
            if (handlers.onError) handlers.onError(evt.error || 'stream error');
          }
        } catch {
          // ignore malformed frames
        }
      }
    }
    if (handlers.onDone) handlers.onDone();
  } catch (err: any) {
    if (err?.name === 'AbortError') return;
    if (handlers.onError) handlers.onError(err);
  } finally {
    try { reader.releaseLock(); } catch {}
  }
}


/* ============== Graph DB helper endpoints ============== */

// GET /api/graphdb/companies (preferred for full list with ticker filtering in backend)
export async function listCompanies() {
  const { data } = await http.get<Company[]>(`/api/graphdb/companies`);
  return data;
}

// GET /api/graphdb/sectors
export async function listSectors() {
  const { data } = await http.get<Sector[]>('/api/graphdb/sectors');
  return data;
}

// GET /api/graphdb/industries_when_sector_given?sectorName=...
export async function listIndustriesBySector(params: { sectorId?: string; sectorName?: string }) {
  const qs = new URLSearchParams();
  if (params.sectorId) qs.append('sectorId', params.sectorId);
  if (params.sectorName) qs.append('sectorName', params.sectorName);
  const { data } = await http.get<Industry[]>(`/api/graphdb/industries_when_sector_given?${qs.toString()}`);
  return data;
}

// GET /api/graphdb/companies_when_industry_given?industryName=...
export async function listCompaniesByIndustry(params: { industryId?: string; industryName?: string }) {
  const qs = new URLSearchParams();
  if (params.industryId) qs.append('industryId', params.industryId);
  if (params.industryName) qs.append('industryName', params.industryName);
  const { data } = await http.get<Company[]>(`/api/graphdb/companies_when_industry_given?${qs.toString()}`);
  return data;
}

// POST /api/graphdb/cypher to list all industries
export async function listAllIndustries() {
  const { data } = await http.post<GraphCypherResponse>('/api/graphdb/cypher', {
    query: `
      MATCH (i:Industry)
      RETURN properties(i) AS industry
      ORDER BY industry.industryName
    `,
    parameters: {},
    mode: 'read',
  });
  const industries: Industry[] = (data.records || []).map((r: any) => r.industry || r);
  return industries;
}

// POST /api/graphdb/cypher to list all companies (for direct select)
export async function listAllCompanies() {
  const { data } = await http.post<GraphCypherResponse>('/api/graphdb/cypher', {
    query: `
      MATCH (c:Company)
      RETURN properties(c) AS company
      ORDER BY company.companyName
    `,
    parameters: {},
    mode: 'read',
  });
  const companies: Company[] = (data.records || []).map((r: any) => r.company || r);
  return companies;
}

/* ============== Special Metrics endpoints ============== */
export async function getInvestmentFactorRankingTable(tickers: string[]) {
  const { data } = await http.post('/api/special_metrics/investment_factor_ranking_table', { tickers });
  return data;
}

export async function refreshSpecialMetricCacheAll({ summary = true }: { summary?: boolean } = { summary: true }) {
  const url = `/api/special_metrics/refresh_special_metric_cache_all?summary=${summary ? 'true' : 'false'}`;
  const res = await fetch(url, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Refresh SpecialMetricCache failed: ${res.status}`);
  return await res.json();
}

export async function computeSpecialMetricRankings() {
  const res = await fetch('/api/special_metrics/compute_rankings', { method: 'POST' });
  if (!res.ok) throw new Error(`Compute SpecialMetricRanking failed: ${res.status}`);
  return await res.json();
}

export async function getSpecialMetricRankingFromCacheAll() {
  const res = await fetch('/api/special_metrics/investment_factor_ranking_table_for_all_companies', { method: 'POST' });
  if (!res.ok) throw new Error(`Fetch SpecialMetricRankingCache failed: ${res.status}`);
  return await res.json();
}

export async function getSpecialMetricRankingFromCacheByDate(cache_date: string) {
  const url = `/api/special_metrics/investment_factor_ranking_table_for_all_companies/${encodeURIComponent(cache_date)}`;
  const res = await fetch(url, { method: 'GET' });
  if (!res.ok) throw new Error(`Fetch SpecialMetricRankingCache by date failed: ${res.status}`);
  return await res.json();
}

/* ============== Data Ingest to Graph DB endpoints ============== */
export async function ingestCsvUnstructured(file: File) {
  const form = new FormData();
  form.append('file', file, file.name);
  const res = await fetch('/api/data_inject_graph_db/csv_unstructured', {
    method: 'POST',
    body: form,
  });
  if (!res.ok) throw new Error(`Unstructured ingest failed: ${res.status}`);
  return await res.json();
}

export async function ingestStructuredCompanyIndustrySector(files: File[], keys: string[]) {
  const form = new FormData();
  files.forEach((f, i) => form.append('files', f, f.name));
  keys.forEach((k) => form.append('keys', k));
  const res = await fetch('/api/data_inject_graph_db/csv_structured_company_industry_sector_data', {
    method: 'POST',
    body: form,
  });
  if (!res.ok) throw new Error(`Structured CIS ingest failed: ${res.status}`);
  return await res.json();
}

export async function ingestStructuredMetrics(file: File, key: string, ticker: string) {
  const form = new FormData();
  form.append('file', file, file.name);
  form.append('key', key);
  form.append('ticker', ticker);
  const res = await fetch('/api/data_inject_graph_db/csv_structured_metrics_data', {
    method: 'POST',
    body: form,
  });
  if (!res.ok) throw new Error(`Structured metrics ingest failed: ${res.status}`);
  return await res.json();
}

export async function createAllCompanyTenKRelationships() {
  const res = await fetch('/api/data_inject_graph_db/create_all_company_tenk_relationships', {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Create relationships failed: ${res.status}`);
  return await res.json();
}

/* ============== Manage Neo4j: Removal endpoints ============== */
export async function removeCompanyNodes() {
  const res = await fetch('/api/graphdb/remove/company_nodes', { method: 'DELETE' });
  if (!res.ok) throw new Error(`Remove Company nodes failed: ${res.status}`);
  return await res.json();
}
export async function removeMetricNodes() {
  const res = await fetch('/api/graphdb/remove/metric_nodes', { method: 'DELETE' });
  if (!res.ok) throw new Error(`Remove Metric nodes failed: ${res.status}`);
  return await res.json();
}
export async function removeIndustryNodes() {
  const res = await fetch('/api/graphdb/remove/industry_nodes', { method: 'DELETE' });
  if (!res.ok) throw new Error(`Remove Industry nodes failed: ${res.status}`);
  return await res.json();
}
export async function removeSectorNodes() {
  const res = await fetch('/api/graphdb/remove/sector_nodes', { method: 'DELETE' });
  if (!res.ok) throw new Error(`Remove Sector nodes failed: ${res.status}`);
  return await res.json();
}
export async function removeTenKChunkNodes() {
  const res = await fetch('/api/graphdb/remove/tenkchunk_nodes', { method: 'DELETE' });
  if (!res.ok) throw new Error(`Remove TenKChunk nodes failed: ${res.status}`);
  return await res.json();
}
export async function removeTenKChunkNodesByTickerYears(items: Array<{ ticker: string; years: number[] }>) {
  const res = await fetch('/api/graphdb/remove/tenkchunk_nodes_by_ticker_years', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items }),
  });
  if (!res.ok) throw new Error(`Remove specific TenKChunk nodes failed: ${res.status}`);
  return await res.json();
}
export async function removeEmptyTenKChunkNodes(min_properties: number = 6) {
  const res = await fetch('/api/graphdb/remove/tenkchunk_empty_nodes', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ min_properties }),
  });
  if (!res.ok) throw new Error(`Remove empty TenKChunk nodes failed: ${res.status}`);
  return await res.json();
}
export async function removePredictedMetricNodes() {
  const res = await fetch('/api/graphdb/remove/predicted_metric_nodes', { method: 'DELETE' });
  if (!res.ok) throw new Error(`Remove PredictedMetric nodes failed: ${res.status}`);
  return await res.json();
}

/* ============== Read Neo4j endpoints ============== */
export async function getNodeCounts(): Promise<Array<{ node_name: string; count: number }>> {
  const res = await fetch('/api/graphdb/node_counts');
  if (!res.ok) throw new Error(`Get node counts failed: ${res.status}`);
  return await res.json();
}

/* ============== Dedicated Report Generation endpoints ============== */

// POST /api/deep_qa_bot_report (non-streaming)
export async function sendReport(payload: ReportRequest) {
  const { data } = await http.post<ChatQAResponse>('/api/deep_qa_bot_report', payload);
  return data;
}

// POST /api/deep_qa_bot_stream_report (SSE streaming)
export async function streamReport(
  payload: ReportRequest,
  handlers: {
    onToken: (text: string) => void;
    onFinal?: (evt: StreamDoneEvent) => void;
    onDone?: () => void;
    onError?: (err: any) => void;
    signal?: AbortSignal;
  }
) {
  const res = await fetch('/api/deep_qa_bot_stream_report', {
    method: 'POST',
    headers: {
      'Accept': 'text/event-stream',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal: handlers.signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Streaming request failed: ${res.status} ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const frames = buffer.split('\n\n');
      buffer = frames.pop() || '';

      for (const frame of frames) {
        let dataPayload = '';
        const lines = frame.split('\n');
        for (const l of lines) {
          if (l.startsWith('data:')) {
            const part = l.slice(5).trim();
            dataPayload += (dataPayload ? '\n' : '') + part;
          }
        }
        if (!dataPayload) continue;

        try {
          const evt = JSON.parse(dataPayload);
          if (evt.type === 'token' && evt.content) {
            handlers.onToken(evt.content);
          } else if (evt.type === 'done') {
            if (handlers.onFinal) handlers.onFinal(evt);
            if (handlers.onDone) handlers.onDone();
          } else if (evt.type === 'error') {
            if (handlers.onError) handlers.onError(evt.error || 'stream error');
          }
        } catch {
          // ignore malformed frames
        }
      }
    }
    if (handlers.onDone) handlers.onDone();
  } catch (err: any) {
    if (err?.name === 'AbortError') return;
    if (handlers.onError) handlers.onError(err);
  } finally {
    try { reader.releaseLock(); } catch {}
  }
}

/**
 * Stream chat via SSE from POST /api/deep_qa_bot_stream (deep search).
 */
export async function streamDeepChat(
  payload: ChatQARequest,
  handlers: {
    onToken: (text: string) => void;
    onFinal?: (evt: StreamDoneEvent) => void;
    onDone?: () => void;
    onError?: (err: any) => void;
    signal?: AbortSignal;
  }
) {
  const res = await fetch('/api/deep_qa_bot_stream', {
    method: 'POST',
    headers: {
      'Accept': 'text/event-stream',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal: handlers.signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Streaming request failed: ${res.status} ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const frames = buffer.split('\n\n');
      buffer = frames.pop() || '';

      for (const frame of frames) {
        let dataPayload = '';
        const lines = frame.split('\n');
        for (const l of lines) {
          if (l.startsWith('data:')) {
            const part = l.slice(5).trim();
            dataPayload += (dataPayload ? '\n' : '') + part;
          }
        }
        if (!dataPayload) continue;

        try {
          const evt = JSON.parse(dataPayload);
          if (evt.type === 'token' && evt.content) {
            handlers.onToken(evt.content);
          } else if (evt.type === 'done') {
            if (handlers.onFinal) handlers.onFinal(evt);
            if (handlers.onDone) handlers.onDone();
          } else if (evt.type === 'error') {
            if (handlers.onError) handlers.onError(evt.error || 'stream error');
          }
        } catch {
          // Ignore non-JSON data frames
        }
      }
    }
    if (handlers.onDone) handlers.onDone();
  } catch (err: any) {
    if (err?.name === 'AbortError') return;
    if (handlers.onError) handlers.onError(err);
  } finally {
    try { reader.releaseLock(); } catch {}
  }
}
