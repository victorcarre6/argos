# Argos — Périmètre et objectifs

## Finalité

Argos est une plateforme de veille technique auto-hébergée pour l’IA générative, les agents, le RAG, le deep learning, l’Ops, le cloud, la cybersécurité IA et le HPC. Elle couvre la chaîne allant du catalogue RSS/Atom à la lecture, l’analyse sémantique et l’interrogation assistée par un modèle local.

Le service vise un usage sur le LAN. Il doit rester léger sur Atlas, conserver ses données indépendamment des conteneurs et déléguer les calculs de modèles à Ollama sur Nyx.

## Usages couverts

- administrer un catalogue structuré de sources ;
- collecter, parser, normaliser et dédupliquer les articles ;
- rechercher, filtrer et lire le flux ;
- surveiller les erreurs, codes HTTP et latences par source ;
- interroger le corpus avec des filtres et des citations ;
- planifier la collecte et envoyer des alertes optionnelles.

## Architecture de référence

```text
Navigateur du LAN
  http://192.168.1.50:1207
          │
          ▼
Atlas — `argos`
React/Vite + nginx :8080
          │ /api vers api:8000
          ▼
Atlas — `argos-api`
Flask :8000, non exposé directement
  ├── Internet : RSS/Atom et Telegram
  ├── /app/config : YAML montés depuis l’hôte
  ├── /app/data/monitoring.db : SQLite
  ├── /app/data/chroma : index RAG Chroma
  └── Nyx/Ollama : 192.168.1.11:11434
```

`backend/app.py` construit Flask et enregistre les blueprints. Les domaines sont :

- `backend/feeds/` : articles, collecte, parsing, déduplication et SQLite ;
- `backend/system/` : chargement de configuration, état partagé et santé ;
- `backend/rag/` : index Chroma, retrieval, agent et routes.

SQLite est la source de vérité des articles. Chroma est un index dérivé, reconstructible à partir de SQLite et de `config/sources.yml`.

## Catalogue de sources

`config/sources.yml` contient actuellement 134 sources réparties en 8 catégories. Leur ordre canonique est : **Aggrégateurs**, **Laboratoires et providers**, **Frameworks et SDK**, **HPC**, **Ops, Cloud et plateformes**, **Sécurité, guardrails et évaluation**, **Appels à projets et financements**, puis **Institutions publiques et politiques**.

Chaque source définit :

- `name` et `url` ;
- `keys`, choisies dans 14 valeurs contrôlées : recherche, LLM, IA Agentique, Orchestration, RAG, Cloud, HPC, Deep Learning, Ops, Monitoring, Politique, Newsletter, Cybersécurité et Appels à projets ;
- `priorité`, entier de 1 à 3 ;
- facultativement `enabled: false` et `max_items`.

Le sous-onglet Sources de Config permet de replier les catégories et de modifier ces champs. Dans Flux, P1 reçoit un contour rouge léger, P2 un contour vert léger et P3 reste neutre. Les clés apparaissent sous chaque source dans l’éditeur et sous forme de pilules vertes sur les cartes ; les tags `snake_case` détectés sont affichés séparément. La recherche combine catégorie, priorité, texte, sources, tags et favoris. Plusieurs sources forment une alternative ; plusieurs tags doivent tous être présents, sans exclure les articles possédant des tags supplémentaires.

La navigation principale est horizontale, dans l’ordre Homepage, Flux, Assistants, Santé et Config. Homepage regroupe les quatre métriques de pilotage, une carte défilante des 30 derniers favoris durables triés par récupération et le rendu Markdown du dernier rapport daté de `data/reports/`. Assistants regroupe le chatbot RAG, une synthèse du bot Telegram sans exposer ses secrets et une description concise des cycles automatiques. Config contient deux sous-onglets horizontaux : Sources pour l’éditeur structuré, puis YAML pour les quatre fichiers bruts et les purges de stockage. Les YAML sont validés avant remplacement atomique. Chaque suppression demande de saisir le nom du magasin et l’API la refuse pendant une collecte.

## Collecte, parsing et stockage

`POST /api/refresh` démarre une collecte asynchrone ; `GET /api/refresh` expose son état. Jusqu’à six sources sont récupérées en parallèle, avec un timeout de 20 secondes. Un échec est enregistré sans interrompre les autres flux.

`collection.max_age_days` dans `config/sources.yml` limite l’âge des entrées ingérées. Le filtre est appliqué avant `max_items`, afin que la limite porte sur les articles récents réellement retenus. Une entrée sans date reste acceptée : son ancienneté ne peut pas être déterminée de manière fiable.

