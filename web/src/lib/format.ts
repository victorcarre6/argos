import type { Article } from "../types";

export function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatBytes(bytes: number): string {
  const digits = bytes > 10_000_000 ? 1 : 2;
  return `${(bytes / 1024 / 1024).toFixed(digits)} Mo`;
}

export function formatElapsed(value: string | null): string {
  if (!value) return "—";
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return "—";
  const totalMinutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60_000));
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

export function matchesQuery(article: Article, query: string): boolean {
  const searchable =
    `${article.title} ${article.summary} ${article.tags.join(" ")}`.toLowerCase();
  const alternatives = query
    .toLowerCase()
    .split(/\s+(?:ou|or)\s+/)
    .filter(Boolean);
  return alternatives.some((group) =>
    group
      .split(/\s+(?:et|and)\s+/)
      .filter(Boolean)
      .every((term) => searchable.includes(term.trim())),
  );
}
