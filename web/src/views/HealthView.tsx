import { CheckCircle2, CircleAlert, TestTube2 } from "lucide-react";
import { useState } from "react";

import { Button, Card, Empty, Label, SectionTitle } from "../components/ui";
import { api, jsonRequest } from "../lib/api";
import { formatBytes, formatDate, formatElapsed } from "../lib/format";
import type { AppHealth, CollectionRun, Config, SourceHealth } from "../types";

export function HealthView({
  appHealth,
  sources,
  runs,
  config,
  refresh,
}: {
  appHealth: AppHealth | null;
  sources: SourceHealth[];
  runs: CollectionRun[];
  config: Config;
  refresh: () => void;
}) {
  const [testing, setTesting] = useState("");
  const [testError, setTestError] = useState("");
  const sourceMap = config.categories.flatMap((category) =>
    category.sources.map((source) => ({ category, source })),
  );
  const runStatus = {
    running: "En cours",
    completed: "Terminée",
    completed_with_errors: "Terminée avec erreurs",
    failed: "Échec",
  } as const;
  const lastFinishedAt = runs.find((run) => run.finished_at)?.finished_at ?? null;

  const testSource = async (sourceName: string) => {
    const found = sourceMap.find((item) => item.source.name === sourceName);
    if (!found) return;
    setTesting(sourceName);
    setTestError("");
    try {
      await api("/health/sources/test", jsonRequest("POST", found));
    } catch (error) {
      setTestError(
        error instanceof Error ? error.message : "Test de la source impossible",
      );
    } finally {
      setTesting("");
      refresh();
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <section className="grid gap-3 md:grid-cols-4">
        <Card className="p-4">
          <Label>Dernier cycle</Label>
          <div className="text-xl font-semibold tabular-nums">
            {formatElapsed(lastFinishedAt)}
          </div>
          <div className="text-xs text-muted-foreground">depuis la collecte</div>
        </Card>
        <Card className="p-4">
          <Label>Stockage total</Label>
          <div className="text-xl font-semibold">
            {appHealth ? formatBytes(appHealth.storage_bytes) : "—"}
          </div>
          <div className="text-xs text-muted-foreground">SQLite · Chroma · rapports</div>
        </Card>
        <Card className="p-4">
          <Label>Signaux en base</Label>
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-semibold">
              {appHealth?.signals_total ?? "—"}
            </span>
            <span className="text-xs text-muted-foreground">
              ({appHealth?.signals_p1 ?? "—"} P1)
            </span>
          </div>
        </Card>
        <Card className="p-4">
          <Label>Sources</Label>
          <div className="flex items-baseline gap-5">
            <span className="text-xl font-semibold text-success">
              {appHealth?.sources_healthy ?? "—"}
              <span className="ml-1 text-[10px] font-medium uppercase">saines</span>
            </span>
            <span className="text-xl font-semibold text-error">
              {appHealth?.sources_failing ?? "—"}
              <span className="ml-1 text-[10px] font-medium uppercase">erreur</span>
            </span>
          </div>
        </Card>
      </section>

      <Card className="order-3 p-5">
        <SectionTitle>Santé des sources</SectionTitle>
        <div className="mt-3 max-h-[17rem] overflow-auto">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 border-b border-border bg-background text-xs text-muted-foreground">
              <tr>
                <th className="pb-2">Source</th>
                <th className="pb-2">Dernière réussite</th>
                <th className="pb-2">Latence</th>
                <th className="pb-2">HTTP</th>
                <th className="pb-2">Volume</th>
                <th className="pb-2">État</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {sources.map((source) => (
                <tr
                  key={source.source}
                  className="h-12 border-b border-border/50"
                >
                  <td className="py-3">
                    <div className="font-medium">{source.source}</div>
                    <div className="text-xs text-muted-foreground">
                      {source.category}
                    </div>
                  </td>
                  <td>{formatDate(source.last_success_at)}</td>
                  <td>{source.latency_ms} ms</td>
                  <td>{source.http_status ?? "—"}</td>
                  <td>{source.last_item_count}</td>
                  <td>
                    {source.last_error ? (
                      <span className="text-error" title={source.last_error}>
                        Erreur
                      </span>
                    ) : (
                      <span className="text-success">OK</span>
                    )}
                  </td>
                  <td>
                    <Button
                      variant="ghost"
                      disabled={testing === source.source}
                      onClick={() => testSource(source.source)}
                      iconStart={<TestTube2 className="size-4" />}
                    >
                      {testing === source.source ? "Test…" : "Tester"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!sources.length && (
          <Empty>
            La santé par source apparaîtra après la première collecte.
          </Empty>
        )}
        {testError && <p className="mt-3 text-sm text-error">{testError}</p>}
      </Card>

      <Card className="order-2 p-5">
        <SectionTitle>Collectes automatisées</SectionTitle>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted-foreground">
              <tr>
                <th className="pb-2">Début</th>
                <th className="pb-2">Origine</th>
                <th className="pb-2">État</th>
                <th className="pb-2">Articles</th>
                <th className="pb-2">Erreurs</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className="border-b border-border/50">
                  <td className="py-3">{formatDate(run.started_at)}</td>
                  <td>{run.trigger === "systemd" ? "Automatique" : "Manuelle"}</td>
                  <td>{runStatus[run.status]}</td>
                  <td>{run.result?.articles ?? "—"}</td>
                  <td className={run.error ? "text-error" : "text-muted-foreground"}>
                    {run.error ?? run.result?.errors?.join(" · ") ?? "Aucune"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!runs.length && <Empty>Aucune collecte historisée pour le moment.</Empty>}
      </Card>

      <Card className="order-1 p-5">
        <SectionTitle>Services IA</SectionTitle>
        <div className="flex items-center gap-3 text-sm">
          {appHealth?.assistant.available ? (
            <CheckCircle2 className="size-5 text-success" />
          ) : (
            <CircleAlert className="size-5 text-warning" />
          )}
          <span>
            Serveur d'inférence :{" "}
            {appHealth?.assistant.available ? "joignable" : "indisponible"} ·{" "}
            {appHealth?.assistant.url ?? "—"}
          </span>
        </div>
        <div className="mt-3 flex items-center gap-3 text-sm">
          {appHealth?.rag_index.pending ? (
            <CircleAlert className="size-5 text-warning" />
          ) : (
            <CheckCircle2 className="size-5 text-success" />
          )}
          <span>
            Index RAG : {appHealth?.rag_index.pending ? "en attente" : "à jour"}
            {appHealth?.rag_index.last_success_at && (
              <> · dernière réussite {formatDate(appHealth.rag_index.last_success_at)}</>
            )}
          </span>
        </div>
        {appHealth?.rag_index.last_error && (
          <p className="mt-2 text-xs text-warning">
            Dernière erreur : {appHealth.rag_index.last_error}
          </p>
        )}
      </Card>
    </div>
  );
}
