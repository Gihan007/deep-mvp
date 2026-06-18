import React, { useEffect, useMemo, useRef, useState } from 'react';
import { getSession, sendChat, sendDeepChat, streamChat, streamDeepChat } from '../api/client';
import type { SessionMessageTuple, ChatQAResponse } from '../api/types';
import Modal from './Modal';
import SourceDetails from './SourceDetails';
import { cleanText, fileToDataUrl } from '../utils/textUtils';
import { useScrollToBottom } from '../hooks/useScrollToBottom';
import MarkdownMessage from './MarkdownMessage';

interface Props {
  sessionId: string;
  onAfterSend?: () => void | Promise<void>;
}

type B64 = string;


export default function ChatView({ sessionId, onAfterSend }: Props) {
  const [messages, setMessages] = useState<SessionMessageTuple[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingAi, setPendingAi] = useState(false);
  const [latestResponse, setLatestResponse] = useState<ChatQAResponse | null>(null);
  const [showSources, setShowSources] = useState(false);

  const [text, setText] = useState('');
  const [imgB64s, setImgB64s] = useState<B64[]>([]);
  const [fileB64s, setFileB64s] = useState<B64[]>([]);
  const [audioB64s, setAudioB64s] = useState<B64[]>([]);
  const [streamEnabled, setStreamEnabled] = useState(true);
  const streamAbortRef = useRef<AbortController | null>(null);
  const [previewImg, setPreviewImg] = useState<string | null>(null);
  const [deepEnabled, setDeepEnabled] = useState<boolean>(false);
  const [reportRequired, setReportRequired] = useState<boolean>(false);
  const [previewPdfUrl, setPreviewPdfUrl] = useState<string | null>(null);

  const { bottomRef, scrollToBottom } = useScrollToBottom([messages, sending, pendingAi]);

  const loadHistory = async () => {
    try {
      setLoadingHistory(true);
      setError(null);
      const res = await getSession(sessionId);
      const msgs = res?.history?.messages ?? [];
      setMessages(msgs);
    } catch (e: any) {
      // If session not found yet, just show empty
      setMessages([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    loadHistory();
    // Reset composer when switching sessions
    setText('');
    setImgB64s([]);
    setFileB64s([]);
    setAudioB64s([]);
    setLatestResponse(null);
    setShowSources(false);
    setReportRequired(false);
  }, [sessionId]);


  const onSelectImages = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    const results = await Promise.all(files.map(fileToDataUrl));
    setImgB64s(prev => [...prev, ...results]);
    e.currentTarget.value = '';
  };

  const onSelectFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    const results = await Promise.all(files.map(fileToDataUrl));
    setFileB64s(prev => [...prev, ...results]);
    e.currentTarget.value = '';
  };

  const onSelectAudios = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    const results = await Promise.all(files.map(fileToDataUrl));
    setAudioB64s(prev => [...prev, ...results]);
    e.currentTarget.value = '';
  };

  const removeImg = (idx: number) => setImgB64s(prev => prev.filter((_, i) => i !== idx));
  const removeFile = (idx: number) => setFileB64s(prev => prev.filter((_, i) => i !== idx));
  const removeAudio = (idx: number) => setAudioB64s(prev => prev.filter((_, i) => i !== idx));

  const canSend = useMemo(() => {
    return text.trim().length > 0; // backend requires a question
  }, [text]);

  const handleSend = async () => {
    if (!canSend || sending) return;
    const q = text.trim();

    // Optimistic update: user message
    setMessages(prev => [...prev, ['HumanMessage', q]]);
    // Clear composer (attachments are per-message)
    setText('');
    setImgB64s([]);
    setFileB64s([]);
    setAudioB64s([]);

    setSending(true);
    setPendingAi(true);
    setError(null);

    const payload = {
      question: q,
      session_id: sessionId,
      base64_images: imgB64s,
      base64_files: fileB64s,
      base64_audios: audioB64s,
      report_requred: reportRequired,
    };

    if (streamEnabled) {
      // Create AI placeholder for incremental tokens
      setMessages(prev => [...prev, ['AIMessage', '']]);
      const controller = new AbortController();
      streamAbortRef.current = controller;

      try {
        const streamer = deepEnabled ? streamDeepChat : streamChat;
        await streamer(payload, {
          signal: controller.signal,
          onToken: (chunk: string) => {
            setMessages(prev => {
              if (prev.length === 0) return prev;
              const lastIdx = prev.length - 1;
              const last = prev[lastIdx];
              if (!last || last[0] !== 'AIMessage') {
                return [...prev, ['AIMessage', chunk]];
              }
              const updated: typeof prev = prev.slice();
              updated[lastIdx] = ['AIMessage', (last[1] ?? '') + chunk];
              return updated;
            });
          },
          onFinal: (evt) => {
            const tokenUsage = evt.token_usage ?? { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, total_cost: 0 };
            const execTime = evt.execution_time ?? 'streamed';
            const resp: ChatQAResponse = {
              answer: (evt.answer ?? ''),
              success: true,
              execution_time: execTime,
              token_usage: tokenUsage,
              source: (evt.source_details ?? []),
              output_images_data: (evt.output_images_data ?? []),
              base64_images: (evt.base64_images ?? []),
              report_base64: evt.report_base64,
            };
            setLatestResponse(resp);
          },
          onDone: async () => {
            setPendingAi(false);
            setSending(false);
            streamAbortRef.current = null;
            try { await loadHistory(); } catch {}
            try { await onAfterSend?.(); } catch {}
          },
          onError: (err: any) => {
            console.error('Stream error:', err);
            setError('Streaming failed');
            setPendingAi(false);
            setSending(false);
            streamAbortRef.current = null;
          }
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

    // Non-streaming fallback
    try {
      const sender = deepEnabled ? sendDeepChat : sendChat;
      const resp = await sender(payload);
      setLatestResponse(resp ?? null);
      await loadHistory();
      await onAfterSend?.();
    } catch (e: any) {
      console.error('Send failed:', e);
      setError('Failed to send message');
    } finally {
      setSending(false);
      setPendingAi(false);
    }
  };

  const stopStreaming = () => {
    if (streamAbortRef.current) {
      streamAbortRef.current.abort();
      streamAbortRef.current = null;
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const hasSources = Boolean(
    latestResponse && (
      (latestResponse.source?.length ?? 0) > 0 ||
      (latestResponse.output_images_data?.length ?? 0) > 0
    )
  );

  const getPdfDataUrl = (b64?: string | null) => {
    if (!b64) return null;
    return b64.startsWith('data:') ? b64 : `data:application/pdf;base64,${b64}`;
  };

  const handleViewPdf = () => {
    const url = getPdfDataUrl(latestResponse?.report_base64);
    if (!url) return;
    setPreviewPdfUrl(url);
  };

  const handleDownloadPdf = () => {
    const url = getPdfDataUrl(latestResponse?.report_base64);
    if (!url) return;
    const a = document.createElement('a');
    a.href = url;
    a.download = 'deep-search-report.pdf';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="chat-view">
      <div className="chat-header">
        <div className="title">Session: <code>{sessionId}</code></div>
      </div>

      <div className="messages" role="log" aria-live="polite">
        {loadingHistory ? (
          <div className="muted">Loading messages...</div>
        ) : messages.length === 0 ? (
          <div className="muted">No messages yet. Ask a question to begin.</div>
        ) : (
          <>
            {messages.map(([type, content]: SessionMessageTuple, idx: number) => {
              const who = type === 'HumanMessage' ? 'human' : type === 'AIMessage' ? 'ai' : 'other';
              const isLastAi = idx === messages.length - 1 && who === 'ai';
              return (
                <div key={idx} className={['message', who].join(' ')}>
                  <div className="bubble">
                    <MarkdownMessage>{cleanText(content)}</MarkdownMessage>
                  </div>
                  {isLastAi && ((latestResponse?.base64_images?.filter(img => img && (img as any).image_base64).length) ?? 0) > 0 && (
                    <div className="image-grid">
                      {((latestResponse?.base64_images ?? []) as Array<{ image_base64: string | null; description?: string }>)
                        .filter(img => !!(img && img.image_base64))
                        .map((img, i) => {
                          const b64 = img.image_base64 as string;
                          const url = b64.startsWith('data:') ? b64 : `data:image/png;base64,${b64}`;
                          const desc = img.description || `generated-${i}`;
                          return (
                            <figure key={i} className="image-figure" style={{ margin: 0 }}>
                              <img
                                src={url}
                                alt={desc}
                                className="image-thumb"
                                style={{ cursor: 'zoom-in' }}
                                onClick={() => setPreviewImg(url)}
                              />
                              {img.description ? <figcaption className="image-caption">{img.description}</figcaption> : null}
                            </figure>
                          );
                        })}
                    </div>
                  )}
                  {isLastAi && hasSources && (
                    <button
                      className="icon-button view-sources-btn"
                      onClick={() => setShowSources(true)}
                      title="View source details"
                    >
                      View sources
                    </button>
                  )}
                  {isLastAi && latestResponse?.report_base64 && (
                    <div className="report-actions" style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
                      <button className="btn" onClick={handleViewPdf}>View report (PDF)</button>
                      <button className="btn" onClick={handleDownloadPdf}>Download report</button>
                    </div>
                  )}
                </div>
              );
            })}
            {pendingAi && (
              <div className={['message', 'ai', 'typing'].join(' ')}>
                <div className="bubble"><span className="spinner" aria-hidden="true" /> Thinking…</div>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {showSources && latestResponse && (
        <Modal title="Source details" onClose={() => setShowSources(false)}>
          <SourceDetails response={latestResponse} />
        </Modal>
      )}

      {previewImg && (
        <Modal title="Image preview" onClose={() => setPreviewImg(null)} maxWidth="90vw">
          <div style={{ textAlign: 'center' }}>
            <img
              src={previewImg}
              alt="preview"
              style={{ maxWidth: '85vw', maxHeight: '80vh' }}
            />
          </div>
        </Modal>
      )}

      {previewPdfUrl && (
        <Modal title="Deep search report" onClose={() => setPreviewPdfUrl(null)} maxWidth="90vw">
          <div style={{ height: '80vh' }}>
            <iframe
              title="report"
              src={previewPdfUrl}
              style={{ width: '100%', height: '100%', border: 'none' }}
            />
          </div>
        </Modal>
      )}

      <div className="composer">
        {error && <div className="error">{error}</div>}

        {(imgB64s.length > 0 || fileB64s.length > 0 || audioB64s.length > 0) && (
          <div className="attachments">
            {imgB64s.map((b64, i) => (
              <div className="attachment" key={`img-${i}`}>
                <img className="preview-img" src={b64} alt={`attachment-${i}`} />
                <button className="icon-button" onClick={() => removeImg(i)} title="Remove">✖</button>
              </div>
            ))}
            {fileB64s.map((b64, i) => (
              <div className="attachment" key={`file-${i}`}>
                <span className="file-pill">File {i + 1}</span>
                <button className="icon-button" onClick={() => removeFile(i)} title="Remove">✖</button>
              </div>
            ))}
            {audioB64s.map((b64, i) => (
              <div className="attachment" key={`audio-${i}`}>
                <span className="file-pill">Audio {i + 1}</span>
                <button className="icon-button" onClick={() => removeAudio(i)} title="Remove">✖</button>
              </div>
            ))}
          </div>
        )}

        <div className="composer-row">
          <div className="actions-left">
            <label className="icon-button" title="Attach images">
              🖼️
              <input type="file" accept="image/*" multiple style={{ display: 'none' }} onChange={onSelectImages} />
            </label>
            <label className="icon-button" title="Attach files">
              📎
              <input type="file" multiple style={{ display: 'none' }} onChange={onSelectFiles} />
            </label>
            <label className="icon-button" title="Attach audio">
              🎤
              <input type="file" accept="audio/*" multiple style={{ display: 'none' }} onChange={onSelectAudios} />
            </label>
          </div>
          <textarea
            className="input"
            placeholder="Send a message..."
            value={text}
            onChange={e => setText(e.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
          />
          <div className="actions-right">
            <label className="toggle" title="Deep search (uses /api/deep_qa_bot)">
              <input
                type="checkbox"
                checked={deepEnabled}
                onChange={e => setDeepEnabled(e.target.checked)}
              />
              <span>Deep search</span>
            </label>
            <label className="toggle" title="If enabled, backend generates a PDF report (report_base64)">
              <input
                type="checkbox"
                checked={reportRequired}
                onChange={e => setReportRequired(e.target.checked)}
              />
              <span>Report (PDF)</span>
            </label>
            <label className="toggle" title="Stream response">
              <input
                type="checkbox"
                checked={streamEnabled}
                onChange={e => setStreamEnabled(e.target.checked)}
              />
              <span>Stream</span>
            </label>
            {streamEnabled && pendingAi && (
              <button className="btn" onClick={stopStreaming}>Stop</button>
            )}
            <button className="btn primary" disabled={!canSend || sending} onClick={handleSend}>
              {sending ? (streamEnabled ? 'Streaming…' : 'Sending…') : 'Send'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
