import { Bot, Clock3, RotateCcw, Send, User } from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import ReactMarkdown from "react-markdown";

import { Button, Card, Pill, SectionTitle } from "../components/ui";
import { api, jsonRequest } from "../lib/api";
import { formatDate } from "../lib/format";
import type {
  AutomationStatus,
  CollectionRun,
  TelegramStatus,
} from "../types";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  model?: string;
  sourceCount?: number;
  error?: boolean;
  pending?: boolean;
};

function createId() {
  return globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function loadMessages(): ChatMessage[] {
  try {
    const stored = JSON.parse(
      localStorage.getItem("argos-assistant-messages") ?? "[]",
    );
    return Array.isArray(stored) ? stored : [];
  } catch {
    return [];
  }
}

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
  const [messages, setMessages] = useState<ChatMessage[]>(loadMessages);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => {
    const existing = localStorage.getItem("argos-assistant-session");
    if (existing) return existing;
    const created = createId();
    localStorage.setItem("argos-assistant-session", created);
    return created;
  });
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem("argos-assistant-messages", JSON.stringify(messages));
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const question = prompt.trim();
    if (!question || loading) return;
    const pendingId = createId();
    setPrompt("");
    setMessages((current) => [
      ...current,
      { id: createId(), role: "user", content: question },
      {
        id: pendingId,
        role: "assistant",
        content: "Réflexion en cours…",
        pending: true,
      },
    ]);
    setLoading(true);
    try {
      const response = await api<{
        answer: string;
        model: string;
        sources: unknown[];
      }>(
        "/assistant",
        jsonRequest("POST", { prompt: question, session_id: sessionId }),
      );
      setMessages((current) =>
        current.map((message) =>
          message.id === pendingId
            ? {
                ...message,
                content: response.answer,
                model: response.model,
                sourceCount: response.sources.length,
                pending: false,
              }
            : message,
        ),
      );
    } catch (error) {
      setMessages((current) =>
        current.map((message) =>
          message.id === pendingId
            ? {
                ...message,
                content:
                  error instanceof Error
                    ? error.message
                    : "Assistant indisponible",
                error: true,
                pending: false,
              }
            : message,
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  const newConversation = async () => {
    if (loading) return;
    await api(`/assistant/session/${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
    }).catch(() => undefined);
    const created = createId();
    localStorage.setItem("argos-assistant-session", created);
    localStorage.removeItem("argos-assistant-messages");
    setSessionId(created);
    setMessages([]);
    setPrompt("");
  };

  const onPromptKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  };

  return (
    <div className="space-y-5">
      <Card className="flex h-[42rem] flex-col overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-lg bg-brand/10 text-brand">
              <Bot className="size-5" />
            </div>
            <div>
              <SectionTitle>Assistant</SectionTitle>
              <p className="text-xs text-muted-foreground">
                Conversation RAG avec mémoire de session
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            onClick={() => void newConversation()}
            disabled={loading}
            iconStart={<RotateCcw className="size-4" />}
            title="Effacer la conversation et créer une nouvelle session"
          >
            Nouvelle conversation
          </Button>
        </div>

        <div
          className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto bg-muted/30 p-5"
          aria-live="polite"
        >
          {!messages.length && (
            <div className="m-auto max-w-md text-center text-sm text-muted-foreground">
              <Bot className="mx-auto mb-3 size-8 text-brand/70" />
              Posez une question sur les signaux collectés. Les questions suivantes
              tiendront compte des échanges précédents de cette session.
            </div>
          )}
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex max-w-[85%] gap-2 ${
                message.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
              }`}
            >
              <div
                className={`mt-1 flex size-7 shrink-0 items-center justify-center rounded-full ${
                  message.role === "user"
                    ? "bg-brand text-brand-foreground"
                    : "border border-border bg-background text-brand"
                }`}
              >
                {message.role === "user" ? (
                  <User className="size-3.5" />
                ) : (
                  <Bot className="size-3.5" />
                )}
              </div>
              <div
                className={`min-w-0 rounded-xl px-4 py-3 text-sm leading-6 ${
                  message.role === "user"
                    ? "bg-brand text-brand-foreground"
                    : message.error
                      ? "border border-error/30 bg-error/10 text-error"
                      : "border border-border bg-background"
                } ${message.pending ? "animate-pulse text-muted-foreground" : ""}`}
              >
                {message.role === "assistant" && !message.pending ? (
                  <div className="markdown">
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  </div>
                ) : (
                  <div className="whitespace-pre-wrap">{message.content}</div>
                )}
                {message.model && (
                  <div className="mt-2 text-[10px] text-muted-foreground">
                    {message.model}
                    {message.sourceCount
                      ? ` · ${message.sourceCount} source${message.sourceCount > 1 ? "s" : ""}`
                      : ""}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-border bg-background p-4">
          <div className="flex items-end gap-3 rounded-lg border border-border bg-muted/30 p-2 focus-within:border-brand">
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={onPromptKeyDown}
              placeholder="Questionner l'assistant…"
              rows={2}
              disabled={loading}
              className="max-h-32 min-h-12 flex-1 resize-none bg-transparent px-2 py-1 text-sm outline-none disabled:cursor-not-allowed"
            />
            <Button
              onClick={() => void send()}
              disabled={loading || !prompt.trim()}
              iconStart={<Send className="size-4" />}
            >
              {loading ? "Inférence…" : "Envoyer"}
            </Button>
          </div>
          <p className="mt-2 px-1 text-[11px] text-muted-foreground">
            Entrée pour envoyer · Maj + Entrée pour aller à la ligne
          </p>
        </div>
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
