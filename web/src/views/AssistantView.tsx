import { Bot } from "lucide-react";
import { useState } from "react";

import { Button, Card, Pill, SectionTitle } from "../components/ui";
import { api, jsonRequest } from "../lib/api";
import type { AssistantStatus } from "../types";

export function AssistantView({ status }: { status: AssistantStatus | null }) {
  const [prompt, setPrompt] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  const send = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    try {
      const response = await api<{ answer: string }>(
        "/assistant",
        jsonRequest("POST", { prompt }),
      );
      setAnswer(response.answer);
    } catch (error) {
      setAnswer(
        error instanceof Error ? error.message : "Assistant indisponible",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="p-6">
      <div className="flex items-center gap-3">
        <Bot className="size-7 text-brand" />
        <div>
          <SectionTitle>
            Assistant <Pill tone="success">RAG</Pill>
          </SectionTitle>
          <p className="text-sm text-muted-foreground">
            Inférence Nyx via {status?.url ?? "http://192.168.1.11:1434"} ·
            modèle {status?.model ?? "qwen3.6:27b"}.
          </p>
        </div>
      </div>
      <div className="mt-5 rounded-lg border border-border bg-muted p-3 text-sm">
        {status?.available ? (
          <span className="text-success">
            Endpoint joignable. Les réponses sont enrichies par les articles
            sémantiquement les plus pertinents et citent leur contexte.
          </span>
        ) : (
          <span className="text-warning">
            Endpoint actuellement indisponible :{" "}
            {status?.error ?? "diagnostic en cours"}. L'onglet reste prêt
            lorsque Nyx :1434 sera démarré.
          </span>
        )}
      </div>
      <textarea
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        placeholder="Questionner l'assistant (WIP)…"
        className="mt-4 min-h-28 w-full rounded-lg border border-border bg-background p-3 text-sm"
      />
      <div className="mt-3 flex justify-end">
        <Button
          onClick={send}
          disabled={loading || !status?.available}
          iconStart={<Bot className="size-4" />}
        >
          {loading ? "Inférence…" : "Envoyer"}
        </Button>
      </div>
      {answer && (
        <div className="mt-5 whitespace-pre-wrap rounded-lg border border-border p-4 text-sm leading-6">
          {answer}
        </div>
      )}
    </Card>
  );
}
