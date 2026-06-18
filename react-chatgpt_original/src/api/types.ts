export interface ChatQARequest {
  question: string;
  session_id?: string | null;
  base64_images?: string[];
  base64_files?: string[];
  base64_audios?: string[];
  // If true, backend will try to generate a base64 PDF report (returned as report_base64)
  report_requred?: boolean;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  total_cost: number;
}

export interface OutputImageData {
  image_path: string;
  description?: string;
}

export interface Base64ImageData {
  image_base64: string | null;
  description?: string;
}

export interface ChatQAResponse {
  answer: string;
  success: boolean;
  execution_time: string; // e.g., "0.42 seconds"
  token_usage: TokenUsage;
  source?: Array<Record<string, unknown>>;
  output_images_data?: OutputImageData[];
  base64_images?: Base64ImageData[];
  // Present only for deep search responses: base64-encoded PDF report
  report_base64?: string;
}

export interface StreamDoneEvent {
  type: 'done';
  session_id: string;
  answer?: string;
  source_details?: Array<Record<string, unknown>>;
  output_images_data?: OutputImageData[];
  base64_images?: Base64ImageData[];
  // Present only for deep search stream final event
  report_base64?: string;
  execution_time?: string; // e.g., "0.42 seconds"
  token_usage?: TokenUsage;
}

export interface SessionDetail {
  session_id: string;
  message_count: number;
  error?: string;
}

export interface SessionsResponse {
  sessions: SessionDetail[];
  total_count: number;
}

export type SessionMessageTuple = [string, string]; // [msg_type, content], e.g., ["HumanMessage", "Hello"]

export interface SessionHistory {
  session_id: string;
  messages: SessionMessageTuple[];
  exists?: boolean;
  error?: string;
}

export interface SessionResponse {
  session_id: string;
  history: {
    session_id: string;
  // messages may be missing if backend error; keep optional and default to []
    messages?: SessionMessageTuple[];
    exists?: boolean;
    error?: string;
  };
  message_count: number;
}

export interface DeleteResponse {
  message: string;
  session_id?: string;
  deleted_count?: number;
}

export type ReportType =
  | 'company_performance_and_investment_thesis'
  | 'industry_deep_drive';

export interface ReportRequest {
  instructions?: string;
  report_type: ReportType;
  time_horizon?: string;
  ticker?: string;
  company_name?: string;
  industry_name?: string;
  session_id?: string | null;

  // Optional fields to satisfy streaming endpoint inconsistencies
  question?: string; // will mirror instructions for streaming
  base64_images?: string[];
  base64_files?: string[];
  base64_audios?: string[];
}

export interface Sector {
  sectorId?: string;
  sectorName?: string;
  [k: string]: any;
}

export interface Industry {
  industryId?: string;
  industryName?: string;
  [k: string]: any;
}

export interface Company {
  companyId?: string;
  companyName?: string;
  ticker?: string;
  [k: string]: any;
}

export interface GraphCypherResponse {
  records: Array<Record<string, any>>;
  summary?: Record<string, any>;
}

// Investment Factor Ranking types
export interface InvestmentFactorRow {
  'Overall Rank': number;
  'Ticker': string;
  'ROIC 5Y Avg': string; // includes value and rank like "0.1234 (5)"
  'Earnings Yield': string;
  'Intrinsic to Market Cap': string;
}

export interface InvestmentFactorResponse {
  table: InvestmentFactorRow[];
  rejected: Array<{ ticker: string; reasons: Record<string, string> }>
}
