import { Bot, Clock3, Send } from "lucide-react";
import { useState } from "react";

import { Button, Card, Pill, SectionTitle } from "../components/ui";
import { api, jsonRequest } from "../lib/api";
import { formatDate } from "../lib/format";
import type {
  AutomationStatus,
  CollectionRun,
  TelegramStatus,
} from "../types";

export function AssistantView({
  telegram,
  automation,
  runs,
}: {
  telegram: TelegramStatus | null;
  automation: AutomationStatus | null;
  runs: CollectionRun[];
}) {
  const [prompt, setPrompt] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => {
    const existing = localStorage.getItem("argos-assistant-session");
    if (existing) return existing;
    const created = globalThis.crypto?.randomUUID?.() ??
      `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem("argos-assistant-session", created);
    return created;
  });

  const send = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    try {
      const response = await api<{ answer: string }>(
        "/assistant",
        jsonRequest("POST", { prompt, session_id: sessionId }),
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
    <div className="space-y-5">
      <Card className="p-6">
        <div className="flex items-center gap-3">
          <Bot className="size-7 text-brand" />
          <div>
            <SectionTitle>Assistant</SectionTitle>
          </div>
        </div>
        <textarea
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Questionner l'assistant…"
          className="mt-4 min-h-28 w-full rounded-lg border border-border bg-background p-3 text-sm"
        />
        <div className="mt-3 flex justify-end">
          <Button
            onClick={send}
            disabled={loading}
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

      <Card className="p-6">
        <div className="flex items-start gap-3">
          <Send className="mt-0.5 size-6 text-success" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <SectionTitle>Bot Telegram</SectionTitle>
              <Pill
                tone={
                  telegram?.ready && !telegram.report_pending
                    ? "success"
                    : telegram?.report_pending
                      ? "warning"
                      : "neutral"
                }
              >
                {telegram?.ready && telegram.report_pending
                  ? "Rapport en attente"
                  : telegram?.ready
                    ? "Prêt"
                  : telegram?.enabled
                    ? "Configuration incomplète"
                    : "Désactivé"}
              </Pill>
            </div>
            <p className="text-sm text-muted-foreground">
              Envoie le rapport généré après la collecte.
            </p>
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <dt className="text-muted-foreground">Token</dt>
                <dd className="font-medium">
                  {telegram?.token_configured ? "Configuré" : "Absent"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Conversation</dt>
                <dd className="font-medium">
                  {telegram?.chat_configured ? "Configurée" : "Absente"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Usage</dt>
                <dd className="font-medium">Rapport AI Summary</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Dernier envoi</dt>
                <dd className="font-medium">
                  {telegram?.last_sent_at
                    ? formatDate(telegram.last_sent_at)
                    : "Jamais"}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </Card>

      <Card className="p-6">
        <div className="flex items-start gap-3">
          <Clock3 className="mt-0.5 size-6 text-success" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <SectionTitle>Cycles de collecte</SectionTitle>
              <Pill tone={automation?.configured ? "success" : "warning"}>
                {automation?.configured ? "Planifié" : "Timer indisponible"}
              </Pill>
            </div>
            <p className="text-sm text-muted-foreground">
              Collectes et pipeline de traitement automatisées.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {automation?.times.map((time) => (
                <Pill key={time} tone="success">
                  {time}
                </Pill>
              ))}
              {!automation?.times.length && <Pill>Aucun horaire lisible</Pill>}
            </div>
            <dl className="mt-4 grid gap-3 text-sm">
              <div>
                <dt className="text-muted-foreground">Dernier cycle</dt>
                <dd className="font-medium">
                  {formatDate(runs[0]?.started_at ?? null)}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </Card>
    </div>
  );
}
