# Frontend Documentation

The Get-Deep frontend is a modern React-based web application that provides an intuitive interface for interacting with the AI agents. Built with TypeScript and Vite, it offers real-time chat functionality, session management, and rich content display.

## 🏗️ Frontend Architecture

### Technology Stack

- **React 18**: Modern React with hooks and functional components
- **TypeScript**: Type-safe JavaScript development
- **Vite**: Fast build tool and development server
- **Axios**: HTTP client for API communication
- **React Markdown**: Markdown rendering with GitHub Flavored Markdown
- **UUID**: Unique identifier generation

### Project Structure

```
react-chatgpt_original/
├── src/
│   ├── components/          # Reusable UI components
│   ├── hooks/              # Custom React hooks
│   ├── services/           # API service layer
│   ├── types/              # TypeScript type definitions
│   ├── utils/              # Utility functions
│   ├── styles/             # CSS and styling
│   ├── App.tsx             # Main application component
│   └── main.tsx            # Application entry point
├── public/                 # Static assets
├── index.html              # HTML template
├── package.json            # Dependencies and scripts
├── tsconfig.json           # TypeScript configuration
└── vite.config.ts         # Vite build configuration
```

## 📦 Dependencies and Setup

### Package Configuration

```json
{
  "name": "react-chatgpt",
  "version": "0.0.1",
  "type": "module",
  "dependencies": {
    "axios": "^1.7.9",           // API communication
    "react": "^18.3.1",          // React framework
    "react-dom": "^18.3.1",      // React DOM rendering
    "react-markdown": "^10.1.0", // Markdown rendering
    "remark-gfm": "^4.0.1",     // GitHub Flavored Markdown
    "uuid": "^9.0.1"            // UUID generation
  },
  "devDependencies": {
    "@types/react": "^18.3.5",         // React type definitions
    "@types/react-dom": "^18.3.0",     // React DOM types
    "@types/uuid": "^9.0.7",           // UUID types
    "@vitejs/plugin-react": "^4.3.1",  // Vite React plugin
    "typescript": "^5.6.2",            // TypeScript compiler
    "vite": "^5.3.0"                   // Build tool
  }
}
```

### Development Setup

```bash
# Navigate to frontend directory
cd react-chatgpt_original/

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Vite Configuration

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})
```

## 🔧 Core Components

### Main Application Component

```typescript
// src/App.tsx
import React, { useState, useEffect } from 'react';
import ChatInterface from './components/ChatInterface';
import SessionManager from './components/SessionManager';
import AgentSelector from './components/AgentSelector';
import { ChatSession, AgentType } from './types';

const App: React.FC = () => {
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<AgentType>('general');
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    // Load existing sessions from API
    const response = await fetch('/api/sessions');
    const sessionData = await response.json();
    setSessions(sessionData);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Get-Deep AI Assistant</h1>
        <AgentSelector 
          selectedAgent={selectedAgent}
          onAgentChange={setSelectedAgent}
        />
      </header>
      
      <main className="app-main">
        <aside className="sidebar">
          <SessionManager 
            sessions={sessions}
            currentSession={currentSession}
            onSessionSelect={setCurrentSession}
            onNewSession={createNewSession}
          />
        </aside>
        
        <section className="chat-area">
          <ChatInterface 
            session={currentSession}
            agentType={selectedAgent}
            onMessageSent={handleMessageSent}
          />
        </section>
      </main>
    </div>
  );
};
```

### Chat Interface Component

```typescript
// src/components/ChatInterface.tsx
import React, { useState, useRef, useEffect } from 'react';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import { Message, ChatSession, AgentType } from '../types';
import { chatService } from '../services/chatService';

interface ChatInterfaceProps {
  session: ChatSession | null;
  agentType: AgentType;
  onMessageSent: (message: Message) => void;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  session,
  agentType,
  onMessageSent
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (content: string) => {
    if (!session || isLoading) return;

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date(),
      sessionId: session.id
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await chatService.sendMessage({
        message: content,
        sessionId: session.id,
        agentType,
        stream: true
      });

      const aiMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        sessionId: session.id,
        metadata: response.metadata
      };

      setMessages(prev => [...prev, aiMessage]);
      onMessageSent(aiMessage);
    } catch (error) {
      console.error('Failed to send message:', error);
      // Handle error - show error message
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-interface">
      <MessageList messages={messages} isLoading={isLoading} />
      <div ref={messagesEndRef} />
      <MessageInput 
        onSendMessage={handleSendMessage}
        disabled={isLoading || !session}
        placeholder={`Message ${agentType} agent...`}
      />
    </div>
  );
};
```

### Message Components

