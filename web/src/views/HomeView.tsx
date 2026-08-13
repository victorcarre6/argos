import { Download } from "lucide-react";
import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

import { ArticleCard, Reader } from "../components/articles";
import { Card, Empty, Label, SectionTitle } from "../components/ui";
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
        <SectionTitle>Flux favoris</SectionTitle>
        {recentFavorites.length ? (
          <div className="max-h-[28.5rem] space-y-2 overflow-y-auto pr-2">
            {recentFavorites.map((article) => (
              <ArticleCard
                key={article.id}
                article={article}
                compact
                onRead={setReader}
              />
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