`feedparser` traite RSS et Atom. Pour chaque entrée, Argos exige titre et URL, nettoie le HTML du résumé, normalise les espaces, limite les longueurs, convertit la meilleure date disponible en UTC, associe catégorie et source, puis détecte les tags depuis une taxonomie globale de 18 concepts en `snake_case` ASCII. Chaque tag possède plusieurs alias non affichés ; par exemple `agentic` et `multi-agent` deviennent tous deux `agents`. La détection respecte les limites de mots et calcule ensuite un score heuristique sur 100 :

- pertinence : `min(60, 10 + 10 × tags normalisés trouvés)` ;
- priorité : 25 points pour P1, 12 pour P2, 0 pour P3 ;
- fraîcheur : jusqu’à 15 points, avec décroissance exponentielle et demi-vie égale à `collection.max_age_days / 2`.

La date d’importation remplace la date de publication lorsqu’elle manque. Tous les articles SQLite sont rescored après chaque collecte afin que fraîcheur, priorité, taxonomie et catégorie courante soient répercutées. Le score exprime une priorité de veille, pas la fiabilité factuelle de l’article.

L’URL normalisée perd fragments et paramètres de tracking. Son SHA-256 devient l’identifiant stable. Une comparaison titre/résumé avec les 500 articles uniques récents détecte aussi les syndications proches ; les doublons restent traçables mais sont masqués par défaut.

Après la collecte, Argos met à jour la santé des sources, applique `storage.retention_days`, synchronise Chroma, génère la synthèse P1, la condense pour Telegram puis livre ce résumé. Telegram n’est utilisé dans aucun autre flux. SQLite se trouve dans `data/monitoring.db` sur l’hôte.

Flux expose la progression pondérée de toute la pipeline : fetch 0–45 %, stockage et scoring 45–55 %, embedding 55–75 %, synthèse 75–92 %, summarizer 92–97 % et Telegram 97–100 %. Le détail avance respectivement par source, opération de stockage, article indexé, partie rédigée, condensation puis message envoyé.

La synchronisation Chroma possède un état persistant dans SQLite. Avant chaque tentative, l’index est marqué en attente. Une panne de Nyx est enregistrée sans invalider la collecte RSS ; le prochain déclenchement manuel ou systemd reprend l’indexation incrémentale et ne marque l’index à jour qu’après un passage complet.

Après une indexation réussie, l’agent de synthèse sélectionne au plus 40 articles P1 apparus depuis la date de modification du dernier rapport, classés de la publication la plus récente à la plus ancienne. La date de collecte sert de repli lorsqu’une date de publication manque. Nyx reçoit leurs identifiants SHA-256 et construit cinq parties au maximum ; `Autres` absorbe les signaux que le plan ne classe pas. Chaque partie utilise ensuite le retrieval Chroma pour rapprocher les nouveaux P1 des signaux antérieurs pertinents. Le document complet, dont le titre contient la date UTC, est archivé atomiquement sous `data/reports/report_YYMMDD_HHMM.md`; `data/summary.md` reste une copie de compatibilité. Homepage résout toujours le dernier nom daté, avec repli sur l’ancien `summary.md` avant la première archive. Si Nyx ou la génération échoue, l’ancien fichier reste intact et les P1 sont repris lors de la prochaine collecte.

Le graphe sans mémoire `summarizer` charge ensuite le dernier rapport complet, demande à Nyx un condensé factuel et sauvegarde `data/reports/telegram_YYMMDD_HHMM.txt`. Le texte commence par `Rapport DD-MM HH:MM`, utilise des paragraphes séparés par une ligne vide et exclut Markdown, URL et références. Sa taille est validée contre `telegram.max_message_chars`; un dépassement bloque la livraison au lieu de tronquer ou découper le texte. Telegram envoie cet artefact en un seul message. Un artefact existant est réutilisé lors d’une reprise afin de ne pas rappeler le modèle.

## RAG, embedding et retrieval

`backend/rag/indexing.py` synchronise au plus 2 000 articles uniques dans la collection Chroma `argos_articles`. Le fingerprint du contenu, le hash des métadonnées et une version d’index permettent de ne réindexer que ce qui change et de supprimer les chunks devenus obsolètes.

