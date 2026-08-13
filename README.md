# Argos

Argos est une plateforme de veille RSS/Atom auto-hébergée consacrée à l’IA, au RAG, aux agents, au deep learning, au cloud et au HPC. Elle collecte et déduplique les articles, surveille la santé des sources et fournit un assistant RAG local avec citations.

## Fonctions principales

- catalogue YAML de 126 sources actives réparties en 8 catégories, éditable dans l’interface ;
- clés thématiques héritées comme tags parents et priorités P1/P2/P3 ;
- taxonomie globale de 19 tags en `snake_case`, enrichie par le contenu et affichée en pilules vertes cliquables ;
- collecte concurrente, normalisation, déduplication et rétention dans SQLite ;
- recherche booléenne, filtres multisélection par catégorie, priorité, source et tags, cinq vues persistantes maximum et santé des flux ;
- index RAG Chroma synchronisé après collecte ;
- retrieval vectoriel filtré par métadonnées et génération sur Ollama/Nyx ;
- graphe LangGraph minimal avec mémoire de session en mémoire vive ;
- pipeline collecte, indexation, rapports thématiques et sommaire Telegram interactif à 10 h, 14 h et 18 h avec systemd ;
- favoris durables affichés sur Homepage et filtrables dans Flux ;
- Data Analysis des favoris/masqués avec taux d’acceptation, distribution des scores et heatmap ApexCharts sombre ;
- progression pondérée et granulaire de la pipeline complète ;
- onglet Config pour éditer les YAML et vider séparément SQLite ou Chroma après confirmation.

La navigation principale suit Homepage, Flux, Assistants, Data Analysis, Santé et Config. Config regroupe l’éditeur structuré des sources et les YAML avancés. Assistants réunit le chatbot RAG, l’état non sensible du bot Telegram et les cycles automatiques. Homepage affiche les quatre métriques, les favoris en cartes compactes et le dernier rapport Markdown. Data Analysis exploite les snapshots durables de `signal_feedback`. Santé présente cycles, stockage, index RAG et état des sources.

Après chaque indexation réussie, un agent LangGraph repère les nouveaux P1, planifie jusqu’à quatre axes plus `5. Autre`, effectue un retrieval et une rédaction par partie, puis fusionne les résultats dans le rapport Markdown. Une panne Nyx conserve le document précédent et reporte les signaux à la prochaine collecte.

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

## Démarrage rapide

Prérequis : Docker Engine et Docker Compose.

```bash
docker compose config
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:1207/api/health
```

Ouvrir <http://localhost:1207>, puis lancer la première collecte depuis **Flux**. Le port public est `1207`; Flask n’est pas publié directement.

Les données persistantes sont dans `data/monitoring.db` et `data/chroma/`. Elles sont montées dans les conteneurs et ne doivent pas être remplacées lors d’une synchronisation.

## Configuration par setup

### Setup 1 — développement local complet avec Docker

Ce mode reproduit l’architecture Atlas sur la machine de développement. Vérifier dans `config/ai.yaml` que les URL Ollama sont joignables depuis les conteneurs. La configuration versionnée cible Nyx sur `http://192.168.1.11:11434`.

Créer un `.env` local uniquement si Telegram est activé :

```dotenv
TELEGRAM_BOT_TOKEN=123456:secret
```

Pour travailler sans Telegram, conserver `enabled: false` dans `config/telegram.yaml` ou laisser le token vide. Lancer ensuite :

```bash
docker compose config
docker compose up -d --build
curl --fail http://127.0.0.1:1207/api/health
```

Les fichiers `config/` sont montés dans l’API et `data/` conserve SQLite, Chroma et les rapports entre les reconstructions.

### Setup 2 — frontend et backend en développement

Ce mode est adapté aux modifications rapides de l’interface. Il nécessite Python avec les dépendances de `backend/`, Node.js et un service Ollama accessible pour les fonctions IA.

```bash
PYTHONPATH=backend PYENV_VERSION=nexus python -m flask --app app run --host 127.0.0.1 --port 8000
npm --prefix web install
npm --prefix web run dev
```

Vite sert l’interface de développement et proxifie `/api` vers Flask selon `web/vite.config.ts`. Les chemins peuvent être remplacés avec `APP_ROOT`, `SOURCES_CONFIG`, `PROMPT_CONFIG`, `SENTENCES_CONFIG`, `VIEWS_CONFIG`, `TIMER_CONFIG` et `DATABASE_PATH`.

### Setup 3 — déploiement Atlas

Atlas héberge Argos dans `/home/vika/argos`, publie l’interface sur `1207` et conserve son `.env` et son répertoire `data/` hors synchronisation :

