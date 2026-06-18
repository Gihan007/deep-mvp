import React, { useEffect, useMemo, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { listSessions, listReportSessions, deleteSession as apiDeleteSession, clearAllSessions as apiClearAll, deleteReportSession as apiDeleteReport, clearAllReportSessions as apiClearAllReport, listGraphUpdateSessions, deleteGraphUpdateSession as apiDeleteGraphUpdate, clearAllGraphUpdateSessions as apiClearAllGraphUpdate } from './api/client';
import type { SessionDetail, SessionsResponse } from './api/types';
import Sidebar from './components/Sidebar';
import ChatView from './components/ChatView';
import ReportView from './components/ReportView';
import InvestmentFactorRanking from './components/InvestmentFactorRanking';
import GraphUpdateView from './components/GraphUpdateView';
import DataIngestView from './components/DataIngestView';

function makeNewSessionId() {
  // Match backend style, but any unique string works
  return `session_${uuidv4().slice(0, 8)}`;
}

export default function App() {
  const [generalSessions, setGeneralSessions] = useState<SessionDetail[]>([]);
  const [reportSessions, setReportSessions] = useState<SessionDetail[]>([]);
  const [selectedGeneralSessionId, setSelectedGeneralSessionId] = useState<string | null>(null);
  const [selectedReportSessionId, setSelectedReportSessionId] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'general' | 'report' | 'investment' | 'graph' | 'ingest'>('general');
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [graphSessions, setGraphSessions] = useState<SessionDetail[]>([]);
  const [selectedGraphSessionId, setSelectedGraphSessionId] = useState<string | null>(null);

  const refreshGeneralSessions = async () => {
    const res: SessionsResponse = await listSessions();
    setGeneralSessions(res.sessions ?? []);
  };
  const refreshReportSessions = async () => {
    const res: SessionsResponse = await listReportSessions();
    setReportSessions(res.sessions ?? []);
  };
  const refreshGraphSessions = async () => {
    const res: SessionsResponse = await listGraphUpdateSessions();
    setGraphSessions(res.sessions ?? []);
  };
  const refreshSessions = async () => {
    try {
      setLoadingSessions(true);
      setError(null);
      await Promise.all([refreshGeneralSessions(), refreshReportSessions(), refreshGraphSessions()]);
    } catch (e: any) {
      console.error('Failed to load sessions:', e);
      setError('Failed to load sessions');
    } finally {
      setLoadingSessions(false);
    }
  };

  useEffect(() => {
    refreshSessions();
  }, []);

  // Refresh the visible tab's sessions when switching tabs
  useEffect(() => {
    (async () => {
      try {
        setLoadingSessions(true);
        if (activeTab === 'general') {
          await refreshGeneralSessions();
        } else if (activeTab === 'report') {
          await refreshReportSessions();
        } else if (activeTab === 'graph') {
          await refreshGraphSessions();
        } else {
          // investment tab has no sessions
        }
      } catch (e) {
        console.warn('Failed to refresh sessions for tab', activeTab, e);
      } finally {
        setLoadingSessions(false);
      }
    })();
  }, [activeTab]);

  const onSelectSession = (id: string) => {
    if (activeTab === 'general') setSelectedGeneralSessionId(id);
    else if (activeTab === 'report') setSelectedReportSessionId(id);
    else if (activeTab === 'graph') setSelectedGraphSessionId(id);
    else return; // no sessions on investment tab
  };

  const onNewChat = () => {
    const id = makeNewSessionId();
    if (activeTab === 'general') {
      setSelectedGeneralSessionId(id);
      setGeneralSessions(prev => (prev.find(s => s.session_id === id) ? prev : [{ session_id: id, message_count: 0 }, ...prev]));
    } else if (activeTab === 'report') {
      setSelectedReportSessionId(id);
      setReportSessions(prev => (prev.find(s => s.session_id === id) ? prev : [{ session_id: id, message_count: 0 }, ...prev]));
    } else if (activeTab === 'graph') {
      setSelectedGraphSessionId(id);
      setGraphSessions(prev => (prev.find(s => s.session_id === id) ? prev : [{ session_id: id, message_count: 0 }, ...prev]));
    } else {
      // no-op for investment tab
    }
  };

  const deleteSession = async (id: string) => {
    try {
      if (activeTab === 'general') await apiDeleteSession(id);
      else if (activeTab === 'report') await apiDeleteReport(id);
      else if (activeTab === 'graph') await apiDeleteGraphUpdate(id);
      else return;
    } catch (e) {
      console.warn('Delete failed (maybe not persisted yet):', e);
    } finally {
      if (activeTab === 'general') {
        if (selectedGeneralSessionId === id) setSelectedGeneralSessionId(null);
      } else if (activeTab === 'report') {
        if (selectedReportSessionId === id) setSelectedReportSessionId(null);
      } else if (activeTab === 'graph') {
        if (selectedGraphSessionId === id) setSelectedGraphSessionId(null);
      }
      await refreshSessions();
    }
  };

  const clearAllSessions = async () => {
    try {
      if (activeTab === 'general') await apiClearAll();
      else if (activeTab === 'report') await apiClearAllReport();
      else if (activeTab === 'graph') await apiClearAllGraphUpdate();
      else return;
    } catch (e) {
      console.warn('Clear all failed:', e);
    } finally {
      if (activeTab === 'general') setSelectedGeneralSessionId(null);
      else if (activeTab === 'report') setSelectedReportSessionId(null);
      else if (activeTab === 'graph') setSelectedGraphSessionId(null);
      await refreshSessions();
    }
  };

  const onAfterSendGeneral = async () => {
    await refreshGeneralSessions();
  };
  const onAfterSendReport = async () => {
    await refreshReportSessions();
  };
  const onAfterSendGraph = async () => {
    await refreshGraphSessions();
  };

  const sidebarSessions = useMemo(() => (
    activeTab === 'general' ? generalSessions : activeTab === 'report' ? reportSessions : activeTab === 'graph' ? graphSessions : []
  ), [activeTab, generalSessions, reportSessions, graphSessions]);

  return (
    <div className="app-root">
      <Sidebar
        sessions={sidebarSessions}
        selectedSessionId={activeTab === 'general' ? selectedGeneralSessionId : activeTab === 'report' ? selectedReportSessionId : activeTab === 'graph' ? selectedGraphSessionId : null}
        onSelectSession={onSelectSession}
        onNewChat={onNewChat}
        onDeleteSession={deleteSession}
        onClearAll={clearAllSessions}
        loading={loadingSessions}
        error={error}
        headerMode={activeTab === 'investment' || activeTab === 'ingest' ? 'none' : 'chat'}
        headerLabel={activeTab === 'report' ? '+ New Report' : activeTab === 'graph' ? '+ New Update Session' : '+ New Chat'}
        className={mobileSidebarOpen ? 'mobile-open' : undefined}
      />
      {mobileSidebarOpen && <div className="mobile-backdrop" onClick={() => setMobileSidebarOpen(false)} />}
      <div className="content">
        <div className="topbar">
          <div className="brand">
            <span className="logo" aria-hidden="true">◎</span>
            <span>Get-Deep Assistant</span>
          </div>
          <button
            className="icon-button menu-btn"
            aria-label="Toggle sidebar"
            onClick={() => setMobileSidebarOpen(s => !s)}
            title="Toggle sidebar"
          >
            ☰
          </button>
        </div>
        <div className="tabs" role="tablist" aria-label="Modes">
          <button
            className={['btn', activeTab === 'general' ? 'primary' : ''].join(' ')}
            role="tab"
            aria-selected={activeTab === 'general'}
            onClick={() => setActiveTab('general')}
          >
            General
          </button>
          <button
            className={['btn', activeTab === 'report' ? 'primary' : ''].join(' ')}
            role="tab"
            aria-selected={activeTab === 'report'}
            onClick={() => setActiveTab('report')}
          >
            Report Generation
          </button>
          <button
            className={['btn', activeTab === 'investment' ? 'primary' : ''].join(' ')}
            role="tab"
            aria-selected={activeTab === 'investment'}
            onClick={() => setActiveTab('investment')}
          >
            Investment Factor Ranking
          </button>
          <button
            className={['btn', activeTab === 'graph' ? 'primary' : ''].join(' ')}
            role="tab"
            aria-selected={activeTab === 'graph'}
            onClick={() => setActiveTab('graph')}
          >
            Update Graph DB
          </button>
          <button
            className={['btn', activeTab === 'ingest' ? 'primary' : ''].join(' ')}
            role="tab"
            aria-selected={activeTab === 'ingest'}
            onClick={() => setActiveTab('ingest')}
          >
            Manage Neo4j
          </button>
        </div>

        {activeTab === 'ingest' ? (
          <DataIngestView />
        ) : activeTab === 'graph' ? (
          selectedGraphSessionId ? (
            <GraphUpdateView sessionId={selectedGraphSessionId as string} onAfterSend={onAfterSendGraph} />
          ) : (
            <div className="empty-state">
              <h2>Start a new update session</h2>
              <p>Create a new graph update session or pick one from the left.</p>
              <button className="btn primary" onClick={onNewChat}>New Update Session</button>
            </div>
          )
        ) : activeTab === 'investment' ? (
          <InvestmentFactorRanking />
        ) : ( (activeTab === 'general' ? selectedGeneralSessionId : selectedReportSessionId) ? (
          activeTab === 'general' ? (
            <ChatView sessionId={selectedGeneralSessionId as string} onAfterSend={onAfterSendGeneral} />
          ) : (
            <ReportView sessionId={selectedReportSessionId as string} onAfterSend={onAfterSendReport} />
          )
        ) : (
          <div className="empty-state">
            <h2>{activeTab === 'general' ? 'Start a new chat' : 'Start a new report'}</h2>
            <p>Create a new conversation or pick one from the left.</p>
            <button className="btn primary" onClick={onNewChat}>
              {activeTab === 'general' ? 'New Chat' : 'New Report Session'}
            </button>
          </div>
        ) )}
      </div>
    </div>
  );
}
