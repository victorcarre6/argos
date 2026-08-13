# Argos — Quick Catch

État de référence : 13/08/2026. Argos est servi sur Atlas à l’adresse `http://192.168.1.50:1207`. Le dépôt de développement est `/home/vika/code/Projects/pantone/argos`; le déploiement est `/home/vika/argos`.

## État actuel

- 126 sources actives, 8 catégories, 14 clés contrôlées et priorités P1/P2/P3.
- Les huit entrées Appels à projets et financements utilisent des RSS officiels validés avec le collecteur Argos : ANR, EIC, HaDEA, REA, Recherche et innovation de la Commission européenne, EuroHPC JU, UKRI et NSF.
- Ordre des catégories : agrégateurs, laboratoires/providers, frameworks/SDK, HPC, Ops/cloud, sécurité, financements, institutions.
- Dans **Flux**, la première ligne conserve catégorie, priorité P1/P2/P3, recherche textuelle et tri. La seconde ajoute une autocomplétion multi-source et un dropdown multi-tag. Les groupes sont cumulatifs ; les sources sélectionnées sont alternatives et tous les tags sélectionnés doivent être présents. Chaque choix devient une pilule verte supprimable.
- La hauteur des deux champs textuels de filtrage s’adapte au viewport avec `clamp(1.25rem, 4vh, 2.25rem)` sans dépasser leur taille historique.
- La source de chaque carte Flux est affichée dans une pilule teintée avec la couleur de sa catégorie.
- Les cartes affichent la date et l’heure de publication du flux, jamais l’heure d’importation comme valeur de remplacement.
- La croix d’une carte passe son champ SQLite `view` à faux : elle disparaît de Flux sans être supprimée ni retirée du RAG.
- L’étoile enregistre un bon candidat ; la croix enregistre un mauvais candidat. La table `signal_feedback` conserve durablement un instantané complet hors rétention et purge courante.
- Homepage affiche jusqu’à 30 favoris durables par récupération décroissante dans une carte haute de trois éléments, sans icône étoile décorative dans son en-tête. Flux possède un toggle étoile cumulable avec tous les autres filtres.
- Pendant une collecte, Flux affiche une progression pondérée de toute la pipeline : sources RSS, persistance/scoring, articles Chroma, plan et parties thématiques, puis sommaire Telegram. Le libellé courant et le compteur local sont actualisés chaque seconde.
- Les quatre métriques de pilotage quotidien sont le total des signaux, les nouveaux signaux de la dernière collecte, les signaux P1 de la fenêtre courante et le bilan de la dernière collecte.
- Conteneur web `argos` : React/Vite compilé, nginx interne `8080`, port LAN `1207`.
- Conteneur backend `argos-api` : Flask interne `8000`, limite mémoire `700m`.
- SQLite est la source de vérité des articles et des états de flux.
- La fenêtre d’ingestion RSS et la rétention SQLite sont pilotées par `collection.max_age_days` et `storage.retention_days` dans le YAML.
- Une taxonomie globale de 19 tags en `snake_case` ASCII remplace les mots-clés propres aux catégories. Les `keys` de source deviennent des tags parents, complétés par les tags explicites, la règle `releases` et les alias détectés dans le contenu.
- Dans Flux, le sélecteur Tags reprend directement ces 19 libellés globaux et les cartes affichent un seul ensemble de tags verts normalisés.
- Le score combine pertinence par tags normalisés (60 points), priorité P1/P2/P3 (25/12/0) et fraîcheur (15), puis tous les articles sont rescored à chaque collecte.
- Chroma dans `data/chroma/` est l’index dérivé du RAG.
- Nyx/Ollama est configuré sur `192.168.1.11:11434`.

Le backend est organisé en `feeds/`, `system/` et `rag/`. `backend/app.py` ne fait que construire l’application et enregistrer les blueprints. Le frontend sépare les vues, composants, types et appels HTTP.

La navigation principale est horizontale : Homepage, Flux, Assistants, Data Analysis, Santé et Config. Dans l’en-tête, le bouton maison gris placé à droite de l’icône Argos ouvre l’accueil Atlas sur `http://192.168.1.50:3141`. **Homepage** contient les quatre métriques de pilotage, les favoris durables en cartes compactes et le dernier rapport, téléchargeable avec son nom daté depuis le bouton aligné sur son titre. **Data Analysis** parcourt les instantanés durables favoris et masqués. Ses cartes supérieures donnent leurs volumes et la part évaluée par rapport aux signaux actuels ; ses graphiques comparent taux d’acceptation par tag, source et priorité ainsi que les distributions de scores. Une heatmap ApexCharts pleine largeur croise ensuite catégories et tags, avec une barre de dégradé continue verticale de 0 à 100 % à droite, des cellules sans décision neutralisées et un thème sombre cohérent avec Argos. **Assistants** affiche le chat RAG, l’état Telegram et une vue concise des cycles. **Config** édite les configurations opérationnelles et permet de vider SQLite ou Chroma après confirmation textuelle.

Dans **Flux**, cliquer sur la catégorie, la source ou l’un des tags d’une carte ajoute la valeur à la multisélection correspondante sans retirer les sélections existantes. Les cartes affichent un seul ensemble de tags verts cliquables ; les clés techniques des sources restent dans les données et le RAG mais ne sont plus dupliquées visuellement.

