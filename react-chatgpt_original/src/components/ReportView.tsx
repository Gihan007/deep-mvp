import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  getReportSession,
  listSectors,
  listIndustriesBySector,
  listCompaniesByIndustry,
  sendReport,
  streamReport,
  listAllCompanies,
  listAllIndustries,
} from '../api/client';
import type {
  SessionMessageTuple,
  ChatQAResponse,
  ReportType,
  Sector,
  Industry,
  Company,
  ReportRequest,
  StreamDoneEvent
} from '../api/types';
import Modal from './Modal';
import SourceDetails from './SourceDetails';
import { cleanText } from '../utils/textUtils';
import { useScrollToBottom } from '../hooks/useScrollToBottom';
import MarkdownMessage from './MarkdownMessage';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Props {
  sessionId: string;
  onAfterSend?: () => void | Promise<void>;
}

const REPORT_TYPES: { label: string; value: ReportType }[] = [
  { label: 'Company performance & investment thesis', value: 'company_performance_and_investment_thesis' },
  { label: 'Industry deep-dive', value: 'industry_deep_drive' },
];

const TIME_OPTIONS = [
  'last 1 year',
  'last 3 years',
  'last 5 years',
  'last 10 years',
  'YTD',
  'custom',
];

export default function ReportView({ sessionId, onAfterSend }: Props) {
  // History and response rendering (like ChatView)
  const [messages, setMessages] = useState<SessionMessageTuple[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingAi, setPendingAi] = useState(false);
  const [latestResponse, setLatestResponse] = useState<ChatQAResponse | null>(null);
  const [showSources, setShowSources] = useState(false);
  const [previewImg, setPreviewImg] = useState<string | null>(null);
  const [previewPdfUrl, setPreviewPdfUrl] = useState<string | null>(null);

  // Form state
  const [reportType, setReportType] = useState<ReportType>('company_performance_and_investment_thesis');
  const [instructions, setInstructions] = useState('');
  const [streamEnabled, setStreamEnabled] = useState(true);

  // Company selection flow (Sector -> Industry -> Company)
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [industriesBySector, setIndustriesBySector] = useState<Industry[]>([]);
  const [companiesByIndustry, setCompaniesByIndustry] = useState<Company[]>([]);
  const [allIndustries, setAllIndustries] = useState<Industry[]>([]); // for industry deep-dive

  const [selectedSector, setSelectedSector] = useState<string>(''); // sectorName for simplicity
  const [selectedIndustry, setSelectedIndustry] = useState<string>(''); // industryName
  const [selectedCompany, setSelectedCompany] = useState<string>(''); // companyName

  // Typeahead fields
  const [companyQuery, setCompanyQuery] = useState<string>(''); // path company typeahead
  const [companyDropdownOpen, setCompanyDropdownOpen] = useState<boolean>(false);

  const [directCompanyQuery, setDirectCompanyQuery] = useState<string>('');
  const [directDropdownOpen, setDirectDropdownOpen] = useState<boolean>(false);

  const [deepIndustryQuery, setDeepIndustryQuery] = useState<string>('');
  const [deepIndustryDropdownOpen, setDeepIndustryDropdownOpen] = useState<boolean>(false);

  const [allCompanies, setAllCompanies] = useState<Company[]>([]);

  // Time horizon
  const [timeOption, setTimeOption] = useState<string>('last 5 years');
  const [timeCustom, setTimeCustom] = useState<string>('');
  const [companySelectMode, setCompanySelectMode] = useState<'direct' | 'by_path'>('direct');
  const [formCollapsed, setFormCollapsed] = useState<boolean>(false);
  const [autoCollapse, setAutoCollapse] = useState<boolean>(true);
  const [composerHeight, setComposerHeight] = useState<number>(300);
  const [isResizing, setIsResizing] = useState<boolean>(false);
  const resizeStartRef = useRef<{ y: number; h: number } | null>(null);

  const streamAbortRef = useRef<AbortController | null>(null);
  const { bottomRef, scrollToBottom } = useScrollToBottom([messages, sending, pendingAi]);

  const loadHistory = async () => {
    try {
      setLoadingHistory(true);
      setError(null);
      const res = await getReportSession(sessionId);
      const msgs = res?.history?.messages ?? [];
      setMessages(msgs);
    } catch {
      setMessages([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    loadHistory();
    // reset local UI for new session
    setInstructions('');
    setSelectedSector('');
    setSelectedIndustry('');
    setSelectedCompany('');
    setCompanyQuery('');
    setDirectCompanyQuery('');
    setDeepIndustryQuery('');
    setLatestResponse(null);
    setShowSources(false);
  }, [sessionId]);

  // Load sectors for company flow
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const secs = await listSectors();
        if (mounted) setSectors(secs || []);
      } catch (e) {
        console.warn('Failed to load sectors', e);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  // Load all industries for deep-dive
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const industries = await listAllIndustries();
        if (mounted) setAllIndustries(industries || []);
      } catch (e) {
        console.warn('Failed to load all industries', e);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  // Load all companies for direct select
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const companies = await listAllCompanies();
        if (mounted) setAllCompanies(companies || []);
      } catch (e) {
        console.warn('Failed to load all companies', e);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  // When sector changes, fetch industries
  useEffect(() => {
    let mounted = true;
    if (!selectedSector) {
      setIndustriesBySector([]);
      setSelectedIndustry('');
      return;
    }
    (async () => {
      try {
        const industries = await listIndustriesBySector({ sectorName: selectedSector });
        if (mounted) {
          setIndustriesBySector(industries || []);
          setSelectedIndustry('');
          setCompaniesByIndustry([]);
          setSelectedCompany('');
        }
      } catch (e) {
        console.warn('Failed to load industries for sector', e);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [selectedSector]);

  // When industry changes, fetch companies
  useEffect(() => {
    let mounted = true;
    if (!selectedIndustry) {
      setCompaniesByIndustry([]);
      setSelectedCompany('');
      return;
    }
    (async () => {
      try {
        const companies = await listCompaniesByIndustry({ industryName: selectedIndustry });
        if (mounted) {
          setCompaniesByIndustry(companies || []);
          setSelectedCompany('');
          setCompanyQuery('');
        }
      } catch (e) {
        console.warn('Failed to load companies for industry', e);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [selectedIndustry]);

  const hasSources = Boolean(
    latestResponse &&
      ((latestResponse.source?.length ?? 0) > 0 || (latestResponse.output_images_data?.length ?? 0) > 0)
  );

  const companyLabel = (c: Company) => `${c.companyName || ''}${c.ticker ? `(${c.ticker})` : ''}`;

  const companySuggestions = useMemo(() => {
    const q = companyQuery.trim().toLowerCase();
    if (!q) return companiesByIndustry;
    return companiesByIndustry.filter((c) => {
      const name = (c.companyName || '').toLowerCase();
      const tick = (c.ticker || '').toLowerCase();
      return name.includes(q) || tick.includes(q);
    });
  }, [companiesByIndustry, companyQuery]);

  const directCompanySuggestions = useMemo(() => {
    const q = directCompanyQuery.trim().toLowerCase();
    if (!q) return allCompanies;
    return allCompanies.filter((c) => {
      const name = (c.companyName || '').toLowerCase();
      const tick = (c.ticker || '').toLowerCase();
      return name.includes(q) || tick.includes(q);
    });
  }, [allCompanies, directCompanyQuery]);

  const deepIndustrySuggestions = useMemo(() => {
    const q = deepIndustryQuery.trim().toLowerCase();
    if (!q) return allIndustries;
    return allIndustries.filter((ind: Industry) => {
      const name = (ind.industryName || '').toLowerCase();
      return name.includes(q);
    });
  }, [allIndustries, deepIndustryQuery]);

  // Helpers: base64 PDF -> Blob URL for reliable large-file rendering
  const base64ToBlob = (b64: string, contentType = 'application/pdf') => {
    const raw = atob(b64);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return new Blob([bytes], { type: contentType });
  };

  const base64PdfToBlobUrl = (b64?: string | null) => {
    if (!b64) return null;
    const pure = b64.startsWith('data:') ? b64.split(',', 2)[1] : b64;
    const blob = base64ToBlob(pure, 'application/pdf');
    return URL.createObjectURL(blob);
  };

  const handleViewPdf = () => {
    const blobUrl = base64PdfToBlobUrl(latestResponse?.report_base64);
    if (!blobUrl) return;
    if (previewPdfUrl) URL.revokeObjectURL(previewPdfUrl);
    setPreviewPdfUrl(blobUrl);
  };

  const handleDownloadPdf = () => {
    const blobUrl = base64PdfToBlobUrl(latestResponse?.report_base64);
    if (!blobUrl) return;
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = 'deep-report.pdf';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    // Revoke after giving the browser a moment to start the download
    setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
  };

  const effectiveTimeHorizon = useMemo(() => {
    return timeOption === 'custom' ? timeCustom.trim() || 'last 5 years' : timeOption;
  }, [timeOption, timeCustom]);

  const canSend = useMemo(() => {
    if (reportType === 'company_performance_and_investment_thesis') {
      if (companySelectMode === 'direct') {
        return !!directCompanyQuery.trim();
      }
      return !!(selectedIndustry.trim() && (companyQuery.trim() || selectedCompany.trim()));
    }
    if (reportType === 'industry_deep_drive') {
      return !!(deepIndustryQuery.trim() || selectedIndustry.trim());
    }
    return false;
  }, [
    reportType,
    companySelectMode,
    directCompanyQuery,
    companyQuery,
    selectedCompany,
    deepIndustryQuery,
    selectedIndustry,
  ]);

  const buildPayload = (): ReportRequest => {
    const parseCompany = (text: string) => {
      const m = text.match(/^(.*?)\s*\(([^)]+)\)\s*$/);
      return {
        name: (m ? m[1] : text).trim(),
        ticker: m ? m[2].trim() : '',
      };
    };

    const viaDirect = !!directCompanyQuery.trim();
    const parsedDirect = viaDirect ? parseCompany(directCompanyQuery) : null;
    const parsedPath = !viaDirect ? parseCompany(companyQuery) : null;

    const company_name = viaDirect ? parsedDirect?.name || '' : parsedPath?.name || selectedCompany || '';
    const industry_name =
      reportType === 'company_performance_and_investment_thesis'
        ? selectedIndustry || ''
        : deepIndustryQuery || selectedIndustry || '';

    const payload: ReportRequest = {
      instructions: instructions.trim(),
      question: instructions.trim(),
      report_type: reportType,
      time_horizon: effectiveTimeHorizon,
      company_name: company_name || undefined,
      industry_name: industry_name || undefined,
      session_id: sessionId,
      base64_images: [],
      base64_files: [],
      base64_audios: [],
    };
    return payload;
  };

  const handleSend = async () => {
    if (!canSend || sending) return;

    const summaryParts = [
      `Report type: ${reportType}`,
      effectiveTimeHorizon ? `Time: ${effectiveTimeHorizon}` : '',
      selectedSector ? `Sector: ${selectedSector}` : '',
      selectedIndustry ? `Industry: ${selectedIndustry}` : '',
      (directCompanyQuery || companyQuery || selectedCompany)
        ? `Company: ${directCompanyQuery || companyQuery || selectedCompany}`
        : '',
    ]
      .filter(Boolean)
      .join(' | ');

    const userText = `Generate report\n${summaryParts}\nInstructions:\n${(instructions || '').trim()}`;

    setMessages((prev) => [...prev, ['HumanMessage', userText]]);
    setSending(true);
    setPendingAi(true);
    if (autoCollapse) setFormCollapsed(true);
    setError(null);

    const payload = buildPayload();

    if (streamEnabled) {
      setMessages((prev) => [...prev, ['AIMessage', '']]);
      const controller = new AbortController();
      streamAbortRef.current = controller;

      try {
        await streamReport(payload, {
          signal: controller.signal,
          onToken: (chunk: string) => {
            setMessages((prev) => {
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
          onFinal: (evt: StreamDoneEvent) => {
            const tokenUsage =
              evt.token_usage ?? { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, total_cost: 0 };
            const execTime = (evt as any).execution_time ?? 'streamed';
            const resp: ChatQAResponse = {
              answer: (evt as any).answer ?? '',
              success: true,
              execution_time: typeof execTime === 'string' ? execTime : 'streamed',
              token_usage: tokenUsage,
              source: (evt as any).source_details ?? [],
              output_images_data: (evt as any).output_images_data ?? [],
              base64_images: (evt as any).base64_images ?? [],
              report_base64: (evt as any).report_base64,
            };
            setLatestResponse(resp);
          },
          onDone: async () => {
            setPendingAi(false);
            setSending(false);
            streamAbortRef.current = null;
            try {
              await loadHistory();
            } catch {}
            try {
              await onAfterSend?.();
            } catch {}
          },
          onError: (err: any) => {
            console.error('Report stream error:', err);
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
      const resp = await sendReport(payload);
      setLatestResponse(resp ?? null);
      await loadHistory();
      await onAfterSend?.();
    } catch (e) {
      console.error('Report send failed:', e);
      setError('Failed to generate report');
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

  const onKeyDownInstructions = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && e.metaKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClosePdfModal = () => {
    if (previewPdfUrl) URL.revokeObjectURL(previewPdfUrl);
    setPreviewPdfUrl(null);
  };

  const onResizerMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    setIsResizing(true);
    resizeStartRef.current = { y: e.clientY, h: composerHeight };
    window.addEventListener('mousemove', onResizerMouseMove as any);
    window.addEventListener('mouseup', onResizerMouseUp as any);
  };
  const onResizerMouseMove = (e: MouseEvent) => {
    if (!resizeStartRef.current) return;
    const delta = e.clientY - resizeStartRef.current.y;
    const newH = Math.min(600, Math.max(140, resizeStartRef.current.h + delta));
    setComposerHeight(newH);
  };
  const onResizerMouseUp = () => {
    setIsResizing(false);
    resizeStartRef.current = null;
    window.removeEventListener('mousemove', onResizerMouseMove as any);
    window.removeEventListener('mouseup', onResizerMouseUp as any);
  };
  const timeIsCustom = timeOption === 'custom';

  return (
    <div className="chat-view">
      <div className="chat-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <div className="title">
          Report session: <code>{sessionId}</code>
        </div>
        <div className="actions-right" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label className="toggle" title="Auto-collapse form on generate">
            <input type="checkbox" checked={autoCollapse} onChange={(e) => setAutoCollapse(e.target.checked)} />
            <span>Auto-collapse</span>
          </label>
          <button className="btn" onClick={() => setFormCollapsed((v) => !v)}>
            {formCollapsed ? 'Show form' : 'Hide form'}
          </button>
        </div>
      </div>

      <div className="messages" role="log" aria-live="polite">
        {loadingHistory ? (
          <div className="muted">Loading messages...</div>
        ) : messages.length === 0 ? (
          <div className="muted">No messages yet. Configure the form below and generate a report.</div>
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
                  {isLastAi &&
                    ((latestResponse?.base64_images?.filter((img) => img && (img as any).image_base64).length) ?? 0) >
                      0 && (
                      <div className="image-grid">
                        {((latestResponse?.base64_images ?? []) as Array<{
                          image_base64: string | null;
                          description?: string;
                        }>)
                          .filter((img) => !!(img && img.image_base64))
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
                                {img.description ? (
                                  <figcaption className="image-caption">{img.description}</figcaption>
                                ) : null}
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
                      <button className="btn" onClick={handleViewPdf}>
                        View report (PDF)
                      </button>
                      <button className="btn" onClick={handleDownloadPdf}>
                        Download report
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
            {pendingAi && (
              <div className={['message', 'ai', 'typing'].join(' ')}>
                <div className="bubble">
                  <span className="spinner" aria-hidden="true" /> Generating report…
                </div>
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
            <img src={previewImg} alt="preview" style={{ maxWidth: '85vw', maxHeight: '80vh' }} />
          </div>
        </Modal>
      )}

      {previewPdfUrl && (
        <Modal title="Report" onClose={handleClosePdfModal} maxWidth="90vw">
          <div style={{ height: '80vh' }}>
            <iframe title="report" src={previewPdfUrl} style={{ width: '100%', height: '100%', border: 'none' }} />
          </div>
        </Modal>
      )}

      {/* Stream + Generate */}
      {!formCollapsed && (
        <div
          className="resizer"
          onMouseDown={onResizerMouseDown}
          style={{ height: 6, cursor: 'row-resize', background: 'var(--border)' }}
          title="Drag to resize form height"
        />
      )}
      <div className="composer" style={{ display: formCollapsed ? 'none' : undefined, height: composerHeight, overflow: 'auto' }}>
        {error && <div className="error">{error}</div>}



        <div
          className="form-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: 12,
            alignItems: 'start',
          }}
        >
          {/* Step 1 — Report type */}
          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <div className="label" style={{ fontWeight: 600 }}>Step 1 — Select report type</div>
          </div>
          <div className="field" style={{ minWidth: 220 }}>
            <label className="label">Report type</label>
            <select
              className="input"
              value={reportType}
              onChange={(e) => setReportType(e.target.value as ReportType)}
            >
              {REPORT_TYPES.map((rt) => (
                <option key={rt.value} value={rt.value}>
                  {rt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Step 2 — Time horizon (for company performance reports) */}
          {reportType === 'company_performance_and_investment_thesis' && (
            <>
              <div className="field" style={{ gridColumn: '1 / -1' }}>
                <div className="label" style={{ fontWeight: 600 }}>Step 2 — Select time horizon</div>
              </div>
              <div className="field" style={{ minWidth: 220 }}>
                <label className="label">Time horizon</label>
                <select className="input" value={timeOption} onChange={(e) => setTimeOption(e.target.value)}>
                  {TIME_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
                {timeIsCustom && (
                  <input
                    className="input"
                    placeholder="e.g., last 7 years, FY2015-2024, etc."
                    value={timeCustom}
                    onChange={(e) => setTimeCustom(e.target.value)}
                    style={{ marginTop: 6 }}
                  />
                )}
              </div>
            </>
          )}

          {/* Company performance flow */}
          {reportType === 'company_performance_and_investment_thesis' && (
            <>
              <div className="field" style={{ gridColumn: '1 / -1' }}>
                <div className="label" style={{ fontWeight: 600 }}>Step 3 — Select company</div>
                <div className="muted">Choose how to select the company</div>
              </div>
              <div className="field" style={{ minWidth: 260 }}>
                <label className="label">Select company by</label>
                <div style={{ display: 'flex', gap: 12 }}>
                  <label className="toggle">
                    <input
                      type="radio"
                      name="companyMode"
                      checked={companySelectMode === 'direct'}
                      onChange={() => setCompanySelectMode('direct')}
                    />
                    <span>Direct search</span>
                  </label>
                  <label className="toggle">
                    <input
                      type="radio"
                      name="companyMode"
                      checked={companySelectMode === 'by_path'}
                      onChange={() => setCompanySelectMode('by_path')}
                    />
                    <span>Sector → Industry → Company</span>
                  </label>
                </div>
              </div>

              {companySelectMode === 'by_path' && (
                <>
                  {/* Sector */}
                  <div className="field" style={{ minWidth: 220 }}>
                    <label className="label">Sector</label>
                    <select className="input" value={selectedSector} onChange={(e) => setSelectedSector(e.target.value)}>
                      <option value="">Select sector</option>
                      {sectors.map((s, i) => (
                        <option key={i} value={s.sectorName || ''}>
                          {s.sectorName || s.sectorId || '(unnamed)'}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Industry */}
                  <div className="field" style={{ minWidth: 260 }}>
                    <label className="label">Industry</label>
                    <select
                      className="input"
                      value={selectedIndustry}
                      onChange={(e) => setSelectedIndustry(e.target.value)}
                    >
                      <option value="">Select industry</option>
                      {allIndustries.map((industry: Industry, i: number) => (
                        <option key={i} value={industry.industryName || ''}>
                          {industry.industryName || industry.industryId || '(unnamed)'}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Company (path) */}
                  <div className="field" style={{ minWidth: 260, position: 'relative' }}>
                    <label className="label">Company</label>
                    <input
                      className="input"
                      placeholder="Type company name or ticker"
                      value={companyQuery}
                      onChange={(e) => {
                        setCompanyQuery(e.target.value);
                        setCompanyDropdownOpen(true);
                      }}
                      onFocus={() => setCompanyDropdownOpen(true)}
                      onBlur={() => setTimeout(() => setCompanyDropdownOpen(false), 150)}
                      disabled={!selectedIndustry}
                    />
                    {companyQuery && (
                      <button
                        type="button"
                        className="icon-button"
                        title="Clear company"
                        onClick={() => {
                          setCompanyQuery('');
                          setSelectedCompany('');
                        }}
                        style={{ position: 'absolute', right: 8, top: 30 }}
                      >
                        ✖
                      </button>
                    )}
                    {companyDropdownOpen && companySuggestions.length > 0 && (
                      <div
                        className="dropdown"
                        style={{
                          position: 'absolute',
                          top: '100%',
                          left: 0,
                          right: 0,
                          zIndex: 10,
                          background: '#1f2937',
                          color: '#e5e7eb',
                          border: '1px solid #374151',
                          borderRadius: 4,
                          maxHeight: 220,
                          overflowY: 'auto',
                          boxShadow: '0 2px 12px rgba(0,0,0,0.32)',
                          marginTop: 4,
                        }}
                      >
                        {companySuggestions.map((c, i) => {
                          const label = companyLabel(c);
                          return (
                            <button
                              key={i}
                              type="button"
                              className="session-button"
                              style={{
                                width: '100%',
                                textAlign: 'left',
                                padding: '6px 10px',
                                background: 'transparent',
                                color: '#e5e7eb',
                                borderBottom: '1px solid #374151',
                              }}
                              onMouseEnter={(e) => {
                                (e.currentTarget as HTMLButtonElement).style.background = '#374151';
                              }}
                              onMouseLeave={(e) => {
                                (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                              }}
                              onClick={() => {
                                setCompanyQuery(label);
                                setSelectedCompany(c.companyName || '');
                                setCompanyDropdownOpen(false);
                              }}
                              title={label}
                            >
                              {label}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </>
              )}

              {companySelectMode === 'direct' && (
                <>
                  {/* Company (direct select) */}
                  <div className="field" style={{ minWidth: 260, position: 'relative' }}>
                    <label className="label">Company (direct select)</label>
                    <input
                      className="input"
                      placeholder="Type company name or ticker"
                      value={directCompanyQuery}
                      onChange={(e) => {
                        setDirectCompanyQuery(e.target.value);
                        setDirectDropdownOpen(true);
                      }}
                      onFocus={() => setDirectDropdownOpen(true)}
                      onBlur={() => setTimeout(() => setDirectDropdownOpen(false), 150)}
                    />
                    {directCompanyQuery && (
                      <button
                        type="button"
                        className="icon-button"
                        title="Clear company"
                        onClick={() => {
                          setDirectCompanyQuery('');
                        }}
                        style={{ position: 'absolute', right: 8, top: 30 }}
                      >
                        ✖
                      </button>
                    )}
                    {directDropdownOpen && directCompanySuggestions.length > 0 && (
                      <div
                        className="dropdown"
                        style={{
                          position: 'absolute',
                          top: '100%',
                          left: 0,
                          right: 0,
                          zIndex: 10,
                          background: '#1f2937',
                          color: '#e5e7eb',
                          border: '1px solid #374151',
                          borderRadius: 4,
                          maxHeight: 220,
                          overflowY: 'auto',
                          boxShadow: '0 2px 12px rgba(0,0,0,0.32)',
                          marginTop: 4,
                        }}
                      >
                        {directCompanySuggestions.map((c, i) => {
                          const label = companyLabel(c);
                          return (
                            <button
                              key={i}
                              type="button"
                              className="session-button"
                              style={{
                                width: '100%',
                                textAlign: 'left',
                                padding: '6px 10px',
                                background: 'transparent',
                                color: '#e5e7eb',
                                borderBottom: '1px solid #374151',
                              }}
                              onMouseEnter={(e) => {
                                (e.currentTarget as HTMLButtonElement).style.background = '#374151';
                              }}
                              onMouseLeave={(e) => {
                                (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                              }}
                              onClick={() => {
                                setDirectCompanyQuery(label);
                                setDirectDropdownOpen(false);
                              }}
                              title={label}
                            >
                              {label}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </>
              )}
            </>
          )}

          {/* Industry deep-dive flow */}
          {reportType === 'industry_deep_drive' && (
            <>
              <div className="field" style={{ gridColumn: '1 / -1' }}>
                <div className="label" style={{ fontWeight: 600 }}>Step 2 — Select industry</div>
              </div>
              <div className="field" style={{ minWidth: 300, position: 'relative' }}>
                <label className="label">Industry</label>
                <input
                  className="input"
                  placeholder="Type industry"
                  value={deepIndustryQuery}
                  onChange={(e) => {
                    setDeepIndustryQuery(e.target.value);
                    setDeepIndustryDropdownOpen(true);
                  }}
                  onFocus={() => setDeepIndustryDropdownOpen(true)}
                  onBlur={() => setTimeout(() => setDeepIndustryDropdownOpen(false), 150)}
                />
                {deepIndustryQuery && (
                  <button
                    type="button"
                    className="icon-button"
                    title="Clear industry"
                    onClick={() => {
                      setDeepIndustryQuery('');
                      setSelectedIndustry('');
                    }}
                    style={{ position: 'absolute', right: 8, top: 30 }}
                  >
                    ✖
                  </button>
                )}
                {deepIndustryDropdownOpen && deepIndustrySuggestions.length > 0 && (
                  <div
                    className="dropdown"
                    style={{
                      position: 'absolute',
                      top: '100%',
                      left: 0,
                      right: 0,
                      zIndex: 10,
                      background: '#1f2937',
                      color: '#e5e7eb',
                      border: '1px solid #374151',
                      borderRadius: 4,
                      maxHeight: 220,
                      overflowY: 'auto',
                      boxShadow: '0 2px 12px rgba(0,0,0,0.32)',
                      marginTop: 4,
                    }}
                  >
                    {deepIndustrySuggestions.map((ind, i) => {
                      const label = ind.industryName || '';
                      return (
                        <button
                          key={i}
                          type="button"
                          className="session-button"
                          style={{
                            width: '100%',
                            textAlign: 'left',
                            padding: '6px 10px',
                            background: 'transparent',
                            color: '#e5e7eb',
                            borderBottom: '1px solid #374151',
                          }}
                          onMouseEnter={(e) => {
                            (e.currentTarget as HTMLButtonElement).style.background = '#374151';
                          }}
                          onMouseLeave={(e) => {
                            (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                          }}
                          onClick={() => {
                            setDeepIndustryQuery(label);
                            setSelectedIndustry(label);
                            setDeepIndustryDropdownOpen(false);
                          }}
                          title={label}
                        >
                          {label}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          )}



          {/* Instructions spanning full width */}
          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <label className="label">Instructions</label>
            <textarea
              className="input"
              placeholder="Add any specific instructions, focus areas, KPIs to analyze, etc."
              rows={3}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              onKeyDown={onKeyDownInstructions}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12, marginTop: 8 }}>
              <label className="toggle" title="Stream response">
                <input type="checkbox" checked={streamEnabled} onChange={(e) => setStreamEnabled(e.target.checked)} />
                <span>Stream</span>
              </label>
              {streamEnabled && pendingAi && (
                <button className="btn" onClick={stopStreaming}>
                  Stop
                </button>
              )}
              <button className="btn primary" disabled={!canSend || sending} onClick={handleSend}>
                {sending ? (streamEnabled ? 'Streaming…' : 'Generating…') : 'Generate'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
