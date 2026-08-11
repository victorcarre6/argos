import { RefreshCw, Save, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { Button, Card, Empty, SectionTitle } from "../components/ui";
import { api, jsonRequest } from "../lib/api";
import type { ClusterResponse, HeatCell, SemanticPoint } from "../types";

function SemanticMap() {
  const [points, setPoints] = useState<SemanticPoint[]>([]);
  const [message, setMessage] = useState("");
  const [selected, setSelected] = useState<SemanticPoint | null>(null);

  const load = () => {
    void api<{ points: SemanticPoint[]; message?: string }>("/viz/semantic-map")
      .then((data) => {
        setPoints(data.points);
        setMessage(data.message ?? "");
      })
      .catch((error) =>
        setMessage(
          error instanceof Error ? error.message : "Carte indisponible",
        ),
      );
  };
  useEffect(load, []);

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div>
          <SectionTitle>Nuage sémantique</SectionTitle>
          <p className="text-sm text-muted-foreground">
            Chaque point est un article ; les proximités viennent des embeddings
            locaux.
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={load}
          iconStart={<RefreshCw className="size-4" />}
        >
          Actualiser
        </Button>
      </div>
      <div className="grid min-h-[460px] md:grid-cols-[1fr_280px]">
        <div
          className="relative overflow-hidden bg-slate-950"
          style={{
            backgroundImage:
              "radial-gradient(circle at 1px 1px, rgba(255,255,255,.12) 1px, transparent 0)",
            backgroundSize: "24px 24px",
          }}
        >
          {points.map((point) => (
            <button
              key={point.id}
              title={point.title}
              onClick={() => setSelected(point)}
              className="absolute size-3 rounded-full border border-white/70 shadow transition hover:z-10 hover:scale-150"
              style={{
                left: `${4 + point.x * 92}%`,
                top: `${5 + point.y * 88}%`,
                backgroundColor: point.color,
              }}
            />
          ))}
          {!points.length && (
            <div className="absolute inset-0 grid place-items-center p-8 text-center text-sm text-slate-300">
              {message || "Chargement des embeddings…"}
            </div>
          )}
          <div className="absolute bottom-3 left-4 text-xs text-slate-400">
            {points.length} articles projetés · couleur = thématique
          </div>
        </div>
        <div className="border-t border-border bg-background p-4 md:border-l md:border-t-0">
          {selected ? (
            <>
              <div className="text-xs text-muted-foreground">
                {selected.category}
                {selected.cluster_name ? ` · ${selected.cluster_name}` : ""}
              </div>
              <a
                className="mt-2 block text-sm font-semibold hover:underline"
                href={selected.url}
                target="_blank"
                rel="noreferrer"
              >
                {selected.title}
              </a>
              <p className="mt-3 line-clamp-6 text-sm text-muted-foreground">
                {selected.summary}
              </p>
              <div className="mt-4 text-xs text-muted-foreground">
                {selected.source} · score {selected.score}
              </div>
            </>
          ) : (
            <div className="text-sm text-muted-foreground">
              Sélectionnez un point pour lire son contexte et ouvrir la source.
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function Heatmap({ initialCells }: { initialCells: HeatCell[] }) {
  const [mode, setMode] = useState("source-category");
  const [cells, setCells] = useState(initialCells);
  useEffect(() => {
    void api<{ cells: HeatCell[] }>(`/viz/heatmap?mode=${mode}`).then((data) =>
      setCells(data.cells),
    );
  }, [mode]);
  const max = Math.max(1, ...cells.map((item) => item.value));
  const xs = [...new Set(cells.map((item) => item.x))];
  const ys = [...new Set(cells.map((item) => item.y))];

  return (
    <Card className="p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <SectionTitle>Carte de chaleur</SectionTitle>
          <p className="text-sm text-muted-foreground">
            Intensité = nombre d'articles uniques.
          </p>
        </div>
        <select
          value={mode}
          onChange={(event) => setMode(event.target.value)}
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
        >
          <option value="source-category">Source × thématique</option>
          <option value="day">Activité par jour</option>
        </select>
      </div>
      <div className="mt-4 overflow-x-auto">
        <div
          className="grid min-w-[680px] gap-1"
          style={{
            gridTemplateColumns: `180px repeat(${xs.length}, minmax(52px, 1fr))`,
          }}
        >
          <div />
          {xs.map((x) => (
            <div
              key={x}
              className="truncate px-1 text-center text-[10px] text-muted-foreground"
              title={x}
            >
              {x}
            </div>
          ))}
          {ys.map((y) => [
            <div
              key={`${y}-label`}
              className="truncate pr-2 text-xs text-muted-foreground"
              title={y}
            >
              {y}
            </div>,
            ...xs.map((x) => {
              const cell = cells.find((item) => item.x === x && item.y === y);
              return (
                <div
                  key={`${x}-${y}`}
                  title={`${x} · ${y} : ${cell?.value ?? 0}`}
                  className="flex h-9 items-center justify-center rounded bg-brand text-xs text-brand-foreground"
                  style={{
                    opacity: cell ? Math.max(0.15, cell.value / max) : 0.04,
                  }}
                >
                  {cell?.value ?? ""}
                </div>
              );
            }),
          ])}
        </div>
      </div>
    </Card>
  );
}

export function VizView({
  clusters,
  heat,
  onRefresh,
  refreshClusters,
}: {
  clusters: ClusterResponse | null;
  heat: HeatCell[];
  onRefresh: () => void;
  refreshClusters: () => void;
}) {
  const [names, setNames] = useState<Record<string, string>>({});
  const saveName = async (id: string, fallback: string) => {
    await api(
      `/clusters/${id}`,
      jsonRequest("PUT", { name: names[id] || fallback }),
    );
    onRefresh();
  };

  return (
    <div className="space-y-4">
      <SemanticMap />
      <Heatmap initialCells={heat} />
      <Card className="p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <SectionTitle>Clusters sémantiques</SectionTitle>
            <p className="text-sm text-muted-foreground">
              Embeddings batchés avec nomic-embed-text-v2-moe sur Nyx. Les noms
              sont éditables.
            </p>
          </div>
          <Button
            onClick={refreshClusters}
            disabled={clusters?.state.running}
            iconStart={<Sparkles className="size-4" />}
          >
            {clusters?.state.running
              ? "Clustering…"
              : "Actualiser les clusters"}
          </Button>
        </div>
        {clusters?.state.error && (
          <p className="mt-3 text-sm text-error">{clusters.state.error}</p>
        )}
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {clusters?.clusters.map((cluster) => (
            <div
              key={cluster.id}
              className="rounded-lg border border-border p-3"
            >
              <div className="flex gap-2">
                <input
                  value={names[cluster.id] ?? cluster.name}
                  onChange={(event) =>
                    setNames({ ...names, [cluster.id]: event.target.value })
                  }
                  className="h-8 min-w-0 flex-1 rounded border border-border bg-background px-2 text-sm font-medium"
                />
                <Button
                  variant="ghost"
                  onClick={() => saveName(cluster.id, cluster.name)}
                >
                  <Save className="size-4" />
                </Button>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                {cluster.size} articles · suggestion : {cluster.auto_name}
              </p>
              <ul className="mt-2 list-disc pl-4 text-xs text-secondary-foreground">
                {cluster.titles.map((title) => (
                  <li key={title} className="truncate">
                    {title}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        {!clusters?.clusters.length && (
          <Empty>
            Lancez l'actualisation pour créer les premiers clusters.
          </Empty>
        )}
      </Card>
    </div>
  );
}
