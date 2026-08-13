import { useMemo, useState } from "react";
import type { ApexOptions } from "apexcharts";
import Chart from "react-apexcharts";

import { ArticleCard, Reader } from "../components/articles";
import { Card, Empty, Label, TabBar } from "../components/ui";
import type { Article, Priority } from "../types";

type FeedbackFilter = "all" | "good" | "bad";
type AcceptanceRow = { name: string; good: number; bad: number; total: number; rate: number };

function acceptanceRows(feedback: Article[], values: (article: Article) => string[]) {
  const counts = new Map<string, { good: number; bad: number }>();
  for (const article of feedback) {
    for (const value of new Set(values(article))) {
      const current = counts.get(value) ?? { good: 0, bad: 0 };
      current[article.candidate === "good" ? "good" : "bad"] += 1;
      counts.set(value, current);
    }
  }
  return [...counts].map(([name, count]) => ({
    name,
    ...count,
    total: count.good + count.bad,
    rate: Math.round((count.good / (count.good + count.bad)) * 100),
  })).sort((left, right) => right.total - left.total || right.rate - left.rate);
}

function AcceptanceChart({ title, rows }: { title: string; rows: AcceptanceRow[] }) {
  return (
    <Card className="p-5">
      <Label>{title}</Label>
      {rows.length ? <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-2">
        {rows.map((row) => (
          <div key={row.name} className="grid grid-cols-[9rem_1fr_3rem] items-center gap-3 text-sm">
            <span className="truncate" title={row.name}>{row.name}</span>
            <div className="flex h-2 overflow-hidden rounded-full bg-error/25" title={`${row.good} favoris · ${row.bad} masqués`}>
              <div className="h-full bg-success" style={{ width: `${row.rate}%` }} />
            </div>
            <span className="text-right font-medium">{row.rate}%</span>
          </div>
        ))}
      </div> : <div className="mt-3"><Empty>Aucune donnée.</Empty></div>}
    </Card>
  );
}

function ScoreDistribution({ feedback }: { feedback: Article[] }) {
  const buckets = useMemo(() => Array.from({ length: 10 }, (_, index) => {
    const min = index * 10;
    const items = feedback.filter((article) => article.score >= min && article.score < min + 10 + (index === 9 ? 1 : 0));
    return { label: `${min}–${min + 9}`, good: items.filter((item) => item.candidate === "good").length, bad: items.filter((item) => item.candidate === "bad").length };
  }), [feedback]);
  const maximum = Math.max(1, ...buckets.flatMap((bucket) => [bucket.good, bucket.bad]));
  return (
    <Card className="p-5">
      <Label>Distribution des scores</Label>
      <div className="mt-4 flex h-52 items-end gap-2" aria-label="Histogramme des scores favoris et masqués">
        {buckets.map((bucket) => <div key={bucket.label} className="flex min-w-0 flex-1 flex-col items-center gap-1">
          <div className="flex h-40 w-full items-end justify-center gap-1">
            <div className="w-2/5 rounded-t bg-success" title={`${bucket.good} favoris`} style={{ height: `${(bucket.good / maximum) * 100}%` }} />
            <div className="w-2/5 rounded-t bg-error/70" title={`${bucket.bad} masqués`} style={{ height: `${(bucket.bad / maximum) * 100}%` }} />
          </div>
          <span className="text-[10px] text-muted-foreground">{bucket.label}</span>
        </div>)}
      </div>
      <div className="mt-2 flex justify-center gap-4 text-xs"><span className="text-success">■ Favoris</span><span className="text-error">■ Masqués</span></div>
    </Card>
  );
}

