# Argos — Explications techniques

Ce document décrit l’implémentation actuelle. Le périmètre fonctionnel est fixé dans [`PROJECT.md`](PROJECT.md), tandis que [`ELN.md`](ELN.md) conserve l’historique des décisions.

## 1. Séparation des responsabilités

Le backend n’est pas organisé selon les couches techniques génériques, mais selon trois domaines cohérents :

```text
backend/app.py
├── feeds/       collecte, parsing, articles, SQLite
├── system/      configuration, état des tâches, santé
└── rag/         indexation Chroma, retrieval, agent
```

`app.py` reste volontairement minimal. Ce découpage évite qu’une modification du RAG touche la collecte, tout en gardant ensemble les articles, leur acquisition et leur stockage. Les blueprints conservent les routes `/api/*`; le renommage historique de `api/` vers `backend/` n’a donc pas changé le contrat du frontend ni le proxy nginx.

Le frontend suit la même logique : `views/` contient les écrans, `components/` les éléments réutilisables, `lib/api.ts` les appels HTTP, `lib/format.ts` les fonctions de présentation/recherche et `types.ts` les contrats partagés. Le shell affiche une navigation principale horizontale en pilules. La vue Config imbrique la même barre réutilisable pour séparer l’éditeur Sources des YAML et opérations de stockage.

Dans Flux, `components/filters.tsx` encapsule les deux filtres multisélection. L’autocomplétion Source ne propose que les sources présentes dans les articles chargés ; le dropdown Tag dérive ses options de `article.tags`. Les filtres de dimensions différentes s’additionnent. Une sélection de plusieurs sources utilise une union, tandis qu’une sélection de plusieurs tags utilise une inclusion de l’ensemble demandé : un article peut conserver d’autres tags.

## 2. Configuration des sources

Le YAML est la source de vérité du catalogue. Une catégorie porte un nom, une couleur et une liste de sources. Une source possède un nom, une URL, une priorité et des clés ; elle peut être désactivée ou limiter son nombre d’entrées.

La section racine `tags` définit une taxonomie globale de 19 identifiants `snake_case` ASCII et leurs alias. Les `keys` restent la classification éditoriale de la source, mais sont traduites en tags parents hérités par ses articles. Les tags explicites, la règle `releases` et la détection textuelle complètent ce socle. La correspondance est insensible à la casse, respecte les limites de mots et déduplique les concepts.

Le vocabulaire contrôlé comporte 14 clés : `recherche`, `LLM`, `IA Agentique`, `Orchestration`, `RAG`, `Cloud`, `HPC`, `Deep Learning`, `Ops`, `Monitoring`, `Politique`, `Newsletter`, `Cybersécurité` et `Appels à projets`. La validation empêche les fautes de frappe de devenir des filtres invisibles. La priorité vaut 1, 2 ou 3 : P1 est accentuée en rouge, P2 en vert et P3 reste neutre.

Les clés et priorités sont résolues depuis le YAML lors de la lecture des articles. Une modification profite donc aussi aux articles existants sans migration SQLite.

Les 126 sources actives sont organisées en 8 catégories après fusion des familles qui se recouvraient. Le compteur principal utilise le nombre de sources actives calculé depuis ce catalogue ; le nombre de sources distinctes présentes dans SQLite est renvoyé séparément comme `collected_sources`.

La famille Appels à projets et financements n’utilise plus de pages HTML ni les anciens endpoints Drupal `node/1`. Ses huit entrées pointent vers des RSS officiels : le flux AAP dédié de l’ANR, les actualités EIC, HaDEA, REA, Recherche et innovation et EuroHPC, les opportunités UKRI et les annonces de financement NSF. Chaque URL a été exécutée par `feeds.collection.fetch_source` : elles répondent toutes en HTTP 200, sont parsées sans erreur et fournissent 15 à 20 entrées sur une fenêtre historique de validation. La fenêtre opérationnelle de sept jours peut légitimement produire zéro article lorsqu’un organisme n’a rien publié récemment sans rendre la source défaillante.

## 3. Cycle d’une collecte

`POST /api/refresh` acquiert un verrou d’état, démarre un thread et répond sans attendre la fin. Les sources actives sont traitées dans un pool de six workers. Pour chaque réponse, `feedparser` uniformise RSS et Atom ; Argos nettoie le HTML, choisit une date, associe la catégorie et calcule un score à partir des tags normalisés, de la priorité et de la fraîcheur.