```typescript
// src/components/MessageList.tsx
import React from 'react';
import MessageItem from './MessageItem';
import LoadingIndicator from './LoadingIndicator';
import { Message } from '../types';

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
}

const MessageList: React.FC<MessageListProps> = ({ messages, isLoading }) => {
  return (
    <div className="message-list">
      {messages.map(message => (
        <MessageItem key={message.id} message={message} />
      ))}
      {isLoading && <LoadingIndicator />}
    </div>
  );
};

// src/components/MessageItem.tsx
import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Message } from '../types';

interface MessageItemProps {
  message: Message;
}

const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  const isUser = message.role === 'user';
  
  return (
    <div className={`message-item ${isUser ? 'user' : 'assistant'}`}>
      <div className="message-avatar">
        {isUser ? '👤' : '🤖'}
      </div>
      <div className="message-content">
        <div className="message-header">
          <span className="message-role">{isUser ? 'You' : 'AI'}</span>
          <span className="message-timestamp">
            {message.timestamp.toLocaleTimeString()}
          </span>
        </div>
        <div className="message-body">
          {isUser ? (
            <p>{message.content}</p>
          ) : (
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                code: CodeBlock,
                table: TableComponent,
                img: ImageComponent
              }}
            >
              {message.content}
            </ReactMarkdown>
          )}
        </div>
        {message.metadata && (
          <MessageMetadata metadata={message.metadata} />
        )}
      </div>
    </div>
  );
};
```

### Agent Selector Component

```typescript
// src/components/AgentSelector.tsx
import React from 'react';
import { AgentType } from '../types';

interface AgentSelectorProps {
  selectedAgent: AgentType;
  onAgentChange: (agent: AgentType) => void;
}

const AGENT_OPTIONS = [
  {
    type: 'general' as AgentType,
    name: 'General Agent',
    description: 'Multi-purpose conversations and basic analysis',
    icon: '💬'
  },
  {
    type: 'deep' as AgentType,
    name: 'Deep Agent',
    description: 'Advanced reasoning and complex problem solving',
    icon: '🧠'
  },
  {
    type: 'report' as AgentType,
    name: 'Report Generator',
    description: 'Comprehensive reports and document generation',
    icon: '📊'
  },
  {
    type: 'update' as AgentType,
    name: 'Update Agent',
    description: 'Database updates and maintenance',
    icon: '🔧'
  }
];

const AgentSelector: React.FC<AgentSelectorProps> = ({
  selectedAgent,
  onAgentChange
}) => {
  return (
    <div className="agent-selector">
      <label>Select AI Agent:</label>
      <div className="agent-options">
        {AGENT_OPTIONS.map(agent => (
          <button
            key={agent.type}
            className={`agent-option ${
              selectedAgent === agent.type ? 'selected' : ''
            }`}
            onClick={() => onAgentChange(agent.type)}
            title={agent.description}
          >
            <span className="agent-icon">{agent.icon}</span>
            <span className="agent-name">{agent.name}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
```

## 🔗 API Service Layer

### Chat Service

```typescript
// src/services/chatService.ts
import axios from 'axios';
import { ChatRequest, ChatResponse, AgentType } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 minutes for complex operations
});

// Request interceptor for authentication
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

export const chatService = {
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const endpoint = getAgentEndpoint(request.agentType);
    
    const response = await apiClient.post(endpoint, {
      message: request.message,
      session_id: request.sessionId,
      stream: request.stream || false
    });

    return response.data;
  },

  async streamMessage(
    request: ChatRequest,
    onChunk: (chunk: string) => void
  ): Promise<void> {
    const endpoint = getAgentEndpoint(request.agentType);
    
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: request.message,
        session_id: request.sessionId,
        stream: true
      })
    });

    if (!response.body) {
      throw new Error('Streaming not supported');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;
        
        const chunk = decoder.decode(value);
        onChunk(chunk);
      }
    } finally {
      reader.releaseLock();
    }
  }
};

function getAgentEndpoint(agentType: AgentType): string {
  const endpoints = {
    general: '/general-chat',
    deep: '/deep-chat',
    report: '/report-generation',
    update: '/update-neo4j'
  };
  
  return endpoints[agentType] || endpoints.general;
}
```

### Session Service

```typescript
// src/services/sessionService.ts
import { apiClient } from './apiClient';
import { ChatSession } from '../types';

export const sessionService = {
  async getSessions(): Promise<ChatSession[]> {
    const response = await apiClient.get('/sessions');
    return response.data;
  },

  async getSession(sessionId: string): Promise<ChatSession> {
    const response = await apiClient.get(`/sessions/${sessionId}`);
    return response.data;
  },

  async createSession(agentType: string): Promise<ChatSession> {
    const response = await apiClient.post('/sessions', {
      agent_type: agentType
    });
    return response.data;
  },

  async deleteSession(sessionId: string): Promise<void> {
    await apiClient.delete(`/sessions/${sessionId}`);
  },

  async updateSession(sessionId: string, updates: Partial<ChatSession>): Promise<ChatSession> {
    const response = await apiClient.patch(`/sessions/${sessionId}`, updates);
    return response.data;
  }
};
```

## 📱 TypeScript Types

### Core Type Definitions

