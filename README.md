# Argos

> A self-hosted RSS monitoring platform for generative AI, agents, RAG, deep learning, and HPC.

Argos collects RSS/Atom feeds, stores articles locally in SQLite, and provides a React interface for browsing and exploring them. Sources, alerts, and AI processing remain under your control.

## Highlights

- Feed browsing, boolean search, filters, reading mode, and a “since last visit” digest.
- Editable sources and categories from the interface or [`config/sources.yml`](config/sources.yml).
- Per-source health: last success, latency, HTTP status, volume, and one-source test action.
- Tracking-URL and similar-syndication deduplication.
- Heatmaps, semantic clusters, and an embedding-powered scatter plot.
- RAG assistant: relevant-article retrieval, local Ollama inference, and citations.
- Scheduled collection with systemd and optional Telegram alerts.

## Architecture

```text
Browser
   │ :1207
   ▼
React + nginx ── /api ──► Flask / RSS / RAG
                            │
                            ├── SQLite (articles, health, embeddings, clusters)
                            └── Local Ollama (optional)
```

## Quick start

Requirements: Docker Engine and Docker Compose.

```bash
git clone ...
cd argos
docker compose up -d --build
```

Open [http://localhost:1207](http://localhost:1207), then start the first collection from the **Feed** tab.

```bash
docker compose ps
curl http://localhost:1207/api/health
docker compose logs -f api
```

Persistent data is stored in `data/monitoring.db`. Do not run `docker compose down -v`.

## Configuration

- Sources: [`config/sources.yml`](config/sources.yml)
- Local AI: [`config/ai.yaml`](config/ai.yaml)
- Telegram: [`config/telegram.yaml`](config/telegram.yaml)

Configure the Ollama URL and models in `config/ai.yaml`:

- embeddings: `nomic-embed-text-v2-moe:latest`;
- assistant: `qwen3.6:27b`.

The **Viz** tab initializes embeddings and clusters on demand. The assistant retrieves the closest articles before generating an answer.

## Deployment

Argos exposes port `1207`. On the target host:

```bash
git clone <your-repository> argos
cd argos
docker compose up -d --build
```