Le score additionne une pertinence plafonnée à 60 (`10 + 10` par tag normalisé), un bonus de priorité P1/P2/P3 de 25/12/0 et une fraîcheur plafonnée à 15. Cette dernière suit `15 × exp(-ln(2) × âge / demi-vie)`, avec une demi-vie égale à la moitié de la fenêtre d’ingestion configurée. Après persistance et purge, `_refresh_scores` relit tous les articles et actualise score, tags et catégorie depuis le YAML.

Avant la normalisation complète, `collection.max_age_days` écarte les entrées trop anciennes. Les entrées sont parcourues jusqu’à obtenir `max_items` articles récents ; un flux contenant de nombreuses archives en tête ne réduit donc pas artificiellement le résultat. Les entrées sans date sont conservées et utilisent ensuite leur date de collecte pour la rétention.

Deux mécanismes limitent les doublons :

1. l’URL canonique retire fragments, slash superflu et paramètres de tracking avant calcul d’un SHA-256 stable ;
2. la similarité pondérée du titre et du résumé rapproche les mêmes dépêches publiées sous plusieurs URL.

La base est mise à jour par article. Une panne isolée est enregistrée dans la santé de la source et ne provoque pas de rollback global. En fin de tâche, Argos applique strictement la pipeline `fetch → SQLite/scoring → embedding Chroma → plan et rapports thématiques → Telegram`. Un échec d’indexation arrête les étapes LLM et Telegram du cycle, sans perdre les articles déjà persistés.

Le tagging fusionne deux niveaux. Les `keys` stables de chaque source sont traduites en tags parents contrôlés et héritées par tous ses articles ; un éventuel champ `tags` explicite complète cette base. `_score` ajoute ensuite les tags dont les alias apparaissent dans le titre ou le résumé. Chaque signal reçoit ainsi au moins le contexte de sa source, tout en conservant les précisions propres à son contenu. Le rescoring global réapplique cette fusion aux articles existants après chaque collecte.

La progression publique couvre toute cette pipeline avec des plages pondérées : fetch 0–45 %, persistance et scoring 45–55 %, embedding 55–75 %, synthèse thématique 75–97 %, Telegram 97–100 %. Le fetch avance source par source, l’indexation article par article, puis la synthèse à la sélection, au plan, pour chaque partie, à l’assemblage et à la sauvegarde. Le frontend interroge uniquement `/api/refresh` chaque seconde pendant une exécution afin de rendre cette granularité sans recharger toutes les autres données.

La table singleton `rag_index_state` conserve `pending`, la dernière tentative, le dernier succès et la dernière erreur. `pending` passe à vrai avant l’appel d’embedding et reste vrai si Nyx échoue. Comme les chunks Chroma portent les fingerprints du contenu et des métadonnées, la tentative suivante saute ce qui est déjà correct et reprend le travail restant. L’échec est visible dans le bilan et l’onglet Santé, mais les articles RSS restent disponibles.

La table `collection_runs` conserve en parallèle les exécutions récentes : origine `systemd` ou manuelle, horodatages, état, bilan JSON et erreur fatale. Cette télémétrie métier remplace dans l’interface la lecture directe de `journalctl` ou du socket Docker, qui donnerait au conteneur des permissions excessives sur Atlas.

## 4. Persistance

SQLite (`data/monitoring.db`) conserve les articles, l’état des sources et les fingerprints. Il constitue la source de vérité sauvegardable.

`signal_feedback` constitue un jeu d’apprentissage éditorial séparé. L’étoile enregistre `candidate=good`; la croix enregistre `candidate=bad` avant de masquer l’article. Chaque ligne conserve un snapshot JSON des métadonnées et du contenu au moment du choix. Cette table n’est visée ni par la rétention temporelle ni par la purge des données courantes, afin de préserver les exemples pour une future calibration du scoring.

Data Analysis exploite directement ces snapshots. Elle rapporte favoris, masqués et ratio entre décisions durables et signaux actuels. Les taux d’acceptation `good / (good + bad)` sont calculés par tag, source et priorité ; un histogramme compare les scores par tranches de dix points. La heatmap ApexCharts catégories × tags utilise une échelle sombre du rouge au vert. Sa légende native par intervalles est masquée au profit d’une barre de dégradé continue verticale, bornée uniquement par 0 et 100 %, tandis que les cellules sans décision restent grises. La vue est chargée dynamiquement pour isoler le moteur graphique du bundle principal. Le corpus survivant à la rétention, la part évaluée peut dépasser 100 %.

