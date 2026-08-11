import { CheckCircle2 } from "lucide-react";
import { useMemo, useState } from "react";

import { ArticleCard, Reader } from "../components/articles";
import { Button, Card, Empty, SectionTitle } from "../components/ui";
import { formatDate } from "../lib/format";
import type { Article } from "../types";

const LAST_VISIT_KEY = "argos-last-visit";

export function DigestView({ articles }: { articles: Article[] }) {
  const [lastVisit, setLastVisit] = useState(
    () =>
      localStorage.getItem(LAST_VISIT_KEY) ||
      new Date(Date.now() - 86_400_000).toISOString(),
  );
  const [reader, setReader] = useState<Article | null>(null);
  const recent = useMemo(
    () =>
      articles.filter(
        (article) =>
          new Date(article.published_at || article.collected_at) >
          new Date(lastVisit),
      ),
    [articles, lastVisit],
  );

  const markRead = () => {
    const now = new Date().toISOString();
    localStorage.setItem(LAST_VISIT_KEY, now);
    setLastVisit(now);
  };

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <SectionTitle>Depuis votre dernière visite</SectionTitle>
            <p className="text-sm text-muted-foreground">
              {recent.length} article(s) depuis le {formatDate(lastVisit)}.
              Cette préférence est locale à ce navigateur.
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={markRead}
            iconStart={<CheckCircle2 className="size-4" />}
          >
            Marquer comme lu
          </Button>
        </div>
      </Card>
      {recent.length ? (
        <div className="space-y-3">
          {recent.map((article) => (
            <ArticleCard
              key={article.id}
              article={article}
              compact={false}
              onRead={setReader}
            />
          ))}
        </div>
      ) : (
        <Empty>Pas de nouvelle lecture depuis votre dernier passage.</Empty>
      )}
      {reader && <Reader article={reader} close={() => setReader(null)} />}
    </div>
  );
}
