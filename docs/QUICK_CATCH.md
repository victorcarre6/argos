# Argos — Quick Catch

État de référence : 12/08/2026. Argos est servi sur Atlas à l’adresse `http://192.168.1.50:1207`. Le dépôt de développement est `/home/vika/code/Projects/pantone/argos`; le déploiement est `/home/vika/argos`.

## État actuel

- 134 sources, 8 catégories, 14 clés contrôlées et priorités P1/P2/P3.
- 125 sources actives : 21 flux défaillants ont été remplacés par des flux officiels vérifiés ; ENISA, EuroHPC JU, HaDEA et OECD AI restent catalogués mais désactivés faute de RSS/Atom officiel exploitable.
- Ordre des catégories : agrégateurs, laboratoires/providers, frameworks/SDK, HPC, Ops/cloud, sécurité, financements, institutions.
- Dans **Flux**, la première ligne conserve catégorie, priorité P1/P2/P3, recherche textuelle et tri. La seconde ajoute une autocomplétion multi-source et un dropdown multi-tag. Les groupes sont cumulatifs ; les sources sélectionnées sont alternatives et tous les tags sélectionnés doivent être présents. Chaque choix devient une pilule verte supprimable.
- La hauteur des deux champs textuels de filtrage s’adapte au viewport avec `clamp(1.25rem, 4vh, 2.25rem)` sans dépasser leur taille historique.
- La source de chaque carte Flux est affichée dans une pilule teintée avec la couleur de sa catégorie.
- Les cartes affichent la date et l’heure de publication du flux, jamais l’heure d’importation comme valeur de remplacement.
- La croix d’une carte passe son champ SQLite `view` à faux : elle disparaît de Flux sans être supprimée ni retirée du RAG.
- L’étoile enregistre un bon candidat ; la croix enregistre un mauvais candidat. La table `signal_feedback` conserve durablement un instantané complet hors rétention et purge courante.
- Homepage affiche jusqu’à 30 favoris durables par récupération décroissante dans une carte haute de trois éléments. Flux possède un toggle étoile cumulable avec tous les autres filtres.
- Pendant une collecte, Flux affiche une progression pondérée de toute la pipeline : sources RSS, persistance/scoring, articles Chroma, nœuds et parties de synthèse, puis messages Telegram. Le libellé courant et le compteur local sont actualisés chaque seconde.
- Les quatre métriques de pilotage quotidien sont le total des signaux, les nouveaux signaux de la dernière collecte, les signaux P1 de la fenêtre courante et le bilan de la dernière collecte.
- Conteneur web `argos` : React/Vite compilé, nginx interne `8080`, port LAN `1207`.
- Conteneur backend `argos-api` : Flask interne `8000`, limite mémoire `700m`.
- SQLite est la source de vérité des articles et des états de flux.
- La fenêtre d’ingestion RSS et la rétention SQLite sont pilotées par `collection.max_age_days` et `storage.retention_days` dans le YAML.
- Une taxonomie globale de 18 tags en `snake_case` ASCII remplace les mots-clés propres aux catégories. Ses alias sont normalisés (`agentic` et `multi-agent` → `agents`) et les limites de mots évitent les correspondances accidentelles. Les `keys` décrivent toujours la source, les tags décrivent l’article.
- Dans Flux, le sélecteur Tags reprend directement ces 18 libellés globaux et les cartes affichent les tags normalisés détectés à côté des clés de la source.
- Le score combine pertinence par tags normalisés (60 points), priorité P1/P2/P3 (25/12/0) et fraîcheur (15), puis tous les articles sont rescored à chaque collecte.
- Chroma dans `data/chroma/` est l’index dérivé du RAG.
- Nyx/Ollama est configuré sur `192.168.1.11:11434`.

Le backend est organisé en `feeds/`, `system/` et `rag/`. `backend/app.py` ne fait que construire l’application et enregistrer les blueprints. Le frontend sépare les vues, composants, types et appels HTTP.

La navigation principale est horizontale : Homepage, Flux, Assistants, Santé et Config. **Homepage** contient les quatre métriques de pilotage, les favoris durables et AI Summary. **Assistants** affiche le chatbot, l’état de livraison Telegram et une vue concise des cycles. **Config** possède les sous-onglets Sources et YAML ; le second édite `sources.yml`, `ai.yaml`, `prompt.yaml` et `telegram.yaml`, puis permet de vider SQLite ou Chroma après confirmation textuelle. Ne pas utiliser ces boutons comme mécanisme de maintenance ordinaire : SQLite contient les données de référence.

Les prompts LLM sont tous dans `config/prompt.yaml` : `assistant.system`, `retrieval.query_plan`, `summary.plan` et `summary.section`. Leur sauvegarde depuis Config vérifie les quatre gabarits et l’ensemble exact de leurs placeholders avant remplacement.

## Pipeline RAG