`GET /api/articles/favorites` relit ces snapshots durables, les trie par `collected_at` décroissant et limite la réponse à 30 éléments. Homepage les affiche sous forme de cartes compactes dans une zone défilante, y compris si l’article courant a ensuite été purgé. Dans Flux, le toggle étoile de la seconde ligne ajoute `candidate=good` aux autres critères actifs. Utiliser la croix requalifie volontairement un favori en mauvais candidat et le retire donc de cette liste.

La rétention SQLite est indépendante de la fenêtre d’ingestion : la première empêche l’ajout d’archives RSS trop anciennes, tandis que `storage.retention_days` supprime automatiquement les données stockées devenues anciennes après chaque collecte.

Chroma (`data/chroma/`) conserve uniquement les chunks destinés au RAG. C’est un index dérivé : il peut être reconstruit depuis SQLite, mais il doit normalement être sauvegardé avec le reste de `data/` pour éviter une réindexation coûteuse. Les deux chemins sont montés sous `/app/data` dans le conteneur.

Une reconstruction Docker ne supprime pas les données. Une synchronisation `rsync --delete` doit impérativement exclure `data`.

## 5. Indexation RAG

`rag/indexing.py` lit jusqu’à 2 000 articles non dupliqués. Pour chaque article, il calcule deux signatures : une pour le contenu et une pour les métadonnées. Si elles correspondent à l’entrée Chroma et à la version d’index, aucun embedding n’est recalculé.

Le texte associe titre et résumé. En dessous de 400 caractères, il reste entier. Sinon, `RecursiveCharacterTextSplitter` produit des blocs de 800 caractères avec 180 caractères de recouvrement. Les séparateurs privilégient paragraphes, lignes, fins de phrase puis espaces. Ce choix est adapté aux résumés RSS : déterministe, peu coûteux et indépendant d’un second appel sémantique.

Chaque chunk contient des métadonnées filtrables : article, source, catégorie, horodatage, score, priorité et booléens pour chacune des 14 clés. `OllamaEmbeddings` utilise `nomic-embed-text-v2-moe:latest` sur Nyx et Chroma stocke les vecteurs dans une collection HNSW cosine.

Quand le rescoring ne change que les métadonnées, l’indexeur met à jour directement les métadonnées Chroma des chunks existants. L’embedding n’est recalculé que lorsque le contenu ou la version de découpage change.

## 6. Retrieval

`rag/retrieve.py` demande d’abord à ChatOllama un objet `QueryPlan`. Le modèle peut extraire une requête libre ainsi que des catégories, sources, clés, priorités, bornes de date et score minimal. Toutes les listes sont ensuite recoupées avec le catalogue ; une valeur inventée est rejetée. Si la planification échoue, la question brute reste utilisable sans filtre.

Le même index Chroma sert deux profils de retrieval. La rédaction du rapport utilise `rag.candidate_k`, `rag.final_k` et `rag.query_model`. Le chatbot passe explicitement le profil `assistant` et remplace ces trois valeurs par celles de `assistant.rag`. Les valeurs de référence actuelles sont respectivement 10 candidats, 4 articles finaux et `qwen3.6:35b-a3b` pour les deux profils, mais elles peuvent désormais évoluer indépendamment. Les candidats sont consommés directement dans l’ordre de similarité, sans second appel de reranking, et un seul chunk par article est retenu.

Le reste de `rag` décrit l’infrastructure commune : chemin Chroma, volume maximal indexé et découpage des documents. Un ancien `ai.yaml` sans `assistant.rag` reste valide ; le loader hérite alors de `candidate_k`, `final_k` et `query_model` depuis `rag`, avec 12 messages de session par défaut.

## 7. Agent LangGraph et sessions

L’agent est un graphe minimal :

```text
START → retrieve → generate → END
```

Le nœud `retrieve` construit le contexte courant. Le nœud `generate` ajoute une instruction système imposant le français, l’usage exclusif du contexte et les citations numérotées, puis appelle `qwen3.6:27b` avec les messages récents.