Sous les filtres, jusqu’à cinq pilules vertes chargent des vues persistantes définies dans `config/views.yaml`. Catégories, priorités, sources et tags acceptent plusieurs valeurs en union. `+ New` demande un nom et capture recherche, tri, filtres, favoris et densité courants ; les noms vides ou dupliqués et le sixième raccourci sont refusés. Le preset initial `Favoris` cible Aggrégateurs et Laboratoires/providers, P1/P2 et les sept tags techniques demandés.

Le bouton gris `Reset`, placé à gauche de `Compact/Confort`, restaure la vue de base sans filtre ni recherche, triée par publication récente, en mode confort et sans supprimer les raccourcis persistants.

Chaque source transmet désormais à ses articles un socle de tags dérivé de ses `keys` (`LLM → llm`, `IA Agentique → agents`, `Ops → deploiement`, etc.). Ces tags hérités sont fusionnés avec ceux détectés dans le titre et le résumé, ce qui garantit au moins un tag par signal sans dupliquer la taxonomie sur les 126 sources. Un champ `tags` explicite peut compléter une source. Le tag `releases` est en plus imposé aux sources dont le nom contient `Releases`; le rescoring de chaque collecte corrige aussi les articles déjà stockés.

Les prompts LLM sont tous dans `config/prompt.yaml` : `assistant.system`, `retrieval.query_plan`, `summary.plan` et `summary.section`. Leur sauvegarde depuis Config vérifie les quatre gabarits et l’ensemble exact de leurs placeholders avant remplacement.

## Pipeline RAG

Après une collecte, `backend/rag/indexing.py` synchronise au plus 2 000 articles uniques dans Chroma. Les textes de 400 caractères ou plus passent dans `RecursiveCharacterTextSplitter` : chunks de 800 caractères, chevauchement de 180. Les métadonnées incluent source, catégorie, date, score, priorité et clés.

`backend/rag/retrieve.py` fait produire à ChatOllama une requête structurée et des filtres contrôlés, cherche les candidats dans Chroma, puis déduplique les articles dans l’ordre de similarité. Aucun reranker n’est appelé. Le rapport utilise `rag.candidate_k`, `rag.final_k` et `rag.query_model` dans `ai.yaml`. `backend/rag/agent.py` orchestre `retrieve → generate` dans un `StateGraph` et sélectionne à la place les paramètres indépendants `assistant.rag`, dont sa limite de messages de session. Les deux profils interrogent le même index Chroma. Le navigateur conserve un UUID de session et la chronologie affichée ; `InMemorySaver` garde l’historique récent côté backend, perdu au redémarrage du processus.

`backend/rag/summary_agent.py` s’exécute après une synchronisation Chroma réussie. Son graphe `select → plan → draft_sections → compose → save` reprend au plus `summary.top_n` P1 apparus depuis la modification du dernier rapport. Le plan structuré crée jusqu’à quatre axes plus `5. Autre`; chaque partie non vide possède son retrieval et sa rédaction. Le Markdown fusionné, le sommaire et les TXT thématiques sont archivés atomiquement en heure `Europe/Paris`. `data/summary.md` reste la copie compatible ; `/api/summary` interdit le cache HTTP. Un échec conserve rapport et fenêtre de reprise précédents.

Le timer Atlas lance `fetch → SQLite/scoring → embedding → plan → parties → Telegram` à 10 h, 14 h et 18 h. Nyx crée de un à quatre axes principaux ; tous les signaux non affectés vont dans `5. Autre`. Les TXT thématiques datés sont fusionnés dans le rapport Markdown principal. Telegram reçoit seulement un sommaire court issu du plan. Sa conclusion choisit par `randint` une entrée du fichier optionnel `sentences.yaml`, puis affiche toujours l’instruction fixe pour répondre par numéro ou utiliser `/download`. Sans phrase exploitable, cette instruction apparaît seule. Chaque destinataire autorisé peut répondre plusieurs fois par `1` à `5`; `/help` explique le fonctionnement et chaque commande vise automatiquement le dernier rapport.

Le comportement mono- et multi-destinataires est couvert par [`tests/test_telegram.py`](../tests/test_telegram.py).

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
  --exclude '.git/' \
  --exclude '.env' \
  --exclude 'web/node_modules/' \
  --exclude 'web/dist/' \
  --exclude 'data/' \
  --exclude 'config/sources copy*.yml' \
  ./ vika@192.168.1.50:/home/vika/argos/

ssh vika@192.168.1.50
cd /home/vika/argos
docker compose config
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:1207/api/health
```

Les exclusions de `data/` et `.env` protègent SQLite, Chroma, les rapports et les secrets de production malgré `--delete`.

## Prochaines priorités

1. Persister la mémoire LangGraph.
2. Évaluer le retrieval sur un jeu de questions et citations attendu.
3. Tester une recherche hybride BM25 + vecteurs et un cross-encoder dédié.
4. Renforcer la collecte contre les URL privées et formaliser les migrations SQLite.

Voir [`PROJECT.md`](PROJECT.md) pour le périmètre, [`EXPLANATIONS.md`](EXPLANATIONS.md) pour les détails et [`ROADMAP.md`](ROADMAP.md) pour le backlog.