```bash
cd /home/vika/code/Projects/pantone/argos
rsync -az --delete \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude 'web/node_modules/' \
  --exclude 'web/dist/' \
  --exclude 'data/' \
  --exclude 'config/sources copy*.yml' \
  ./ atlas:/home/vika/argos/

ssh atlas 'cd /home/vika/argos && docker compose config && docker compose up -d --build'
ssh atlas 'curl --fail http://127.0.0.1:1207/api/health'
```

Ne jamais retirer l’exclusion de `data/` avec `--delete` : ce répertoire contient la base, l’index et l’historique des rapports de production.

### Setup 4 — Ollama, embeddings et profils RAG

Les modèles doivent être disponibles sur Nyx avant une pipeline complète :

```bash
ssh vika@192.168.1.11 'ollama pull nomic-embed-text-v2-moe:latest'
ssh vika@192.168.1.11 'ollama pull qwen3.6:27b'
ssh vika@192.168.1.11 'ollama pull qwen3.6:35b-a3b'
```

`config/ai.yaml` sépare les responsabilités :

- `embedding` configure le serveur et le modèle d’embedding partagé ;
- `assistant` configure le modèle de réponse, son timeout et `assistant.rag`, profil du chat multi-tour ;
- `rag` configure Chroma, l’indexation, le chunking et le retrieval du rapport ;
- `summary.top_n` borne les nouveaux P1 incorporés à chaque rapport.

Dans `config/prompt.yaml`, `summary.plan` produit jusqu’à quatre axes principaux ; les signaux restants sont regroupés dans `5. Autre`.

La configuration actuelle indexe au plus 2 000 articles, découpe à partir de 400 caractères en chunks de 800 avec un chevauchement de 180, utilise `10/4` candidats/résultats pour le rapport et `30/10` pour l’assistant.

### Setup 5 — Telegram

Créer le bot avec BotFather, récupérer les identifiants des conversations autorisées, puis configurer uniquement les éléments non secrets dans `config/telegram.yaml` :

```yaml
enabled: true
bot_token_env: TELEGRAM_BOT_TOKEN
chat_ids:
  user1: "123456789"
  user2: "987654321"
max_message_chars: 3900
```

Sur Atlas, enregistrer le token dans `/home/vika/argos/.env`, protéger le fichier, puis recréer l’API :

```bash
ssh atlas 'chmod 600 /home/vika/argos/.env'
ssh atlas 'cd /home/vika/argos && docker compose up -d --build api'
```

Le token ne doit jamais être écrit dans un YAML versionné. Le bot envoie le sommaire numéroté, puis accepte plusieurs demandes `1` à `5`, `/help` et `/download`. Le backend reçoit les commandes par long polling et persiste son offset.

### Setup 6 — automatisation systemd sur Atlas

Installer les unités une première fois, ou après une modification de `systemd/` :

```bash
ssh atlas
cd /home/vika/argos
sudo cp systemd/argos-collect.service systemd/argos-collect.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now argos-collect.timer
systemctl list-timers argos-collect.timer
```

Le timer lance la pipeline à 10 h, 14 h et 18 h selon le fuseau local d’Atlas. Les déploiements limités au code ou à `config/` ne nécessitent pas de réinstaller les unités.

## Fichiers de configuration

- `config/sources.yml` : taxonomie globale des tags, catégories, flux, clés, priorités, fenêtre RSS et rétention SQLite ;
- `config/ai.yaml` : Ollama, embeddings RAG, Chroma, chunking et retrieval ;
- `config/prompt.yaml` : prompts du chatbot, du self-query, du plan et des rapports thématiques P1 ;
- `config/sentences.yaml` : phrases optionnelles sélectionnées aléatoirement pour conclure le sommaire Telegram ;
- `config/views.yaml` : cinq raccourcis persistants maximum pour les filtres et l’affichage de Flux ;
- `config/telegram.yaml` : destinataires autorisés du bot Telegram interactif ;
- `systemd/argos-collect.*` : collecte à 10 h, 14 h et 18 h sur Atlas.

`web/` charge ApexCharts uniquement à l’ouverture de Data Analysis afin de ne pas alourdir le bundle principal.

Les embeddings utilisent actuellement `nomic-embed-text-v2-moe:latest`, les réponses `qwen3.6:27b` et la planification des requêtes `qwen3.6:35b-a3b` sur Nyx. La disponibilité de Nyx est nécessaire pour l’indexation Chroma et l’assistant, mais pas pour lire les articles déjà collectés.

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
