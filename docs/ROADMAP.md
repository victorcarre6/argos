# Roadmap — Argos

## Priorité actuelle

- [TODO] 11/08 — Persister les checkpoints LangGraph afin de conserver les sessions après redémarrage.
- [TODO] 11/08 — Créer un jeu d’évaluation RAG et mesurer retrieval, citations et fidélité des réponses.
- [TODO] 11/08 — Évaluer une recherche hybride FTS5/BM25 + Chroma et un reranker cross-encoder sur Nyx.
- [TODO] 11/08 — Ajouter une protection SSRF aux URL de sources et aux redirections.
- [TODO] 11/08 — Versionner les migrations SQLite et tester une restauration de sauvegarde.
- [TODO] 11/08 — Vérifier sur Atlas l’assistant de bout en bout avec les modèles Nyx actifs.

## Réalisé

- [DONE] 12/08 — Permettre le téléchargement du dernier rapport daté depuis Homepage.
- [DONE] 12/08 — Condenser chaque rapport avec un agent dédié avant son envoi en un message Telegram sans Markdown.
- [DONE] 12/08 — Archiver les synthèses sous `report_YYMMDD_HHMM.md` et charger automatiquement la plus récente.
- [DONE] 12/08 — Borner la synthèse aux 40 P1 publiés les plus récemment, avec seuil configurable.
- [DONE] 12/08 — Recentrer les cartes Santé sur cycle, stockage, signaux et état agrégé des sources.
- [DONE] 12/08 — Afficher les favoris durables sur Homepage et les filtrer dans Flux.
- [DONE] 11/08 — Normaliser les identifiants de tags globaux en `snake_case` ASCII.
- [DONE] 11/08 — Représenter toute la pipeline de collecte avec une progression granulaire et pondérée.
- [DONE] 11/08 — Afficher et sélectionner exclusivement les tags globaux normalisés dans Flux.
- [DONE] 11/08 — Tolérer les sorties JSON invalides du planificateur de synthèse avec un regroupement déterministe complet.
- [DONE] 11/08 — Homogénéiser les tags avec une taxonomie globale de 18 concepts et des alias dédupliqués.
- [DONE] 11/08 — Réserver Telegram à la livraison du rapport après la pipeline complète, avec découpage et reprise sans doublon.
- [DONE] 11/08 — Ajouter les filtres multisélection Source et Tags à la vue Flux.
- [DONE] 11/08 — Afficher dans Assistants les cycles automatiques depuis le timer systemd et l’historique SQLite.
- [DONE] 11/08 — Centraliser et valider tous les prompts LLM dans `config/prompt.yaml`.
- [DONE] 11/08 — Générer après chaque embedding une synthèse LangGraph des nouveaux P1, enrichie par RAG et sauvegardée atomiquement.
- [DONE] 11/08 — Ajouter Homepage avec les métriques de pilotage et le rendu Markdown de `data/summary.md`.
- [DONE] 11/08 — Regrouper chatbot et informations Telegram dans Assistants et réordonner la navigation.
- [DONE] 11/08 — Auditer le dépôt et retirer façades, routes, états, appels réseau et configurations devenus morts ou dupliqués.
- [DONE] 11/08 — Retirer Digest, adopter la navigation horizontale d’Aede et intégrer Sources à Config dans deux sous-onglets.
- [DONE] 11/08 — Constituer un dataset durable de bons/mauvais candidats à partir de l’étoile et de la croix des cartes Flux.
- [DONE] 11/08 — Intégrer priorité et fraîcheur au score, puis rescorer tout SQLite à chaque collecte sans ré-embeder les contenus inchangés.
- [DONE] 11/08 — Limiter l’ingestion RSS aux 14 derniers jours et ramener la rétention automatique SQLite à 60 jours.
- [DONE] 11/08 — Réparer 21 flux fournisseurs/institutions en erreur et désactiver proprement quatre institutions sans flux officiel exploitable.
- [DONE] 11/08 — Afficher dans Santé l’historique persistant des collectes automatiques/manuelles et le diagnostic RAG.
- [DONE] 11/08 — Planifier collecte et embedding à 10 h, 14 h et 18 h, avec reprise persistante de l’index après une panne Nyx.
- [DONE] 11/08 — Calculer les métriques de sources depuis le YAML, ajouter l’onglet Config et les purges confirmées SQLite/Chroma.
- [DONE] 11/08 — Fusionner le catalogue en 8 catégories cohérentes sans perdre les 134 sources.
- [DONE] 11/08 — Remplacer LCEL par un `StateGraph` minimal avec mémoire de session et séparer `indexing`, `retrieve` et `agent`.
- [DONE] 11/08 — Utiliser `RecursiveCharacterTextSplitter` et supprimer LlamaIndex.
- [DONE] 11/08 — Créer l’index Chroma et la self-query filtrée sur Nyx ; le reranking génératif a ensuite été retiré pour réduire la latence.
- [DONE] 11/08 — Consolider le backend actif dans `feeds`, `system` et `rag`, puis retirer entièrement `clustering`.
- [DONE] 11/08 — Découper le frontend en vues, composants, contrats et appels API maintenables.
- [DONE] 11/08 — Repenser le panneau Sources avec catégories repliables et édition des nouveaux champs.
- [DONE] 11/08 — Étendre le catalogue à 134 sources, avec 14 clés et priorités P1/P2/P3.
- [DONE] 10/08 — Livrer collecte concurrente, parsing, SQLite, déduplication, rétention et santé des flux.
- [DONE] 10/08 — Livrer recherche, Digest, heatmap, clusters, carte sémantique et alertes Telegram optionnelles.
- [DONE] 11/08 — Retirer Viz, la heatmap, la carte sémantique et le backend de clusterisation afin de recentrer Argos sur la veille et le RAG.
- [DONE] 10/08 — Préparer le timer systemd initial et le déploiement Docker sur le port LAN `1207`.

Les idées non planifiées restent dans [`../IDEAS.md`](../IDEAS.md).
