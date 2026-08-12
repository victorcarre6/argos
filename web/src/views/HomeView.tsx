import { Download, ExternalLink } from "lucide-react";
import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

import { Reader } from "../components/articles";
import { Card, Empty, Label, Pill, SectionTitle } from "../components/ui";
import { formatDate } from "../lib/format";
import type { Article, Config, Stats, SummaryDocument } from "../types";

export function HomeView({
  config,
  stats,
  summary,
  favorites,
}: {
  config: Config;
  stats: Stats;
  summary: SummaryDocument;
  favorites: Article[];
}) {
  const [reader, setReader] = useState<Article | null>(null);
  const recentFavorites = useMemo(
    () =>
      [...favorites]
        .sort(
          (left, right) =>
            Date.parse(right.collected_at) - Date.parse(left.collected_at),
        )
        .slice(0, 30),
    [favorites],
  );

  return (
    <div className="space-y-5">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="p-4">
          <Label>Total signaux</Label>
          <div className="text-2xl font-semibold">{stats.total}</div>
          <div className="text-xs text-muted-foreground">
            actuellement indexés
          </div>
        </Card>
        <Card className="p-4">
          <Label>Nouveaux signaux</Label>
          <div className="text-2xl font-semibold">{stats.new_signals ?? "—"}</div>
          <div className="text-xs text-muted-foreground">
            dernière collecte
          </div>
        </Card>
        <Card className="p-4">
          <Label>Signaux P1</Label>
          <div className="text-2xl font-semibold">{stats.priority_one_recent}</div>
          <div className="text-xs text-muted-foreground">
            sur {config.collection?.max_age_days ?? "—"} jours
          </div>
        </Card>
        <Card className="p-4">
          <Label>Dernière collecte</Label>
          <div className="pt-1 text-sm font-medium">
            {formatDate(stats.last_collection)}
          </div>
          <div className="text-xs text-muted-foreground">
            {stats.last_collection_successful_sources ?? "—"} OK ·{" "}
            {stats.last_collection_failed_sources ?? "—"} erreurs
          </div>
        </Card>
      </section>

      <Card className="p-6">
        <div>
          <SectionTitle>Flux favoris</SectionTitle>
          <p className="text-sm text-muted-foreground">
            30 derniers signaux étoilés, triés par date de récupération.
          </p>
        </div>
        {recentFavorites.length ? (
          <div className="mt-4 max-h-[28.5rem] space-y-3 overflow-y-auto pr-2">
            {recentFavorites.map((article) => (
              <article
                key={article.id}
                className="flex min-h-36 flex-col justify-between rounded-lg border border-border p-4"
              >
                <div>
                  <div className="mb-2 flex flex-wrap gap-1.5">
                    <Pill tone="brand">{article.category}</Pill>
                    {article.tags.map((tag) => (
                      <Pill key={tag} tone="neutral">
                        {tag}
                      </Pill>
                    ))}
                  </div>
                  <button
                    type="button"
                    className="text-left font-semibold hover:text-brand"
                    onClick={() => setReader(article)}
                  >
                    {article.title}
                  </button>
                </div>
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>
                    {article.source} · récupéré le {formatDate(article.collected_at)}
                  </span>
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 hover:text-brand"
                  >
                    Source <ExternalLink className="size-3" />
                  </a>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="mt-4">
            <Empty>Aucun signal étoilé.</Empty>
          </div>
        )}
      </Card>

      <Card className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-2 [&>h3]:mb-0">
            <SectionTitle>Dernier rapport</SectionTitle>
            {summary.content.trim() && (
              <a
                href="/api/summary/download"
                download
                title="Télécharger le dernier rapport"
                aria-label="Télécharger le dernier rapport"
                className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <Download className="size-4" />
              </a>
            )}
          </div>
          {summary.updated_at && (
            <span className="text-xs text-muted-foreground">
              Mis à jour le {formatDate(summary.updated_at)}
            </span>
          )}
        </div>
        {summary.content.trim() ? (
          <div className="markdown mt-5 text-sm leading-7">
            <ReactMarkdown>{summary.content}</ReactMarkdown>
          </div>
        ) : (
          <div className="mt-5">
            <Empty>Aucun rapport disponible.</Empty>
          </div>
        )}
      </Card>
      {reader && <Reader article={reader} close={() => setReader(null)} />}
    </div>
  );
}
