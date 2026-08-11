import { ExternalLink, Star, X } from "lucide-react";

import { formatDate } from "../lib/format";
import type { Article, Priority } from "../types";
import { Button, Card, Pill } from "./ui";

const PRIORITY_BORDER: Record<Priority, string> = {
  1: "border-red-400/70",
  2: "border-emerald-400/60",
  3: "",
};

const PRIORITY_BADGE: Record<Priority, string> = {
  1: "bg-red-500/15 text-red-600",
  2: "bg-emerald-500/15 text-emerald-600",
  3: "bg-muted text-muted-foreground",
};

export function ArticleCard({
  article,
  compact,
  onRead,
  onHide,
  onFavorite,
  sourceColor,
}: {
  article: Article;
  compact: boolean;
  onRead: (article: Article) => void;
  onHide?: (article: Article) => void;
  onFavorite?: (article: Article) => void;
  sourceColor?: string;
}) {
  return (
    <Card
      className={`${compact ? "p-3" : "p-4"} relative ${PRIORITY_BORDER[article.priorité]}`}
    >
      {onHide && (
        <button
          type="button"
          className="absolute right-2 top-2 rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          onClick={() => onHide(article)}
          aria-label={`Retirer ${article.title} de la vue`}
          title="Retirer de la vue"
        >
          <X className="size-4" />
        </button>
      )}
      {onFavorite && (
        <button
          type="button"
          className={`absolute right-9 top-2 rounded p-1 transition-colors hover:bg-muted ${
            article.candidate === "good"
              ? "text-amber-500"
              : "text-muted-foreground hover:text-amber-500"
          }`}
          onClick={() => onFavorite(article)}
          aria-label={`Marquer ${article.title} comme bon candidat`}
          title="Bon candidat"
        >
          <Star
            className="size-4"
            fill={article.candidate === "good" ? "currentColor" : "none"}
          />
        </button>
      )}
      <span className="absolute right-2 top-10 font-mono text-sm font-normal text-brand">
        {article.score}
      </span>
      <div className="flex gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap gap-2">
            <Pill tone={article.score >= 55 ? "brand" : "neutral"}>
              {article.category}
            </Pill>
            {article.keys.map((key) => (
              <Pill key={key} tone="success">
                {key}
              </Pill>
            ))}
            {article.tags.map((tag) => (
              <Pill key={tag} tone="neutral">
                {tag}
              </Pill>
            ))}
          </div>
          <button
            className="text-left font-semibold hover:text-brand"
            onClick={() => onRead(article)}
          >
            {article.title}
          </button>
          {!compact && (
            <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
              {article.summary || "Aucun résumé fourni par le flux."}
            </p>
          )}
          <div className="mt-3 flex items-center gap-2 pr-9 text-xs text-secondary-foreground">
            <span
              className="rounded-full border px-2 py-0.5 font-medium"
              style={
                sourceColor
                  ? {
                      backgroundColor: `${sourceColor}1f`,
                      borderColor: `${sourceColor}66`,
                      color: sourceColor,
                    }
                  : undefined
              }
            >
              {article.source}
            </span>
            <span>
              {article.published_at
                ? `Publié le ${formatDate(article.published_at)}`
                : "Date de publication non fournie"}
            </span>
            <a
              className="inline-flex items-center gap-1 hover:text-brand"
              href={article.url}
              target="_blank"
              rel="noreferrer"
            >
              Source <ExternalLink className="size-3" />
            </a>
          </div>
        </div>
      </div>
      <span
        className={`absolute bottom-3 right-3 rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold ${PRIORITY_BADGE[article.priorité]}`}
      >
        P{article.priorité}
      </span>
    </Card>
  );
}

export function Reader({
  article,
  close,
}: {
  article: Article;
  close: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-40 bg-foreground/20 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
    >
      <div className="mx-auto mt-8 max-w-3xl rounded-xl border border-border bg-background p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <Pill tone="brand">{article.category}</Pill>
            <h2 className="mt-3 text-xl font-semibold">{article.title}</h2>
          </div>
          <Button variant="ghost" onClick={close} aria-label="Fermer">
            <X className="size-4" />
          </Button>
        </div>
        <p className="mt-5 whitespace-pre-line text-sm leading-6 text-muted-foreground">
          {article.summary || "Le flux ne fournit pas de résumé."}
        </p>
        <div className="mt-5 flex items-center justify-between border-t border-border pt-4 text-sm">
          <span>
            {article.source} ·{" "}
            {article.published_at
              ? `publié le ${formatDate(article.published_at)}`
              : "date de publication non fournie"}
          </span>
          <a
            className="inline-flex items-center gap-1 text-brand"
            href={article.url}
            target="_blank"
            rel="noreferrer"
          >
            Ouvrir l'article <ExternalLink className="size-4" />
          </a>
        </div>
      </div>
    </div>
  );
}