```typescript
// src/types/index.ts
export type AgentType = 'general' | 'deep' | 'report' | 'update';

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  sessionId: string;
  metadata?: MessageMetadata;
}

export interface MessageMetadata {
  toolOutputs?: any[];
  charts?: ChartData[];
  attachments?: Attachment[];
  processingTime?: number;
  tokensUsed?: number;
}

export interface ChatSession {
  id: string;
  name?: string;
  agentType: AgentType;
  createdAt: Date;
  lastActivity: Date;
  messageCount: number;
  isActive: boolean;
}

export interface ChatRequest {
  message: string;
  sessionId?: string;
  agentType: AgentType;
  stream?: boolean;
  attachments?: File[];
}

export interface ChatResponse {
  response: string;
  sessionId: string;
  toolOutputs?: any[];
  charts?: ChartData[];
  metadata?: any;
}

export interface ChartData {
  type: 'line' | 'bar' | 'pie' | 'scatter';
  data: any;
  title?: string;
  description?: string;
}

export interface Attachment {
  id: string;
  filename: string;
  type: string;
  size: number;
  url: string;
}
```

## 🎨 Styling and UI

### CSS Architecture

```css
/* src/styles/main.css */
:root {
  --primary-color: #007bff;
  --secondary-color: #6c757d;
  --success-color: #28a745;
  --danger-color: #dc3545;
  --warning-color: #ffc107;
  --info-color: #17a2b8;
  
  --background-color: #f8f9fa;
  --surface-color: #ffffff;
  --text-color: #212529;
  --text-muted: #6c757d;
  
  --border-radius: 8px;
  --box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  --transition: all 0.3s ease;
}

.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.app-header {
  background: var(--surface-color);
  border-bottom: 1px solid #dee2e6;
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.app-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.sidebar {
  width: 300px;
  background: var(--surface-color);
  border-right: 1px solid #dee2e6;
  overflow-y: auto;
}

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--background-color);
}
```

### Component-Specific Styles

```css
/* Message Styling */
.message-item {
  display: flex;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid #f1f3f5;
}

.message-item.user {
  background: #f8f9ff;
  flex-direction: row-reverse;
}

.message-item.assistant {
  background: var(--surface-color);
}

.message-content {
  flex: 1;
  max-width: 100%;
}

.message-body {
  margin-top: 8px;
  line-height: 1.6;
}

/* Code block styling */
.message-body pre {
  background: #f6f8fa;
  border-radius: var(--border-radius);
  padding: 16px;
  overflow-x: auto;
  border: 1px solid #e1e4e8;
}

.message-body code {
  background: #f6f8fa;
  padding: 2px 4px;
  border-radius: 3px;
  font-family: 'SFMono-Regular', Consolas, monospace;
}

/* Agent selector styling */
.agent-selector {
  display: flex;
  align-items: center;
  gap: 16px;
}

.agent-options {
  display: flex;
  gap: 8px;
}

.agent-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border: 2px solid #e1e4e8;
  border-radius: var(--border-radius);
  background: var(--surface-color);
  cursor: pointer;
  transition: var(--transition);
}

.agent-option:hover {
  border-color: var(--primary-color);
}

.agent-option.selected {
  border-color: var(--primary-color);
  background: #f0f7ff;
}
```

## 🔧 Custom Hooks

### Chat Management Hook

```typescript
// src/hooks/useChat.ts
import { useState, useCallback } from 'react';
import { Message, ChatSession, AgentType } from '../types';
import { chatService } from '../services/chatService';

export const useChat = (session: ChatSession | null, agentType: AgentType) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = useCallback(async (content: string) => {
    if (!session || isLoading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: new Date(),
      sessionId: session.id
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await chatService.sendMessage({
        message: content,
        sessionId: session.id,
        agentType
      });

      const aiMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        sessionId: session.id,
        metadata: response.metadata
      };

      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      // Add error message to chat
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: 'system',
        content: 'Failed to send message. Please try again.',
        timestamp: new Date(),
        sessionId: session.id
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [session, agentType, isLoading]);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    messages,
    isLoading,
    sendMessage,
    clearMessages
  };
};
```

## 🚀 Build and Deployment

### Production Build

```bash
# Build for production
npm run build

# The dist/ folder contains the production build
# Serve with any static file server:
npx serve dist/

# Or integrate with backend serving
```

### Environment Configuration

```typescript
// Environment variables (in .env files)
VITE_API_BASE_URL=http://localhost:8080  # Development
VITE_API_BASE_URL=https://api.yourdomain.com  # Production

VITE_APP_NAME="Get-Deep AI Assistant"
VITE_APP_VERSION="1.0.0"
```

### Integration with Backend

The frontend can be served:
1. **Standalone**: Separate React dev server or static hosting
2. **Integrated**: Served by FastAPI as static files

```python
# For integrated serving, add to FastAPI app:
from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory="react-chatgpt_original/dist", html=True), name="frontend")
```

---

This comprehensive frontend documentation provides everything needed to understand, develop, and extend the Get-Deep React application, including component architecture, API integration, styling, and deployment strategies.
