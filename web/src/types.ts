export type Tab =
  | "home"
  | "watch"
  | "health"
  | "assistant"
  | "config";
export type Priority = 1 | 2 | 3;

export type Source = {
  name: string;
  url: string;
  keys: string[];
  priorité: Priority;
  enabled?: boolean;
  max_items?: number;
};

export type Category = {
  name: string;
  color?: string;
  sources: Source[];
};

export type Config = {
  app?: { name?: string; description?: string };
  collection?: { max_age_days?: number };
  tags: Record<string, string[]>;
  categories: Category[];
};

export type Article = {
  id: string;
  title: string;
  url: string;
  source: string;
  category: string;
  summary: string;
  published_at: string;
  collected_at: string;
  score: number;
  tags: string[];
  keys: string[];
  priorité: Priority;
  view: boolean;
  candidate: "good" | "bad" | null;
};

export type Stats = {
  total: number;
  sources: number;
  collected_sources: number;
  new_signals: number | null;
  priority_one_recent: number;
  last_collection: string | null;
  last_collection_sources: number | null;
  last_collection_failed_sources: number | null;
  last_collection_successful_sources: number | null;
};

export type SummaryDocument = {
  content: string;
  updated_at: string | null;
};

export type AsyncState = {
  running: boolean;
  started_at: string | null;
  finished_at: string | null;
  result: {
    sources: number;
    failed_sources?: number;
    articles: number;
    new?: number;
    duplicates?: number;
    summary?: {
      generated: boolean;
      signals: number;
      sections: number;
      planning_mode: "llm" | "fallback" | null;
      path: string;
    } | null;
    summarizer?: {
      generated: boolean;
      reused: boolean;
      path: string | null;
      chars: number;
    } | null;
    errors: string[];
  } | null;
  error: string | null;
  progress: {
    stage:
      | "idle"
      | "fetch"
      | "storage"
      | "embedding"
      | "summary"
      | "summarizer"
      | "telegram";
    label: string;
    percent: number;
    completed: number;
    total: number;
    failed: number;
  };
};

export type SourceHealth = {
  source: string;
  category: string;
  url: string;
  last_attempt_at: string | null;
  last_success_at: string | null;
  latency_ms: number;
  http_status: number | null;
  last_error: string | null;
  last_item_count: number;
  total_successes: number;
  total_failures: number;
};

export type CollectionRun = {
  id: number;
  trigger: "manual" | "systemd";
  started_at: string;
  finished_at: string | null;
  status: "running" | "completed" | "completed_with_errors" | "failed";
  result: AsyncState["result"];
  error: string | null;
};

export type AssistantStatus = {
  available: boolean;
  url: string;
  model: string;
  error: string | null;
};

export type TelegramStatus = {
  enabled: boolean;
  ready: boolean;
  token_configured: boolean;
  chat_configured: boolean;
  max_message_chars: number;
  report_pending: boolean;
  last_sent_at: string | null;
};

export type AutomationStatus = {
  configured: boolean;
  calendar: string | null;
  times: string[];
  persistent: boolean;
};

export type AppHealth = {
  uptime_seconds: number;
  storage_bytes: number;
  signals_total: number;
  signals_p1: number;
  sources_healthy: number;
  sources_failing: number;
  assistant: AssistantStatus;
  telegram: TelegramStatus;
  automation: AutomationStatus;
  rag_index: {
    pending: boolean;
    last_attempt_at: string | null;
    last_success_at: string | null;
    last_error: string | null;
  };
};