function FeedbackHeatmap({ feedback }: { feedback: Article[] }) {
  const categories = useMemo(
    () => [...new Set(feedback.map((article) => article.category))].sort((left, right) => left.localeCompare(right, "fr")),
    [feedback],
  );
  const tags = useMemo(
    () => [...new Set(feedback.flatMap((article) => article.tags))].sort((left, right) => left.localeCompare(right, "fr")),
    [feedback],
  );
  const cells = useMemo(() => {
    const values = new Map<string, { good: number; bad: number }>();
    for (const article of feedback) {
      for (const tag of new Set(article.tags)) {
        const key = `${article.category}\u0000${tag}`;
        const current = values.get(key) ?? { good: 0, bad: 0 };
        current[article.candidate === "good" ? "good" : "bad"] += 1;
        values.set(key, current);
      }
    }
    return values;
  }, [feedback]);
  const series = useMemo(() => categories.map((category) => ({
    name: category,
    data: tags.map((tag) => {
      const value = cells.get(`${category}\u0000${tag}`);
      const total = value ? value.good + value.bad : 0;
      return { x: tag, y: value && total ? Math.round((value.good / total) * 100) : -1 };
    }),
  })), [categories, cells, tags]);
  const options = useMemo<ApexOptions>(() => ({
    chart: {
      type: "heatmap",
      background: "transparent",
      foreColor: "#a9b3c1",
      toolbar: { show: false },
      animations: { enabled: false },
    },
    theme: { mode: "dark" },
    plotOptions: {
      heatmap: {
        radius: 3,
        enableShades: false,
        colorScale: {
          ranges: [
            { from: -1, to: -1, color: "#374151", name: "Aucune décision" },
            { from: 0, to: 19, color: "#dc2626", name: "0–19 %" },
            { from: 20, to: 39, color: "#f97316", name: "20–39 %" },
            { from: 40, to: 59, color: "#eab308", name: "40–59 %" },
            { from: 60, to: 79, color: "#84cc16", name: "60–79 %" },
            { from: 80, to: 100, color: "#16a34a", name: "80–100 %" },
          ],
        },
      },
    },
    dataLabels: {
      enabled: true,
      style: { colors: ["#f8fafc"], fontSize: "10px", fontWeight: 600 },
      formatter: (value) => Number(value) < 0 ? "—" : `${value}%`,
    },
    grid: { borderColor: "#263244", padding: { left: 8, right: 8 } },
    legend: {
      show: false,
    },
    stroke: { width: 2, colors: ["#111827"] },
    xaxis: {
      type: "category",
      labels: { rotate: -45, rotateAlways: true, trim: false, style: { colors: "#a9b3c1", fontSize: "11px" } },
      axisBorder: { color: "#334155" },
      axisTicks: { color: "#334155" },
    },
    yaxis: { labels: { maxWidth: 190, style: { colors: "#d1d5db", fontSize: "12px" } } },
    tooltip: {
      theme: "dark",
      custom: ({ seriesIndex, dataPointIndex }) => {
        const category = categories[seriesIndex];
        const tag = tags[dataPointIndex];
        const value = cells.get(`${category}\u0000${tag}`);
        if (!value) return `<div class="argos-chart-tooltip"><strong>${category}</strong><br>${tag}<br>Aucune décision</div>`;
        const total = value.good + value.bad;
        const rate = Math.round((value.good / total) * 100);
        return `<div class="argos-chart-tooltip"><strong>${category}</strong><br>${tag}<br>${rate} % d’acceptation<br>${value.good} favoris · ${value.bad} masqués · ${total} décisions</div>`;
      },
    },
  }), [categories, cells, tags]);

  return (
    <Card className="p-5">
      <Label>Heatmap catégories × tags</Label>
      {categories.length && tags.length ? (
        <div className="mt-3 overflow-x-auto">
          <div className="flex min-w-[900px] items-center gap-5">
            <div className="min-w-0 flex-1">
              <Chart options={options} series={series} type="heatmap" height={Math.max(430, categories.length * 54 + 190)} />
            </div>
            <div className="flex h-64 shrink-0 items-stretch gap-2" aria-label="Échelle continue du taux d’acceptation, de 0 à 100 pour cent">
              <div className="flex flex-col justify-between text-xs text-muted-foreground"><span>100 %</span><span>0 %</span></div>
              <div
                className="w-4 rounded-full ring-1 ring-white/10"
                style={{ background: "linear-gradient(to top, #dc2626 0%, #f97316 25%, #eab308 50%, #84cc16 75%, #16a34a 100%)" }}
              />
            </div>
          </div>
        </div>
      ) : <div className="mt-3"><Empty>Aucune donnée pour construire la heatmap.</Empty></div>}
    </Card>
  );
}

export function DataAnalysisView({ feedback, currentTotal }: { feedback: Article[]; currentTotal: number }) {
  const [filter, setFilter] = useState<FeedbackFilter>("all");
  const [reader, setReader] = useState<Article | null>(null);
  const good = feedback.filter((article) => article.candidate === "good");
  const bad = feedback.filter((article) => article.candidate === "bad");
  const shown = filter === "good" ? good : filter === "bad" ? bad : feedback;
  const reviewedRate = currentTotal ? Math.round((feedback.length / currentTotal) * 100) : 0;
  const tagRows = useMemo(() => acceptanceRows(feedback, (article) => article.tags), [feedback]);
  const sourceRows = useMemo(() => acceptanceRows(feedback, (article) => [article.source]), [feedback]);
  const priorityRows = useMemo(() => acceptanceRows(feedback, (article) => [`P${article.priorité as Priority}`]), [feedback]);

  return <div className="space-y-5">
    <section className="grid gap-3 sm:grid-cols-3">
      <Card className="p-4"><Label>Favoris</Label><div className="text-2xl font-semibold text-success">{good.length}</div><div className="text-xs text-muted-foreground">signaux conservés</div></Card>
      <Card className="p-4"><Label>Masqués</Label><div className="text-2xl font-semibold text-error">{bad.length}</div><div className="text-xs text-muted-foreground">signaux ignorés</div></Card>
      <Card className="p-4"><Label>Part évaluée</Label><div className="text-2xl font-semibold">{reviewedRate}%</div><div className="text-xs text-muted-foreground">{feedback.length} décisions / {currentTotal} signaux actuels</div></Card>
    </section>

    <section className="grid gap-5 xl:grid-cols-2">
      <AcceptanceChart title="Taux d’acceptation par tag" rows={tagRows} />
      <AcceptanceChart title="Taux d’acceptation par source" rows={sourceRows} />
      <ScoreDistribution feedback={feedback} />
      <AcceptanceChart title="Performance par priorité" rows={priorityRows} />
    </section>

    <FeedbackHeatmap feedback={feedback} />

    <div className="flex items-center justify-between gap-3">
      <TabBar items={[{ value: "all", label: "Tous" }, { value: "good", label: "Favoris" }, { value: "bad", label: "Masqués" }]} value={filter} onChange={setFilter} />
      <span className="text-sm text-muted-foreground">{shown.length} signaux</span>
    </div>
    {shown.length ? <div className="space-y-2">{shown.map((article) => <ArticleCard key={article.id} article={article} compact onRead={setReader} />)}</div> : <Empty>Aucun signal dans cette sélection.</Empty>}
    {reader && <Reader article={reader} close={() => setReader(null)} />}
  </div>;
}
