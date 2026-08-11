import {
  Activity,
  Bot,
  CalendarDays,
  Database,
  Rss,
  Settings2,
  Waves,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { api, jsonRequest } from "./lib/api";
import type {
  AppHealth,
  AssistantStatus,
  AsyncState,
  Config,
  ClusterResponse,
  HeatCell,
  SourceHealth,
  Stats,
  Tab,
  Article,
} from "./types";
import { AssistantView } from "./views/AssistantView";
import { DigestView } from "./views/DigestView";
import { HealthView } from "./views/HealthView";
import { SourcesView } from "./views/SourcesView";
import { VizView } from "./views/VizView";
import { WatchView } from "./views/WatchView";

const EMPTY_CONFIG: Config = { categories: [] };
const EMPTY_ASYNC_STATE: AsyncState = {
  running: false,
  started_at: null,
  finished_at: null,
  result: null,
  error: null,
};

const NAVIGATION: { value: Tab; label: string; icon: typeof Rss }[] = [
  { value: "watch", label: "Flux", icon: Rss },
  { value: "digest", label: "Digest", icon: CalendarDays },
  { value: "health", label: "Santé", icon: Activity },
  { value: "viz", label: "Viz", icon: Waves },
  { value: "assistant", label: "Assistant", icon: Bot },
  { value: "sources", label: "Sources", icon: Settings2 },
];

async function loadResource<T>(
  path: string,
  apply: (value: T) => void,
): Promise<string | null> {
  try {
    apply(await api<T>(path));
    return null;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return `${path} : ${message}`;
  }
}

function AppShell({
  tab,
  stats,
  error,
  onTabChange,
  children,
}: {
  tab: Tab;
  stats: Stats;
  error: string;
  onTabChange: (tab: Tab) => void;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background text-foreground md:flex">
      <aside className="border-b border-border bg-muted md:min-h-screen md:w-60 md:border-b-0 md:border-r">
        <div className="p-5">
          <div className="flex items-center gap-2">
            <div className="flex size-8 items-center justify-center rounded-lg bg-brand text-brand-foreground">
              <Rss className="size-4" />
            </div>
            <div>
              <h1 className="font-semibold">Argos</h1>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                RSS Monitor
              </p>
            </div>
          </div>
        </div>

        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col">
          {NAVIGATION.map((item) => {
            const Icon = item.icon;
            const active = tab === item.value;
            return (
              <button
                key={item.value}
                onClick={() => onTabChange(item.value)}
                className={`flex shrink-0 items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                  active
                    ? "bg-background font-medium text-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                <Icon className="size-4" />
                {item.label}
                {item.value === "assistant" && (
                  <span className="ml-auto rounded bg-warning/15 px-1.5 py-0.5 text-[10px] text-warning">
                    WIP
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="hidden px-5 pt-6 text-xs text-muted-foreground md:block">
          <div className="flex items-center gap-2">
            <Database className="size-3" />
            Atlas · :1207
          </div>
          <div className="mt-2">{stats.total} signaux indexés</div>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <header className="border-b border-border bg-background/80 px-6 py-4 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center justify-end">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Activity className="size-4 text-success" />
              Opérationnel
            </div>
          </div>
        </header>
        <div className="mx-auto max-w-7xl px-6 py-6">
          {error && (
            <div className="mb-4 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
              {error}
            </div>
          )}
          <ErrorBoundary key={tab}>{children}</ErrorBoundary>
        </div>
      </main>
    </div>
  );
}

export function App() {
  const [tab, setTab] = useState<Tab>("watch");
  const [config, setConfig] = useState<Config>(EMPTY_CONFIG);
  const [articles, setArticles] = useState<Article[]>([]);
  const [stats, setStats] = useState<Stats>({
    total: 0,
    sources: 0,
    last_collection: null,
  });
  const [collection, setCollection] = useState<AsyncState>(EMPTY_ASYNC_STATE);
  const [appHealth, setAppHealth] = useState<AppHealth | null>(null);
  const [sourceHealth, setSourceHealth] = useState<SourceHealth[]>([]);
  const [clusters, setClusters] = useState<ClusterResponse | null>(null);
  const [heat, setHeat] = useState<HeatCell[]>([]);
  const [assistantStatus, setAssistantStatus] =
    useState<AssistantStatus | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const refreshInProgress = useRef(false);

  const refresh = useCallback(async () => {
    if (refreshInProgress.current) return;
    refreshInProgress.current = true;

    const failures = await Promise.all([
      loadResource<Config>("/sources", setConfig),
      loadResource<{ articles: Article[] }>("/articles?limit=400", (value) =>
        setArticles(value.articles),
      ),
      loadResource<Stats>("/stats", setStats),
      loadResource<AsyncState>("/refresh", setCollection),
      loadResource<AppHealth>("/health/app", setAppHealth),
      loadResource<{ sources: SourceHealth[] }>("/health/sources", (value) =>
        setSourceHealth(value.sources),
      ),
      loadResource<ClusterResponse>("/clusters", setClusters),
      loadResource<{ cells: HeatCell[] }>("/viz/heatmap", (value) =>
        setHeat(value.cells),
      ),
      loadResource<AssistantStatus>("/assistant/status", setAssistantStatus),
    ]);

    const messages = failures.filter((failure): failure is string =>
      Boolean(failure),
    );
    setError(
      messages.length
        ? `Rafraîchissement partiel — ${messages.join(" | ")}`
        : "",
    );
    refreshInProgress.current = false;
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 10_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const startCollection = async () => {
    try {
      setCollection(await api<AsyncState>("/refresh", { method: "POST" }));
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Collecte impossible",
      );
    }
  };

  const saveSources = async () => {
    setSaving(true);
    try {
      await api("/sources", jsonRequest("PUT", config));
      await refresh();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Enregistrement impossible",
      );
    } finally {
      setSaving(false);
    }
  };

  const refreshClusters = async () => {
    try {
      await api("/clusters", { method: "POST" });
      await refresh();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Clustering impossible",
      );
    }
  };

  let content: ReactNode;
  switch (tab) {
    case "watch":
      content = (
        <WatchView
          config={config}
          stats={stats}
          articles={articles}
          collection={collection}
          onCollect={startCollection}
        />
      );
      break;
    case "digest":
      content = <DigestView articles={articles} />;
      break;
    case "health":
      content = (
        <HealthView
          appHealth={appHealth}
          sources={sourceHealth}
          config={config}
          refresh={() => void refresh()}
        />
      );
      break;
    case "viz":
      content = (
        <VizView
          clusters={clusters}
          heat={heat}
          onRefresh={() => void refresh()}
          refreshClusters={refreshClusters}
        />
      );
      break;
    case "assistant":
      content = <AssistantView status={assistantStatus} />;
      break;
    case "sources":
      content = (
        <SourcesView
          config={config}
          onChange={setConfig}
          onSave={saveSources}
          saving={saving}
        />
      );
      break;
  }

  return (
    <AppShell tab={tab} stats={stats} error={error} onTabChange={setTab}>
      {content}
    </AppShell>
  );
}