Le frontend crée un UUID stable dans `localStorage` et l’envoie comme `session_id`. LangGraph utilise cet identifiant comme `thread_id`; `InMemorySaver` sépare les conversations et `assistant.rag.session_message_limit` borne les messages relus par la génération. L’interface inspirée de NEXUS affiche chaque question et réponse dans une chronologie en bulles de 42 rem de haut, garde la saisie au bas du panneau et défile vers le dernier tour. La chronologie visible est aussi enregistrée dans `localStorage`, ce qui évite sa disparition lorsque React démonte la vue pendant un changement d’onglet. Cette copie ne remplace pas le checkpoint : Nouvelle conversation appelle `DELETE /api/assistant/session/<session_id>`, efface l’affichage et renouvelle l’UUID. Les checkpoints ne survivent pas au redémarrage : une persistance durable reste au backlog.

## 8. Agent de synthèse P1

Après `sync_index()`, `rag/summary_agent.py` exécute un second `StateGraph` :

```text
START → select → plan → draft_sections → compose → save → END
                 └──── aucun nouveau P1 ──────────────→ END
```

`select` croise les sources P1 actives du YAML avec les articles visibles, uniques et apparus après la date de modification du dernier rapport archivé. Les archives valides suivent `data/reports/report_YYMMDD_HHMM.md` en heure `Europe/Paris` et sont ordonnées par leur nom ISO compact. Avant la première archive, `data/summary.md` fournit le seuil historique ; en l’absence de tout document, la fenêtre initiale reprend `collection.max_age_days`. Le seuil emploie le `mtime` précis du fichier sélectionné plutôt que la minute tronquée dans son nom. Une erreur avant `save` laisse ainsi la borne intacte et les mêmes P1 sont repris au prochain passage.

`select` classe les candidats par `published_at` décroissant, avec `collected_at` comme date de repli, puis conserve les `summary.top_n` premiers. `plan` demande une sortie structurée comportant jusqu’à quatre axes, leur titre, leur aperçu Telegram et leurs identifiants. La normalisation supprime les doublons, renumérote les axes sans trou et place tous les signaux restants dans `5. Autre`; un regroupement par catégorie prend le relais si Nyx ne fournit pas de JSON valide. `draft_sections` effectue ensuite un retrieval et une rédaction propres à chaque partie non vide.

Le prompt distingue les références `NOUVEAU` des références `CONTEXTE`, exige une discussion de chaque P1 et des citations numérotées. Une liste Markdown déterministe associe ensuite chaque numéro à son titre, son URL, sa source et son rôle. `compose` date le titre en heure de Paris. `save` remplace atomiquement l’archive datée, puis `data/summary.md`, conservé comme copie de compatibilité. Pour interpréter correctement les anciennes archives nommées en UTC, le résolveur lit en priorité l’horodatage ISO inclus dans leur contenu et le convertit en heure de Paris. Lors de l’initialisation SQLite, les anciens articles sans `first_seen_at` sont backfillés depuis `collected_at` afin qu’un simple refetch ne les fasse pas passer pour de nouveaux signaux.

`compose` fusionne les parties dans le rapport Markdown principal et fabrique sans nouvel appel LLM un sommaire borné à partir des aperçus du plan. `save` écrit atomiquement le rapport, `telegram_YYMMDD_HHMM.txt` et les fichiers `telegram_YYMMDD_HHMM_part_N.txt`. Le numéro 5 existe toujours, avec un constat explicite si aucun signal secondaire n’est présent.

`system/telegram.py` envoie le sommaire à chaque entrée nommée de `telegram.chat_ids`, puis une boucle de long polling traite `/start`, `/help`, `/download` et les chiffres. Seules les conversations configurées sont autorisées. Le fichier d’offset avance après une réponse réussie ; une erreur réseau provoque donc une nouvelle tentative. Les rapports longs sont découpés par paragraphes et une nouvelle collecte remplace automatiquement la cible par ses artefacts les plus récents.

## 9. Configuration des prompts

`config/prompt.yaml` centralise les instructions auparavant dispersées dans les modules Python : système du chatbot, planification du self-query, plan thématique et rédaction des parties. `rag/prompts.py` recharge le YAML à chaque appel, sélectionne le gabarit et applique `str.format` avec les seules données préparées par le code.

