import React, { useEffect, useMemo, useRef, useState } from 'react';
import { sendGraphUpdate, streamGraphUpdate, getGraphUpdateSession } from '../api/client';
import type { ChatQAResponse } from '../api/types';
import Modal from './Modal';
import SourceDetails from './SourceDetails';
import { cleanText } from '../utils/textUtils';
import { useScrollToBottom } from '../hooks/useScrollToBottom';
import MarkdownMessage from './MarkdownMessage';

interface Props {
  sessionId: string;
  onAfterSend?: () => void | Promise<void>;
}

export default function GraphUpdateView({ sessionId, onAfterSend }: Props) {
  const [messages, setMessages] = useState<Array<[string, string]>>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [pendingAi, setPendingAi] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamEnabled, setStreamEnabled] = useState(true);

  const [latestResponse, setLatestResponse] = useState<ChatQAResponse | null>(null);
  const [showSources, setShowSources] = useState(false);

  const streamAbortRef = useRef<AbortController | null>(null);
  const { bottomRef, scrollToBottom } = useScrollToBottom([messages, pendingAi, sending]);

  // Load history when session changes
  useEffect(() => {
    (async () => {
      try {
        setLoadingHistory(true);
        const res = await getGraphUpdateSession(sessionId);
        const msgs = (res?.history?.messages as Array<[string, string]>) || [];
        setMessages(msgs);
      } catch (e) {
        setMessages([]);
      } finally {
        setLoadingHistory(false);
      }
    })();
  }, [sessionId]);

  const canSend = useMemo(() => text.trim().length > 0, [text]);


  const hasSources = Boolean(
    latestResponse && ((latestResponse.source?.length ?? 0) > 0)
  );

  const stopStreaming = () => {
    if (streamAbortRef.current) {
      streamAbortRef.current.abort();
      streamAbortRef.current = null;
    }
  };

  const handleSend = async () => {
    if (!canSend || sending) return;

    const q = text.trim();
    setMessages(prev => [...prev, ['HumanMessage', q]]);
    setText('');
    setSending(true);
    setPendingAi(true);
    setError(null);

    const payload = { question: q, session_id: sessionId };

    if (streamEnabled) {
      setMessages(prev => [...prev, ['AIMessage', '']]);
      const controller = new AbortController();
      streamAbortRef.current = controller;

      try {
        await streamGraphUpdate(payload, {
          signal: controller.signal,
          onToken: (chunk: string) => {
            setMessages(prev => {
              const updated = prev.slice();
              const lastIdx = updated.length - 1;
              const last = updated[lastIdx];
              if (!last || last[0] !== 'AIMessage') {
                updated.push(['AIMessage', chunk]);
              } else {
                updated[lastIdx] = ['AIMessage', (last[1] ?? '') + chunk];
              }
              return updated;
            });
          },
          onFinal: (evt: any) => {
            const tokenUsage = evt.token_usage ?? { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, total_cost: 0 };
            const execTime = (evt as any).execution_time ?? 'streamed';
            const resp: ChatQAResponse = {
              answer: (evt as any).answer ?? '',
              success: true,
              execution_time: typeof execTime === 'string' ? execTime : 'streamed',
              token_usage: tokenUsage,
              source: (evt as any).source_details ?? [],
              output_images_data: (evt as any).output_images_data ?? [],
              base64_images: (evt as any).base64_images ?? [],
            };
            setLatestResponse(resp);
          },
          onDone: async () => {
            setPendingAi(false);
            setSending(false);
            streamAbortRef.current = null;
            try {
              const res = await getGraphUpdateSession(sessionId);
              const msgs = (res?.history?.messages as Array<[string, string]>) || [];
              setMessages(msgs);
            } catch {}
            try { await onAfterSend?.(); } catch {}
          },
          onError: (err: any) => {
            console.error('Graph stream error:', err);
            setError('Streaming failed');
            setPendingAi(false);
            setSending(false);
            streamAbortRef.current = null;
          },
        });
      } catch (e: any) {
        if (e?.name !== 'AbortError') {
          console.error('Stream failed:', e);
          setError('Streaming failed');
        }
        setPendingAi(false);
        setSending(false);
        streamAbortRef.current = null;
      }
      return;
    }

    try {
      const resp = await sendGraphUpdate(payload);
      setLatestResponse(resp ?? null);
      try {
        const res = await getGraphUpdateSession(sessionId);
        const msgs = (res?.history?.messages as Array<[string, string]>) || [];
        setMessages(msgs);
      } catch {
        setMessages(prev => [...prev, ['AIMessage', resp?.answer || '']]);
      }
      try { await onAfterSend?.(); } catch {}
    } catch (e) {
      console.error('Graph update failed:', e);
      setError('Failed to execute graph update');
    } finally {
      setSending(false);
      setPendingAi(false);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-view">
      <div className="chat-header">
        <div className="title">Graph Update Console <span className="muted">(Session: <code>{sessionId}</code>)</span></div>
      </div>

      <div className="messages" role="log" aria-live="polite">
        {loadingHistory ? (
          <div className="muted">Loading messages...</div>
        ) : null}


        {messages.length === 0 ? (
          <div className="muted">No messages yet. Describe a graph update and press Execute.</div>
        ) : (
          messages.map(([who, content], i) => {
            const role = who === 'HumanMessage' ? 'human' : who === 'AIMessage' ? 'ai' : 'other';
            const isLastAi = i === messages.length - 1 && role === 'ai';
            return (
              <div key={i} className={["message", role].join(' ')}>
                <div className="bubble">
                  <MarkdownMessage>{cleanText(content)}</MarkdownMessage>
                </div>
                {isLastAi && hasSources && (
                  <button
                    className="icon-button view-sources-btn"
                    onClick={() => setShowSources(true)}
                    title="View source details"
                  >
                    View sources
                  </button>
                )}
              </div>
            );
          })
        )}

        {pendingAi && (
          <div className={["message", 'ai', 'typing'].join(' ')}>
            <div className="bubble"><span className="spinner" aria-hidden="true" /> Executing…</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {showSources && latestResponse && (
        <Modal title="Source details" onClose={() => setShowSources(false)}>
          <SourceDetails response={latestResponse} />
        </Modal>
      )}

      <div className="composer">
        {error && <div className="error">{error}</div>}
        <div className="composer-row">
          <div className="actions-left" />
          <textarea
            className="input"
            placeholder="Describe the graph update to execute… (Enter to send, Shift+Enter for new line)"
            value={text}
            onChange={e => setText(e.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
          />
          <div className="actions-right">
            <label className="toggle" title="Stream response">
              <input type="checkbox" checked={streamEnabled} onChange={(e) => setStreamEnabled(e.target.checked)} />
              <span>Stream</span>
            </label>
            {streamEnabled && pendingAi && (
              <button className="btn" onClick={stopStreaming}>Stop</button>
            )}
            <button className="btn primary" disabled={!canSend || sending} onClick={handleSend}>
              {sending ? (streamEnabled ? 'Streaming…' : 'Executing…') : 'Execute'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
