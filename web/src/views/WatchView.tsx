import { Eye, Play, RefreshCw, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { ArticleCard, Reader } from "../components/articles";
import { Button, Card, Empty, Label, SectionTitle } from "../components/ui";
import { formatDate, matchesQuery } from "../lib/format";
import type { Article, AsyncState, Config, Stats } from "../types";

export function WatchView({
  config,
  stats,
  articles,
  collection,
  onCollect,
}: {
  config: Config;
  stats: Stats;
  articles: Article[];
  collection: AsyncState;
  onCollect: () => void;
}) {
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const [compact, setCompact] = useState(false);
  const [reader, setReader] = useState<Article | null>(null);

  const shown = useMemo(
    () =>
      articles.filter(
        (article) =>
          (!category || article.category === category) &&
          (!search || matchesQuery(article, search)),
      ),
    [articles, category, search],
  );
  const configuredSources = config.categories
    .flatMap((item) => item.sources)
    .filter((item) => item.enabled !== false).length;

  return (
    <div className="space-y-5">
      <section className="grid gap-3 sm:grid-cols-3">
        <Card className="p-4">
          <Label>Articles indexés</Label>
          <div className="text-2xl font-semibold">{stats.total}</div>
        </Card>
        <Card className="p-4">
          <Label>Sources actives</Label>
          <div className="text-2xl font-semibold">
            {stats.sources || configuredSources}
          </div>
        </Card>
        <Card className="p-4">
          <Label>Dernière collecte</Label>
          <div className="pt-1 text-sm font-medium">
            {formatDate(stats.last_collection)}
          </div>
        </Card>
      </section>

      {collection.result && (
        <div className="rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success">
          Collecte terminée :{" "}
          {collection.result.new ?? collection.result.articles} nouveaux
          articles, {collection.result.duplicates ?? 0} regroupements de
          syndication.
        </div>
      )}
      {collection.error && (
        <div className="rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
          Erreur de collecte : {collection.error}
        </div>
      )}

      <Card className="p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <SectionTitle>Derniers signaux</SectionTitle>
            <p className="text-sm text-muted-foreground">
              Recherche : séparer les alternatives par « ou », les termes requis
              par « et ».
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={() => setCompact((value) => !value)}
              iconStart={<Eye className="size-4" />}
            >
              {compact ? "Confort" : "Compact"}
            </Button>
            <Button
              onClick={onCollect}
              disabled={collection.running}
              iconStart={
                collection.running ? (
                  <RefreshCw className="size-4 animate-spin" />
                ) : (
                  <Play className="size-4" />
                )
              }
            >
              {collection.running ? "Collecte…" : "Collecter"}
            </Button>
          </div>
        </div>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          >
            <option value="">Toutes les catégories</option>
            {config.categories.map((item) => (
              <option key={item.name}>{item.name}</option>
            ))}
          </select>
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Ex. agent et MCP, ou RAG"
              className="h-9 w-full rounded-md border border-border bg-background py-1 pl-9 pr-3 text-sm"
            />
          </div>
        </div>
      </Card>

      {shown.length ? (
        <div className="space-y-3">
          {shown.map((article) => (
            <ArticleCard
              key={article.id}
              article={article}
              compact={compact}
              onRead={setReader}
            />
          ))}
        </div>
      ) : (
        <Empty>
          Aucun article pour ce filtre. Lancez une collecte ou ajustez les
          sources.
        </Empty>
      )}
      {reader && <Reader article={reader} close={() => setReader(null)} />}
    </div>
  );
}
