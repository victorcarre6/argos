export type Tab =
  | "watch"
  | "digest"
  | "health"
  | "viz"
  | "assistant"
  | "sources";
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
  keywords?: string[];
  sources: Source[];
};

export type Config = {
  app?: { name?: string; description?: string };
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
};

export type Stats = {
  total: number;
  sources: number;
  last_collection: string | null;
};

export type AsyncState = {
  running: boolean;
  started_at: string | null;
  finished_at: string | null;
  result: {
    sources: number;
    articles: number;
    new?: number;
    duplicates?: number;
    errors: string[];
  } | null;
  error: string | null;
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

export type AssistantStatus = {
  available: boolean;
  url: string;
  model: string;
  error: string | null;
};

export type AppHealth = {
  uptime_seconds: number;
  database_bytes: number;
  articles: number;
  duplicates: number;
  sources_healthy: number;
  sources_failing: number;
  assistant: AssistantStatus;
};

export type Cluster = {
  id: string;
  name: string;
  auto_name: string;
  size: number;
  titles: string[];
};

export type ClusterResponse = {
  clusters: Cluster[];
  state: AsyncState;
};

export type HeatCell = { x: string; y: string; value: number };

export type SemanticPoint = {
  id: string;
  title: string;
  summary: string;
  url: string;
  source: string;
  category: string;
  score: number;
  cluster_id: string | null;
  cluster_name: string | null;
  color: string;
  x: number;
  y: number;
};
