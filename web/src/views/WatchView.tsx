import { Eye, Play, RefreshCw, Search, Star } from "lucide-react";
import { useMemo, useState } from "react";

import { ArticleCard, Reader } from "../components/articles";
import { SourceFilter, TagFilter } from "../components/filters";
import { Button, Card, Empty, SectionTitle } from "../components/ui";
import { matchesQuery } from "../lib/format";
import type { Article, AsyncState, Config } from "../types";

export function WatchView({
  config,
  articles,
  collection,
  onCollect,
  onHide,
  onFavorite,
}: {
  config: Config;
  articles: Article[];
  collection: AsyncState;
  onCollect: () => void;
  onHide: (article: Article) => void;
  onFavorite: (article: Article) => void;
}) {
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const [priority, setPriority] = useState("");
  const [sources, setSources] = useState<string[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [sort, setSort] = useState<"published" | "collected" | "score">(
    "published",
  );
  const [compact, setCompact] = useState(false);
  const [reader, setReader] = useState<Article | null>(null);

  const shown = useMemo(
    () =>
      articles
        .filter(
          (article) =>
            (!category || article.category === category) &&
            (!priority || article.priorité === Number(priority)) &&
            (!search || matchesQuery(article, search)) &&
            (!sources.length || sources.includes(article.source)) &&
            (!tags.length || tags.every((tag) => article.tags.includes(tag))) &&
            (!favoritesOnly || article.candidate === "good"),
        )
        .sort((left, right) => {
          if (sort === "score") return right.score - left.score;
          const field = sort === "published" ? "published_at" : "collected_at";
          return (
            (Date.parse(right[field] || "") || 0) -
            (Date.parse(left[field] || "") || 0)
          );
        }),
    [articles, category, favoritesOnly, priority, search, sort, sources, tags],
  );
  const sourceOptions = useMemo(
    () =>
      [...new Set(articles.map((article) => article.source))].sort((left, right) =>
        left.localeCompare(right, "fr"),
      ),
    [articles],
  );
  const tagOptions = useMemo(
    () => Object.keys(config.tags),
    [config.tags],
  );
  const sourceColors = useMemo(
    () =>
      new Map(
        config.categories.flatMap((item) =>
          item.sources.map((source) => [source.name, item.color] as const),
        ),
      ),
    [config.categories],
  );
  return (
    <div className="space-y-5">
      {collection.running && (
        <Card className="p-4">
          <div className="flex items-center justify-between gap-4 text-sm">
            <span className="font-medium">Pipeline de collecte</span>
            <span className="text-muted-foreground">
              {Math.round(collection.progress.percent)} %
            </span>
          </div>
          <div
            className="mt-2 h-2 overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-label="Progression de la collecte"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={collection.progress.percent}
          >
            <div
              className="h-full rounded-full bg-brand transition-[width] duration-300"
              style={{
                width: `${collection.progress.percent}%`,
              }}
            />
          </div>
          <div className="mt-2 flex items-center justify-between gap-4 text-xs text-muted-foreground">
            <span>
              {collection.progress.label}
            </span>
            <span>
              {collection.progress.stage === "fetch" &&
                collection.progress.total > 0
                ? `${collection.progress.completed}/${collection.progress.total} sources · ${collection.progress.failed} erreur(s)`
                : `${collection.progress.completed}/${collection.progress.total}`}
            </span>
          </div>
        </Card>
      )}

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
              variant="success"
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
        <div className="mt-4 flex items-center gap-2 overflow-x-auto pb-1">
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            className="h-9 shrink-0 rounded-md border border-border bg-background px-3 text-sm"
          >
            <option value="">Toutes les catégories</option>
            {config.categories.map((item) => (
              <option key={item.name}>{item.name}</option>
            ))}
          </select>
          <select
            value={priority}
            onChange={(event) => setPriority(event.target.value)}
            className="h-9 shrink-0 rounded-md border border-border bg-background px-3 text-sm"
          >
            <option value="">Toutes les priorités</option>
            <option value="1">P1</option>
            <option value="2">P2</option>
            <option value="3">P3</option>
          </select>
          <div className="relative min-w-64 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="<str> <et|ou> <str>"
              className="filter-text-field w-full rounded-md border border-border bg-background py-1 pl-9 pr-3 text-sm"
            />
          </div>
          <select
            value={sort}
            onChange={(event) =>
              setSort(event.target.value as "published" | "collected" | "score")
            }
            className="h-9 shrink-0 rounded-md border border-border bg-background px-3 text-sm"
          >
            <option value="published">Plus récente publication</option>
            <option value="collected">Plus récente importation</option>
            <option value="score">Score</option>
          </select>
        </div>
        <div className="mt-3 flex flex-col gap-2 lg:flex-row lg:items-start">
          <SourceFilter
            options={sourceOptions}
            selected={sources}
            onAdd={(source) =>
              setSources((current) =>
                current.includes(source) ? current : [...current, source],
              )
            }
            onRemove={(source) =>
              setSources((current) => current.filter((item) => item !== source))
            }
          />
          <TagFilter
            options={tagOptions}
            selected={tags}
            onAdd={(tag) =>
              setTags((current) =>
                current.includes(tag) ? current : [...current, tag],
              )
            }
            onRemove={(tag) =>
              setTags((current) => current.filter((item) => item !== tag))
            }
          />
          <Button
            variant={favoritesOnly ? "secondary" : "ghost"}
            onClick={() => setFavoritesOnly((current) => !current)}
            aria-pressed={favoritesOnly}
            title="Filtrer les favoris"
            className={favoritesOnly ? "text-amber-500" : "text-muted-foreground"}
            iconStart={
              <Star
                className="size-4"
                fill={favoritesOnly ? "currentColor" : "none"}
              />
            }
          >
            Favoris
          </Button>
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
              onHide={onHide}
              onFavorite={onFavorite}
              sourceColor={sourceColors.get(article.source)}
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