Le validateur impose les variables exactes : `{context}`, `{categories, sources, keys, question}`, `{signals}` et `{title, references}`. Une édition invalide via Config reçoit HTTP 400 et ne remplace pas le fichier courant. Le YAML reste un réglage opérationnel : retrieval et sauvegarde atomique restent dans le code.

## 10. API utile

| Route | Rôle |
|---|---|
| `GET /api/health` | Healthcheck léger du backend |
| `GET /api/health/app` | Stockage persistant total, volumes de signaux, santé de Nyx, Telegram et de l’index RAG |
| `GET /api/summary` | Contenu, nom et date de modification du dernier rapport daté, sans cache HTTP |
| `GET /api/summary/download` | Téléchargement du dernier rapport avec son nom daté |
| `GET/POST /api/refresh` | État ou démarrage de la collecte |
| `GET /api/articles` | Articles filtrés et enrichis depuis le catalogue |
| `GET /api/articles/favorites` | Jusqu’à 30 snapshots favoris durables, triés par récupération |
| `GET /api/articles/feedback` | Tous les snapshots favoris/masqués pour Data Analysis |
| `GET/POST /api/views` | Lecture ou ajout atomique d’un raccourci Flux, cinq maximum |
| `GET/PUT /api/sources` | Lecture ou remplacement structuré des sources |
| `POST /api/assistant` | Question RAG avec `session_id` |
| `DELETE /api/assistant/session/<session_id>` | Effacement de la session |
| `GET/PUT /api/config/<name>` | Lecture ou écriture atomique des YAML autorisés |
| `GET /api/rag/index/status` | État persistant de la synchronisation Chroma |
| `GET /api/collection/runs` | Historique des collectes automatiques et manuelles |
| `DELETE /api/storage/sqlite` | Vidage des données courantes et `VACUUM`, hors feedback durable |
| `DELETE /api/storage/chroma` | Suppression de l’index Chroma situé dans `data/` |

Les purges sont séparées parce que SQLite est la source de vérité alors que Chroma est reconstructible. Elles sont refusées lorsqu’une collecte est active. L’interface exige en plus une confirmation textuelle `SQLITE` ou `CHROMA`.

Les détails exacts de paramètres restent définis par les routes et les appels dans `web/src/lib/api.ts`; ce tableau documente les responsabilités, pas un contrat OpenAPI exhaustif.

La route de synthèse ne reçoit aucun chemin du client : elle choisit uniquement le dernier fichier conforme de `data/reports/`, avec repli sur `summary.md`. Le frontend confie son contenu à `react-markdown` sans activer le HTML brut. L’absence de rapport produit une carte vide, pas une erreur globale de rafraîchissement.

## 11. Déploiement et limites

nginx publie le port hôte `1207` vers son port `8080` et relaie `/api` vers `api:8000`. La route exacte `/api/assistant` possède un timeout proxy de 210 secondes afin de laisser aboutir le timeout d’inférence Ollama de 180 secondes sans produire de HTTP 504 prématuré. Flask n’a pas de port hôte. Le web est limité à 150 Mo et l’API à 700 Mo. Les appels de modèles sont distants, ce qui maintient ces limites raisonnables.

Compose monte également `systemd/argos-collect.timer` en lecture seule dans l’API. `/api/health/app` parse `OnCalendar` et `Persistent` depuis ce fichier ; la carte Cycles de collecte n’embarque donc aucune copie des horaires. La dernière exécution automatique affichée provient de `collection_runs`, identifiée par `trigger=systemd`.

Les modes de panne sont volontairement séparés : une indisponibilité de Nyx bloque l’indexation et l’assistant, mais pas la consultation SQLite ; un flux RSS cassé n’arrête pas les autres ; Telegram désactivé ou indisponible n’affecte pas les données collectées et laisse le rapport en attente. L’exposition est prévue pour un LAN de confiance. Avant toute exposition Internet, il faut ajouter authentification, TLS, limitation de débit et protection SSRF.

## 12. Vérification

Les contrôles de référence sont Ruff et Black pour Python, unittest avec `PYTHONPATH=backend`, Oxlint et le build Vite pour le frontend, puis `docker compose config --quiet`. Un test RAG avec modèle factice valide le passage de deux à quatre messages entre deux appels de même session ; la validation de bout en bout sur Nyx doit être répétée après déploiement et collecte réels.
