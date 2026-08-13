import { Database, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button, Card, SectionTitle, TabBar } from "../components/ui";
import { api, jsonRequest } from "../lib/api";
import type { Config } from "../types";
import { SourcesView } from "./SourcesView";

type ConfigName = "sources" | "ai" | "telegram" | "prompt" | "sentences" | "views";
type ConfigFile = { name: ConfigName; label: string; content: string };

const CONFIGS: Array<{ name: ConfigName; label: string }> = [
  { name: "sources", label: "Sources" },
  { name: "ai", label: "IA et RAG" },
  { name: "telegram", label: "Telegram" },
  { name: "prompt", label: "Prompts" },
  { name: "sentences", label: "Phrases Telegram" },
  { name: "views", label: "Vues Flux" },
];

type ConfigSection = "sources" | "advanced";
const CONFIG_SECTIONS = [
  { value: "sources", label: "Sources" },
  { value: "advanced", label: "YAML" },
] satisfies Array<{ value: ConfigSection; label: string }>;

export function ConfigView({
  config,
  onSourcesChange,
  onSourcesSave,
  savingSources,
  onChanged,
}: {
  config: Config;
  onSourcesChange: (config: Config) => void;
  onSourcesSave: () => void;
  savingSources: boolean;
  onChanged: () => void;
}) {
  const [section, setSection] = useState<ConfigSection>("sources");
  const [files, setFiles] = useState<ConfigFile[]>([]);
  const [selected, setSelected] = useState<ConfigName>("sources");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (section !== "advanced") return;
    void Promise.all(
      CONFIGS.map(async ({ name, label }) => ({
        name,
        label,
        content: (await api<{ content: string }>(`/config/${name}`)).content,
      })),
    )
      .then(setFiles)
      .catch((error: Error) => setMessage(error.message));
  }, [section]);

  const current = files.find((file) => file.name === selected);
  const updateContent = (content: string) =>
    setFiles((items) =>
      items.map((item) => (item.name === selected ? { ...item, content } : item)),
    );

  const save = async () => {
    if (!current) return;
    setBusy(true);
    setMessage("");
    try {
      await api(
        `/config/${selected}`,
        jsonRequest("PUT", { content: current.content }),
      );
      setMessage(`${current.label} enregistré.`);
      onChanged();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Enregistrement impossible",
      );
    } finally {
      setBusy(false);
    }
  };

  const flush = async (store: "sqlite" | "chroma") => {
    const confirmation = window.prompt(
      `Cette action efface ${store === "sqlite" ? "toutes les données SQLite" : "tout l’index Chroma"}. Saisissez ${store.toUpperCase()} pour confirmer.`,
    );
    if (confirmation !== store.toUpperCase()) return;
    setBusy(true);
    setMessage("");
    try {
      await api(`/storage/${store}`, { method: "DELETE" });
      setMessage(`${store === "sqlite" ? "SQLite" : "Chroma"} a été vidé.`);
      onChanged();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Suppression impossible");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <TabBar items={CONFIG_SECTIONS} value={section} onChange={setSection} />

      {section === "sources" ? (
        <SourcesView
          config={config}
          onChange={onSourcesChange}
          onSave={onSourcesSave}
          saving={savingSources}
        />
      ) : (
        <>
          <Card className="p-5">
            <SectionTitle>Configuration YAML</SectionTitle>
            <p className="text-sm text-muted-foreground">
              Les fichiers sont validés comme YAML avant leur remplacement
              atomique.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {CONFIGS.map((item) => (
                <Button
                  key={item.name}
                  variant={selected === item.name ? "primary" : "secondary"}
                  onClick={() => setSelected(item.name)}
                >
                  {item.label}
                </Button>
              ))}
            </div>
            <textarea
              aria-label={`Configuration ${current?.label ?? selected}`}
              value={current?.content ?? ""}
              onChange={(event) => updateContent(event.target.value)}
              className="mt-4 min-h-[32rem] w-full rounded-md border border-border bg-background p-3 font-mono text-xs"
              spellCheck={false}
            />
            <Button
              className="mt-3"
              disabled={busy || !current}
              onClick={save}
              iconStart={<Save className="size-4" />}
            >
              Enregistrer {current?.label ?? ""}
            </Button>
          </Card>

          <Card className="border-error/30 p-5">
            <SectionTitle>Zone destructive</SectionTitle>
            <p className="text-sm text-muted-foreground">
              SQLite contient les articles et analyses. Chroma contient l’index
              RAG dérivé. Une tâche en cours bloque ces opérations.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => flush("sqlite")}
                iconStart={<Database className="size-4" />}
              >
                Vider SQLite
              </Button>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => flush("chroma")}
                iconStart={<Trash2 className="size-4" />}
              >
                Vider Chroma
              </Button>
            </div>
          </Card>
          {message && <p className="text-sm text-muted-foreground">{message}</p>}
        </>
      )}
    </div>
  );
}
