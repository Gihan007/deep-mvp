import React from 'react';
import type { SessionDetail } from '../api/types';

interface Props {
  sessions: SessionDetail[];
  selectedSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
  onClearAll: () => void;
  loading?: boolean;
  error?: string | null;
  headerMode?: 'chat' | 'none';
  className?: string;
  headerLabel?: string;
}

export default function Sidebar({
  sessions,
  selectedSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onClearAll,
  loading,
  error,
  headerMode = 'chat',
  className,
  headerLabel,
}: Props) {
  return (
    <aside className={["sidebar", className || ''].join(' ').trim()}>
      {headerMode === 'chat' && (
        <div className="sidebar-header">
          <button className="btn primary full" onClick={onNewChat}>{headerLabel || '+ New Chat'}</button>
        </div>
      )}

      <div className="sidebar-body">
        {loading ? (
          <div className="muted">Loading sessions...</div>
        ) : error ? (
          <div className="error">{error}</div>
        ) : sessions.length === 0 ? (
          <div className="muted">No sessions yet</div>
        ) : (
          <ul className="session-list">
            {sessions.map((s) => (
              <li
                key={s.session_id}
                className={['session-item', s.session_id === selectedSessionId ? 'active' : ''].join(' ')}
              >
                <button
                  className="session-button"
                  onClick={() => onSelectSession(s.session_id)}
                  title={s.session_id}
                >
                  <span className="session-title">{s.session_id}</span>
                  <span className="session-count">{s.message_count}</span>
                </button>
                <button
                  className="icon-button danger"
                  onClick={() => onDeleteSession(s.session_id)}
                  title="Delete session"
                >
                  🗑️
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {headerMode === 'chat' && (
        <div className="sidebar-footer">
          <button className="btn danger full" onClick={onClearAll}>Clear All</button>
        </div>
      )}
    </aside>
  );
}
