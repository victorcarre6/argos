import {
  Activity,
  Bot,
  FileCog,
  House,
  Rss,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { TabBar } from "./components/ui";
import { api, jsonRequest } from "./lib/api";
import type {
  AppHealth,
  AsyncState,
  Config,
  CollectionRun,
  SourceHealth,
  Stats,
  SummaryDocument,
  Tab,
  Article,
} from "./types";
import { AssistantView } from "./views/AssistantView";
import { ConfigView } from "./views/ConfigView";
import { HealthView } from "./views/HealthView";
import { HomeView } from "./views/HomeView";
import { WatchView } from "./views/WatchView";

const EMPTY_CONFIG: Config = { tags: {}, categories: [] };
const EMPTY_ASYNC_STATE: AsyncState = {
  running: false,
  started_at: null,
  finished_at: null,
  result: null,
  error: null,
  progress: {
    stage: "idle",
    label: "En attente",
    percent: 0,
    completed: 0,
    total: 0,
    failed: 0,
  },
};

const NAVIGATION: Array<{ value: Tab; label: string; icon: ReactNode }> = [
  { value: "home", label: "Homepage", icon: <House className="size-4" /> },
  { value: "watch", label: "Flux", icon: <Rss className="size-4" /> },
  { value: "assistant", label: "Assistants", icon: <Bot className="size-4" /> },
  { value: "health", label: "Santé", icon: <Activity className="size-4" /> },
  { value: "config", label: "Config", icon: <FileCog className="size-4" /> },
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
  appHealth,
  error,
  onTabChange,
  children,
}: {
  tab: Tab;
  appHealth: AppHealth | null;
  error: string;
  onTabChange: (tab: Tab) => void;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <div className="flex size-8 items-center justify-center rounded-lg bg-success text-white">
              <Rss className="size-4" />
            </div>
            <div>
              <h1 className="font-semibold">Argos</h1>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                RSS Monitor
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Activity
              className={`size-4 ${appHealth ? "text-success" : "text-muted-foreground"}`}
            />
            {appHealth ? "Opérationnel" : "État indisponible"}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-6">
        <TabBar
          items={NAVIGATION}
          value={tab}
          onChange={onTabChange}
          className="mb-5"
        />
        {error && (
          <div className="mb-4 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
            {error}
          </div>
        )}
        <ErrorBoundary key={tab}>{children}</ErrorBoundary>
      </main>
    </div>
  );
}

export function App() {
  const [tab, setTab] = useState<Tab>("home");
  const [config, setConfig] = useState<Config>(EMPTY_CONFIG);
  const [articles, setArticles] = useState<Article[]>([]);
  const [favoriteArticles, setFavoriteArticles] = useState<Article[]>([]);
  const [stats, setStats] = useState<Stats>({
    total: 0,
    sources: 0,
    collected_sources: 0,
    new_signals: null,
    priority_one_recent: 0,
    last_collection: null,
    last_collection_sources: null,
    last_collection_failed_sources: null,
    last_collection_successful_sources: null,
  });
  const [collection, setCollection] = useState<AsyncState>(EMPTY_ASYNC_STATE);
  const [appHealth, setAppHealth] = useState<AppHealth | null>(null);
  const [sourceHealth, setSourceHealth] = useState<SourceHealth[]>([]);
  const [collectionRuns, setCollectionRuns] = useState<CollectionRun[]>([]);
  const [summary, setSummary] = useState<SummaryDocument>({
    content: "",
    updated_at: null,
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const refreshInProgress = useRef(false);

  const refresh = useCallback(async (includeConfig = true) => {
    if (refreshInProgress.current) return;
    refreshInProgress.current = true;

    const requests = [
      loadResource<{ articles: Article[] }>("/articles?limit=400", (value) =>
        setArticles(value.articles),
      ),
      loadResource<{ articles: Article[] }>("/articles/favorites?limit=30", (value) =>
        setFavoriteArticles(value.articles),
      ),
      loadResource<Stats>("/stats", setStats),
      loadResource<AsyncState>("/refresh", setCollection),
      loadResource<AppHealth>("/health/app", setAppHealth),
      loadResource<{ sources: SourceHealth[] }>("/health/sources", (value) =>
        setSourceHealth(value.sources),
      ),
      loadResource<{ runs: CollectionRun[] }>("/collection/runs", (value) =>
        setCollectionRuns(value.runs),
      ),
      loadResource<SummaryDocument>("/summary", setSummary),
    ];
    if (includeConfig) {
      requests.push(loadResource<Config>("/sources", setConfig));
    }
    const failures = await Promise.all(requests);

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
    const timer = window.setInterval(() => void refresh(false), 10_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    if (!collection.running) return;
    const timer = window.setInterval(() => {
      void loadResource<AsyncState>("/refresh", setCollection);
    }, 1_000);
    return () => window.clearInterval(timer);
  }, [collection.running]);

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

  const hideArticle = async (article: Article) => {
    try {
      await api(`/articles/${article.id}/view`,
        jsonRequest("PATCH", { view: false }),
      );
      setArticles((current) => current.filter((item) => item.id !== article.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Masquage impossible");
    }
  };

  const favoriteArticle = async (article: Article) => {
    try {
      await api(
        `/articles/${article.id}/feedback`,
        jsonRequest("PATCH", { candidate: "good" }),
      );
      setArticles((current) =>
        current.map((item) =>
          item.id === article.id ? { ...item, candidate: "good" } : item,
        ),
      );
      await refresh(false);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Favori impossible",
      );
    }
  };

  let content: ReactNode;
  switch (tab) {
    case "home":
      content = (
        <HomeView
          config={config}
          stats={stats}
          summary={summary}
          favorites={favoriteArticles}
        />
      );
      break;
    case "watch":
      content = (
        <WatchView
          config={config}
          articles={articles}
          collection={collection}
          onCollect={startCollection}
          onHide={(article) => void hideArticle(article)}
          onFavorite={(article) => void favoriteArticle(article)}
        />
      );
      break;
    case "health":
      content = (
        <HealthView
          appHealth={appHealth}
          sources={sourceHealth}
          runs={collectionRuns}
          config={config}
          refresh={() => void refresh()}
        />
      );
      break;
    case "assistant":
      content = (
        <AssistantView
          telegram={appHealth?.telegram ?? null}
          automation={appHealth?.automation ?? null}
          runs={collectionRuns}
        />
      );
      break;
    case "config":
      content = (
        <ConfigView
          config={config}
          onSourcesChange={setConfig}
          onSourcesSave={saveSources}
          savingSources={saving}
          onChanged={() => void refresh()}
        />
      );
      break;
  }

  return (
    <AppShell
      tab={tab}
      appHealth={appHealth}
      error={error}
      onTabChange={setTab}
    >
      {content}
    </AppShell>
  );
}
