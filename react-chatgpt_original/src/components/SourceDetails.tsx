import React from 'react';
import type { ChatQAResponse } from '../api/types';

interface Props {
  response: ChatQAResponse;
}

function isNonEmptyArray<T = unknown>(v: unknown): v is T[] {
  return Array.isArray(v) && v.length > 0;
}

function humanKey(key: string) {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

export default function SourceDetails({ response }: Props) {
  const sources = response.source ?? [];
  const outImages = response.output_images_data ?? [];
  const executionTime = response.execution_time || 'streamed';
  const token = response.token_usage ?? {
    prompt_tokens: 0,
    completion_tokens: 0,
    total_tokens: 0,
    total_cost: 0
  };

  // Try to pull common fields if present for nicer rendering
  const renderSourceCard = (src: Record<string, unknown>, idx: number) => {
    const anySrc = src as any;
    const title: string | undefined =
      anySrc.title || anySrc.Name || anySrc.filename || anySrc.file_name || anySrc.doc_title;
    const url: string | undefined = anySrc.url || anySrc.link || anySrc.href;
    const page: number | string | undefined = anySrc.page || anySrc.page_number;
    const score: number | string | undefined = anySrc.score || anySrc.similarity || anySrc.rank;
    const snippet: string | undefined =
      anySrc.snippet || anySrc.text || anySrc.excerpt || anySrc.chunk || anySrc.content;

    return (
      <div key={idx} className="source-card">
        <div className="source-card-header">
          <div className="source-card-title">{title || `Source ${idx + 1}`}</div>
          {url ? (
            <a className="source-link" href={url as string} target="_blank" rel="noreferrer">Open ↗</a>
          ) : null}
        </div>
        <div className="source-card-meta">
          {page !== undefined ? <span className="meta-pill">Page: {String(page)}</span> : null}
          {score !== undefined ? <span className="meta-pill">Score: {String(score)}</span> : null}
        </div>
        {snippet ? (
          <div className="source-snippet">{snippet}</div>
        ) : (
          <pre className="source-json">{JSON.stringify(src, null, 2)}</pre>
        )}
      </div>
    );
  };

  return (
    <div className="source-details">
      <div className="section">
        <div className="section-title">Run Info</div>
        <div className="kv-grid">
          <div className="kv-row"><div className="k">Execution Time</div><div className="v">{executionTime}</div></div>
          <>
            <div className="kv-row"><div className="k">Prompt Tokens</div><div className="v">{token.prompt_tokens}</div></div>
            <div className="kv-row"><div className="k">Completion Tokens</div><div className="v">{token.completion_tokens}</div></div>
            <div className="kv-row"><div className="k">Total Tokens</div><div className="v">{token.total_tokens}</div></div>
            <div className="kv-row"><div className="k">Total Cost</div><div className="v">{token.total_cost}</div></div>
          </>
        </div>
      </div>

      {isNonEmptyArray<Record<string, unknown>>(sources) && (
        <div className="section">
          <div className="section-title">Citations</div>
          <div className="source-list">
            {sources.map((s, i) => renderSourceCard(s, i))}
          </div>
        </div>
      )}


      {isNonEmptyArray(outImages) && (
        <div className="section">
          <div className="section-title">Output Images</div>
          <ul className="path-list">
            {outImages.map((it: any, i: number) => (
              <li key={i}>
                <code>{it?.image_path}</code>
                {it?.description ? <span className="muted"> — {String(it.description)}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      {!isNonEmptyArray(sources) && !isNonEmptyArray(outImages) ? (
        <div className="muted">No source details were returned for this response.</div>
      ) : null}
    </div>
  );
}