Après une collecte, `backend/rag/indexing.py` synchronise au plus 2 000 articles uniques dans Chroma. Les textes de 900 caractères ou plus passent dans `RecursiveCharacterTextSplitter` : chunks de 1 200 caractères, chevauchement de 180. Les métadonnées incluent source, catégorie, date, score, priorité et clés.

`backend/rag/retrieve.py` fait produire à ChatOllama une requête structurée et des filtres contrôlés, cherche les 24 chunks les plus proches dans Chroma, déduplique les articles dans l’ordre de similarité et en conserve 6. Aucun reranker n’est appelé. `backend/rag/agent.py` orchestre `retrieve → generate` dans un `StateGraph`. Le navigateur conserve un UUID de session ; `InMemorySaver` garde l’historique récent, perdu au redémarrage du processus.

`backend/rag/summary_agent.py` s’exécute après une synchronisation Chroma réussie. Son graphe `select → plan → draft_sections → compose → save` reprend au plus 40 P1 apparus depuis la dernière modification de `summary.md`, triés par date de publication décroissante (date de collecte en repli). Le seuil vient de `summary.top_n` dans `config/ai.yaml`. Le plan LLM utilise les SHA originaux, crée au plus cinq parties dont `Autres` si nécessaire, puis enrichit chaque partie avec le retrieval existant. L’écriture est atomique. En cas d’échec, le fichier précédent et la fenêtre de reprise restent inchangés.

Une sortie JSON invalide du planificateur Nyx déclenche automatiquement un regroupement de repli par catégorie au lieu d’abandonner la synthèse. Le champ `planning_mode` du résultat vaut alors `fallback`.

Le timer Atlas lance la pipeline `fetch → SQLite/scoring → embedding → synthèse → Telegram` à 10 h, 14 h et 18 h. Une panne Nyx ne perd pas les articles : `rag_index_state.pending` reste vrai dans SQLite et la prochaine collecte reprend l’indexation, puis la synthèse P1. Telegram n’est utilisé qu’ici. Une empreinte écrite après livraison complète empêche les doublons ; un échec conserve le rapport en attente pour le prochain cycle. L’état et la dernière erreur sont visibles dans **Santé** et via `GET /api/rag/index/status`.

**Santé** affiche également l’historique `collection_runs` : origine automatique/manuelle, état, volume et erreurs. Après cette mise à jour, recopier les unités systemd une fois pour transmettre `trigger=systemd`. Tant que `systemd/*.service` et `*.timer` ne changent plus, les rsync/build suivants ne nécessitent aucun `daemon-reload` ni redémarrage du timer.

Les sections Santé suivent l’ordre Services IA, Collectes automatisées, Santé des sources ; les flux en erreur apparaissent en premier et la fenêtre de table affiche cinq lignes avant défilement. Les textes d’aide redondants ont été retirés de Homepage, Flux et Assistants.

Les quatre cartes Santé affichent le temps écoulé depuis le dernier cycle en heures/minutes, la taille cumulée de `data/`, le nombre de signaux non dupliqués avec son sous-total P1, puis les sources saines et en erreur dans une carte commune.

L’assistant dispose d’un timeout proxy nginx de 210 secondes, légèrement supérieur au timeout d’inférence de 180 secondes. Son interface ne présente plus de statut `WIP`, d’étiquette `RAG` ni de bandeau de disponibilité ; les erreurs d’inférence apparaissent dans la zone de réponse.

## Commandes locales

```bash
docker compose up -d --build
curl --fail http://127.0.0.1:1207/api/health
docker compose logs -f api
```

```bash
PYENV_VERSION=nexus ruff check backend tests
PYENV_VERSION=nexus black --check backend tests
PYTHONPATH=backend PYENV_VERSION=nexus python -m unittest discover -s tests
npm --prefix web run lint
npm --prefix web run build
docker compose config --quiet
```

## Synchronisation et reconstruction sur Atlas

```bash
cd /home/vika/code/Projects/pantone/argos
rsync -az --delete \
  --exclude '.git' \
  --exclude 'web/node_modules' \
  --exclude 'web/dist' \
  --exclude 'data' \
  --exclude 'config/sources copy*.yml' \
  ./ vika@192.168.1.50:/home/vika/argos/

ssh vika@192.168.1.50
cd /home/vika/argos
docker compose config
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:1207/api/health
```

L’exclusion de `data` protège SQLite et Chroma malgré `--delete`. Le fichier `.env` de production contient les secrets et doit lui aussi rester hors synchronisation si un fichier local du même nom est créé.

## Prochaines priorités

1. Persister la mémoire LangGraph.
2. Évaluer le retrieval sur un jeu de questions et citations attendu.
3. Tester une recherche hybride BM25 + vecteurs et un cross-encoder dédié.
4. Renforcer la collecte contre les URL privées et formaliser les migrations SQLite.

Voir [`PROJECT.md`](PROJECT.md) pour le périmètre, [`EXPLANATIONS.md`](EXPLANATIONS.md) pour les détails et [`ROADMAP.md`](ROADMAP.md) pour le backlog.
