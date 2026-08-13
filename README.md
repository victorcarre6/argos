# Argos

Argos est une plateforme auto-hébergée de veille RSS/Atom. Elle collecte, classe et déduplique des signaux, génère des rapports thématiques et permet d’interroger le corpus avec un assistant RAG local.

## Fonctionnalités

- catalogue de sources et taxonomie configurables en YAML ;
- collecte concurrente, scoring, tags hérités et déduplication dans SQLite ;
- recherche, filtres multisélection et vues sauvegardées ;
- favoris, signaux masqués et visualisations éditoriales ;
- index vectoriel Chroma et assistant conversationnel avec citations ;
- rapports thématiques et bot Telegram interactif ;
- suivi de la collecte, des sources et de l’index RAG.

## Architecture

- `backend/` : API Flask, collecte, stockage et RAG ;
- `web/` : SPA React/Vite servie par nginx ;
- `config/` : sources, modèles, prompts, vues et Telegram ;
- `data/` : SQLite, Chroma et rapports persistants ;
- `systemd/` : exemple de planification des collectes.

SQLite est la source de vérité. Chroma est un index dérivé reconstructible. Les fonctions IA utilisent un serveur compatible Ollama configuré dans `config/ai.yaml`.

## Démarrage

Prérequis : Docker Engine et Docker Compose.

```bash
docker compose up -d --build
curl --fail http://127.0.0.1:1207/api/health
```

L’interface est disponible sur <http://localhost:1207>. Les données de `data/` doivent être conservées entre les reconstructions.

## Développement

Prérequis supplémentaires : Python, Node.js et les dépendances du backend.

```bash
PYTHONPATH=backend python -m flask --app app run --host 127.0.0.1 --port 8000
npm --prefix web install
npm --prefix web run dev
```

Vite proxifie `/api` vers Flask. Les chemins et services externes se configurent par YAML ou variables d’environnement.

## Configuration

- `config/sources.yml` : sources, catégories, tags, priorités et rétention ;
- `config/ai.yaml` : modèles, embeddings, Chroma et retrieval ;
- `config/prompt.yaml` : prompts de l’assistant et des rapports ;
- `config/views.yaml` : vues sauvegardées de Flux ;
- `config/telegram.yaml` : activation et destinataires Telegram ;
- `config/sentences.yaml` : phrases optionnelles du sommaire Telegram.

Les secrets, notamment `TELEGRAM_BOT_TOKEN`, doivent rester dans `.env` et ne jamais être versionnés.

## Vérifications

```bash
ruff check backend tests
black --check backend tests
PYTHONPATH=backend python -m unittest discover -s tests
npm --prefix web run lint
npm --prefix web run build
docker compose config --quiet
```

