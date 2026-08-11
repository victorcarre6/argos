import { CheckCircle2, CircleAlert, TestTube2 } from "lucide-react";
import { useState } from "react";

import { Button, Card, Empty, Label, SectionTitle } from "../components/ui";
import { api, jsonRequest } from "../lib/api";
import { formatBytes, formatDate } from "../lib/format";
import type { AppHealth, Config, SourceHealth } from "../types";

export function HealthView({
  appHealth,
  sources,
  config,
  refresh,
}: {
  appHealth: AppHealth | null;
  sources: SourceHealth[];
  config: Config;
  refresh: () => void;
}) {
  const [testing, setTesting] = useState("");
  const sourceMap = config.categories.flatMap((category) =>
    category.sources.map((source) => ({ category, source })),
  );

  const testSource = async (sourceName: string) => {
    const found = sourceMap.find((item) => item.source.name === sourceName);
    if (!found) return;
    setTesting(sourceName);
    try {
      await api("/health/sources/test", jsonRequest("POST", found));
    } finally {
      setTesting("");
      refresh();
    }
  };

  return (
    <div className="space-y-4">
      <section className="grid gap-3 md:grid-cols-4">
        <Card className="p-4">
          <Label>Base SQLite</Label>
          <div className="text-xl font-semibold">
            {appHealth ? formatBytes(appHealth.database_bytes) : "—"}
          </div>
        </Card>
        <Card className="p-4">
          <Label>Doublons regroupés</Label>
          <div className="text-xl font-semibold">
            {appHealth?.duplicates ?? "—"}
          </div>
        </Card>
        <Card className="p-4">
          <Label>Sources saines</Label>
          <div className="text-xl font-semibold text-success">
            {appHealth?.sources_healthy ?? "—"}
          </div>
        </Card>
        <Card className="p-4">
          <Label>Sources en erreur</Label>
          <div className="text-xl font-semibold text-error">
            {appHealth?.sources_failing ?? "—"}
          </div>
        </Card>
      </section>

      <Card className="p-5">
        <SectionTitle>Santé des sources</SectionTitle>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted-foreground">
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
                <tr key={source.source} className="border-b border-border/50">
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
      </Card>

      <Card className="p-5">
        <SectionTitle>Services IA</SectionTitle>
        <div className="flex items-center gap-3 text-sm">
          {appHealth?.assistant.available ? (
            <CheckCircle2 className="size-5 text-success" />
          ) : (
            <CircleAlert className="size-5 text-warning" />
          )}
          <span>
            Assistant Nyx :{" "}
            {appHealth?.assistant.available ? "joignable" : "indisponible"} ·{" "}
            {appHealth?.assistant.url ?? "—"}
          </span>
        </div>
      </Card>
    </div>
  );
}