Les textes d’au moins 900 caractères sont découpés par le `RecursiveCharacterTextSplitter` des intégrations LangChain : blocs de 1 200 caractères, chevauchement de 180, priorité aux paragraphes, lignes et phrases. Les chunks portent l’identifiant, le titre, l’URL, la source, la catégorie, les dates, le score, la priorité et les 14 indicateurs de clés. `OllamaEmbeddings` envoie leur texte à Nyx ; Chroma utilise un index HNSW cosine persistant.

Pour chaque question :

1. ChatOllama produit un plan structuré séparant requête sémantique et filtres explicites ;
2. les valeurs de catégories, sources, clés, priorités, dates et score sont validées contre le catalogue ;
3. Chroma retourne jusqu’à 24 chunks dans l’ordre de similarité ;
4. Argos déduplique les articles et garde jusqu’à 6 sources ;
5. le modèle `qwen3.6:27b` répond uniquement à partir du contexte et cite `[1]`, `[2]`, etc.

L’assistant conversationnel utilise `START → retrieve → generate → END`. Un UUID stable du navigateur sert de `thread_id`; `InMemorySaver` conserve au plus 12 messages récents utilisés par la génération. `DELETE /api/assistant/session/<session_id>` efface une session. Cette mémoire disparaît à chaque redémarrage du backend.

L’agent de synthèse utilise un second graphe sans mémoire : `select → plan → draft_sections → compose → save`. `plan` produit une sortie Pydantic structurée ; le code valide les identifiants, déduplique les affectations et crée `Autres` si nécessaire. `draft_sections` effectue un retrieval et une génération par partie. `compose` assemble le Markdown sans nouvel appel de modèle et `save` utilise un fichier temporaire suivi d’un remplacement atomique.

La logique RAG reste répartie explicitement entre `indexing.py`, `retrieve.py`, `agent.py`, `summary_agent.py` et `summarizer.py` ; les routes importent directement le domaine concerné. `rag/prompts.py` charge et interpole les cinq gabarits LLM depuis `config/prompt.yaml`, sans prompt métier inline dans le code.

## Déploiement et ports

Compose construit `./backend` et `./web`. Le service `web` publie `1207:8080`; le service `api` reste accessible uniquement sur le réseau Compose. Les limites mémoire sont 150 Mo pour le web et 700 Mo pour l’API. `./config` et `./data` sont montés dans le backend.

La synchronisation de développement vers Atlas doit exclure `.git`, `web/node_modules`, `web/dist`, `data` et les copies locales de `sources.yml`. La procédure canonique se trouve dans [`QUICK_CATCH.md`](QUICK_CATCH.md).

## Contraintes et hors périmètre

- Pas de dépendance à un service cloud pour l’IA ; Nyx doit rester substituable par configuration.
- Pas d’exposition Internet ni d’authentification applicative dans le périmètre actuel.
- Pas de service Chroma séparé : l’index est embarqué et persistant sur disque.
- Pas encore de retrieval hybride, de reranker cross-encoder ni de mémoire de conversation durable.
- Collecte et synchronisation RAG sont asynchrones ; l’état doit rester observable par API.

## Critères de succès

- Le catalogue se charge, se modifie et conserve clés, priorités et ordre logique.
- Les métriques de sources sont calculées depuis le catalogue : sources actives et sources déjà collectées restent distinguées.
- Une source défaillante n’empêche pas les autres d’être collectées.
- Une URL connue est mise à jour sans duplication et les syndications sont identifiées.
- Les données SQLite et Chroma survivent à une reconstruction des conteneurs.
- Le RAG applique les filtres autorisés, cite les articles retrouvés et isole les sessions.
- Après une synthèse réussie, le summarizer produit un condensé sans Markdown que Telegram livre en un seul message, avec reprise en attente en cas d’échec.
- Homepage restitue jusqu’à 30 favoris durables et Santé calcule cycle, stockage, volumes de signaux et sources sans constante métier dans le frontend.
- L’interface reste accessible sur Atlas au port `1207` sous les limites mémoire prévues.

## Configuration de référence

| Fichier | Responsabilité |
|---|---|
| `config/sources.yml` | Catalogue, clés, priorités, taxonomie globale des tags et rétention |
| `config/ai.yaml` | Ollama, modèles, Chroma, chunking, retrieval et sessions |
| `config/prompt.yaml` | Prompts et variables du chatbot, self-query, synthèse et summarizer |
| `config/telegram.yaml` | Activation, destination et taille du résumé Telegram |
| `docker-compose.yml` | Images, volumes, ports, secrets injectés et mémoire |
| `systemd/argos-collect.*` | Déclenchement à 10 h, 14 h et 18 h |
