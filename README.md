# Argos

Argos est une plateforme de veille RSS/Atom auto-hébergée consacrée à l’IA, au RAG, aux agents, au deep learning, au cloud et au HPC. Elle collecte et déduplique les articles, surveille la santé des sources et fournit un assistant RAG local avec citations.

## Fonctions principales

- catalogue YAML de 126 sources actives réparties en 8 catégories, éditable dans l’interface ;
- clés thématiques et priorités P1/P2/P3 affichées dans Flux ;
- taxonomie globale de 18 tags en `snake_case`, filtrables et affichés sur les cartes ;
- collecte concurrente, normalisation, déduplication et rétention dans SQLite ;
- recherche booléenne, filtres cumulatifs par catégorie, priorité, source et tags, et santé des flux ;
- index RAG Chroma synchronisé après collecte ;
- retrieval vectoriel filtré par métadonnées et génération sur Ollama/Nyx ;
- graphe LangGraph minimal avec mémoire de session en mémoire vive ;
- pipeline collecte, indexation, synthèse, condensation et livraison Telegram en un message à 10 h, 14 h et 18 h avec systemd ;
- favoris durables affichés sur Homepage et filtrables dans Flux ;
- progression pondérée et granulaire de la pipeline complète ;
- onglet Config pour éditer les YAML et vider séparément SQLite ou Chroma après confirmation.

La navigation principale est une barre horizontale en pilules. Config regroupe l’éditeur structuré des sources et les réglages avancés dans deux sous-onglets.
L’onglet Assistants regroupe le chatbot RAG et l’état non sensible du bot Telegram.
Il décrit aussi les cycles automatiques à partir du fichier timer systemd réellement monté dans l’API, ainsi que la dernière exécution enregistrée.
Homepage regroupe les quatre métriques de pilotage, les 30 derniers favoris dans une fenêtre de trois cartes et le dernier rapport Markdown de `data/reports/`. Santé présente le dernier cycle, le stockage total, les signaux dont les P1 et l’état agrégé des sources.

Après chaque indexation réussie, un agent LangGraph repère les nouveaux P1, effectue un retrieval Chroma global puis rédige le rapport en un seul appel Nyx avant de remplacer atomiquement `data/summary.md`. Une panne Nyx conserve le document précédent et reporte les signaux à la prochaine collecte.

## Architecture

```text
Navigateur :1207
    │
React/Vite servi par nginx :8080
    │ /api
Flask :8000 (réseau Docker uniquement)
    ├── flux RSS/Atom
    ├── SQLite /app/data/monitoring.db
    ├── Chroma /app/data/chroma
    └── Ollama sur Nyx 192.168.1.11:11434
```

Le code serveur se trouve dans `backend/` : `feeds/` regroupe collecte, articles et stockage, `system/` la configuration et la santé, et `rag/` l’indexation, le retrieval et l’agent. Le service Compose garde le nom `api`, même si son contexte de build est `./backend`.

## Démarrage

Prérequis : Docker Engine et Docker Compose.

```bash
docker compose config
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:1207/api/health
```

Ouvrir <http://localhost:1207>, puis lancer la première collecte depuis **Flux**. Le port public est `1207`; Flask n’est pas publié directement.

Les données persistantes sont dans `data/monitoring.db` et `data/chroma/`. Elles sont montées dans les conteneurs et ne doivent pas être remplacées lors d’une synchronisation.

## Configuration

- `config/sources.yml` : taxonomie globale des tags, catégories, flux, clés, priorités, fenêtre RSS et rétention SQLite ;
- `config/ai.yaml` : Ollama, embeddings RAG, Chroma, chunking et retrieval ;
- `config/prompt.yaml` : prompts du chatbot, du self-query, de la synthèse P1 et du summarizer Telegram ;
- `config/telegram.yaml` : livraison facultative du rapport AI Summary ;
- `systemd/argos-collect.*` : collecte à 10 h, 14 h et 18 h sur Atlas.

Les embeddings utilisent actuellement `nomic-embed-text-v2-moe:latest` et les réponses `qwen3.6:27b` sur Nyx. La disponibilité de Nyx est nécessaire pour l’indexation Chroma et l’assistant, mais pas pour lire les articles déjà collectés.

Si Nyx est indisponible après une collecte, les articles restent dans SQLite et l’index RAG passe en attente. La prochaine collecte, planifiée ou manuelle, reprend automatiquement la synchronisation incrémentale.

## Vérifications locales

```bash
PYENV_VERSION=nexus ruff check backend tests
PYENV_VERSION=nexus black --check backend tests
PYTHONPATH=backend PYENV_VERSION=nexus python -m unittest discover -s tests
npm --prefix web run lint
npm --prefix web run build
docker compose config --quiet
```

La documentation détaillée commence dans [`docs/PROJECT.md`](docs/PROJECT.md). Le contexte opérationnel condensé est dans [`docs/QUICK_CATCH.md`](docs/QUICK_CATCH.md).
