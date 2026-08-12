# ELN — Argos

## 12/08 01:05 — Audit complet de la documentation

Les dix fichiers Markdown du projet ont été réalignés sur l’application courante : trois domaines backend actifs, taxonomie de 18 tags `snake_case`, progression de pipeline, synthèse avec fallback, livraison Telegram exclusive, favoris durables, cartes Santé dynamiques, libellés simplifiés et sous-onglet YAML. Les références à Digest, Viz, clusters et heatmap sont conservées uniquement dans les entrées explicitement historiques.

## 12/08 01:20 — Sélection P1 bornée

- Conservation des identifiants SHA-256 dans la planification Nyx.
- Sélection des 40 P1 les plus récents selon leur date de publication, avec date de collecte en repli.
- Ajout du paramètre `summary.top_n` dans la configuration IA et d’un test de borne et de tri.

## 11/08 — Identité verte et métriques Flux

Le favicon, le carré Argos et le bouton Collecter utilisent désormais le vert `success`. La carte Nouveaux signaux est complétée par une carte Total signaux, portant le bandeau supérieur à quatre métriques.

## 11/08 — Position du score

Le score des cartes Flux est déplacé sous la croix, dans la colonne d’actions, avec une graisse normale afin de réduire sa dominance visuelle.

## 11/08 — Feedback éditorial persistant

Création de `signal_feedback`, table hors rétention contenant le label good/bad et un snapshot JSON complet du signal. L’étoile produit un bon candidat et reste remplie après rechargement ; la croix produit un mauvais candidat puis masque l’article. Ce corpus servira à mesurer et ajuster le scoring ultérieurement.

## 11/08 — Masquage non destructif des articles

Ajout du booléen SQLite `view`, vrai par défaut, et d’une croix sur les cartes Flux. Le masquage persiste après recollecte et retire l’article des listes UI sans le supprimer de SQLite, des analyses ou du RAG.

## 11/08 — Cartes de pilotage quotidien

Les cartes Flux affichent désormais les nouveaux signaux de la dernière collecte, les articles P1 récents et la dernière collecte avec son bilan sources OK/erreurs. Les valeurs viennent de SQLite et restent disponibles après redémarrage.

## 11/08 — Date affichée dans Flux

Les cartes et le lecteur affichent uniquement `published_at` avec date et heure. Quand le flux ne fournit pas cette valeur, l’interface l’indique explicitement au lieu d’afficher `collected_at`.

## 11/08 — Ajustement du scoring

La pertinence devient `min(60, 10 + 10 × mots-clés)`. La fraîcheur adopte une décroissance exponentielle de demi-vie `max_age_days / 2`, soit 7 jours avec la configuration actuelle, au lieu d’une pente linéaire.

## 11/08 — Rescoring global des signaux (formule initiale)

La première formule combinait pertinence lexicale, priorité et fraîcheur linéaire. Après chaque collecte, tous les articles SQLite étaient déjà recalculés et les changements de score mettaient à jour les métadonnées Chroma sans nouvel embedding. La décroissance linéaire a été remplacée ensuite par la formule exponentielle décrite ci-dessus.

## 11/08 — Progression de la collecte

L’état partagé expose désormais sources terminées/total, dernière source achevée et échecs. Flux affiche ces informations dans une barre sous les trois métriques pendant toute collecte manuelle ou systemd. Avec six workers concurrents, la source affichée est la dernière terminée, pas une unique source active.

## 11/08 — Tri des articles dans Flux

La barre Flux tient sur une ligne dans l’ordre catégorie, priorité, recherche, tri. Le tri décroissant propose publication récente par défaut, importation récente ou score.

## 11/08 — Fenêtre d’ingestion et rétention

Ajout de `collection.max_age_days=14` dans `sources.yml`. Les entrées datées plus anciennes sont ignorées avant application de `max_items`; celles sans date restent acceptées. `storage.retention_days` passe de 180 à 60 jours et continue d’être appliqué automatiquement après chaque collecte, avant la synchronisation Chroma.

## 11/08 — Réparation des 25 sources en erreur

Validation HTTP et `feedparser` des remplacements : 21 sources utilisent désormais un RSS/Atom officiel fonctionnel, notamment GPUOpen, ROCm Atom, Databricks, Meta Engineering et des releases GitHub officielles. ENISA, EuroHPC JU, HaDEA et OECD AI ne proposent plus de flux exploitable vérifiable ; elles restent documentées mais désactivées. Le catalogue compte donc 125 sources actives. Santé masque les entrées désactivées et résout catégorie/URL depuis le YAML courant.

## 11/08 — Lisibilité des sources et de la santé

Les cartes Flux mettent la source en évidence dans une pilule teintée par la couleur de catégorie configurée. La vue Santé présente désormais les collectes, les services IA puis les sources, avec les flux défaillants en tête.

## 11/08 — Filtre de priorité dans Flux

Ajout d’un sélecteur P1/P2/P3 sur la même ligne que la catégorie et la recherche. Les trois critères se combinent avec un ET ; chaque champ vide reste neutre.

## 11/08 — Observabilité des collectes automatisées

Ajout de `collection_runs` pour afficher dans Santé l’origine, les horaires, le résultat et les erreurs des collectes. Le service systemd appelle désormais `/api/refresh?trigger=systemd`; le bouton reste identifié comme manuel. Les journaux système et le socket Docker ne sont volontairement pas montés dans le conteneur. Les unités ne doivent être réinstallées que lorsqu’elles changent, pas après chaque build applicatif.

## 11/08 — Planification et reprise de l’index RAG

Le timer systemd est réglé sur 10 h, 14 h et 18 h. L’indexation Chroma n’est plus une étape dont l’échec est seulement ajouté aux erreurs de collecte : son état est persisté dans `rag_index_state`. Une panne Nyx laisse l’index en attente, tout en conservant les articles SQLite, puis la collecte suivante reprend incrémentalement. L’onglet Santé expose l’attente, la dernière réussite et la dernière erreur.

## 11/08 — Ordre canonique des catégories

Le catalogue est réordonné pour suivre le parcours de veille : agrégateurs, laboratoires/providers, frameworks/SDK, HPC, Ops/cloud, sécurité et évaluation, appels à projets, puis institutions publiques. Les libellés sont harmonisés sans modifier les 134 sources ni leur ordre interne.

## 11/08 — Configuration administrable et métriques dynamiques

Le compteur de la page Flux ne mesure plus les seules sources déjà présentes dans SQLite : l’API calcule les 129 sources actives depuis les 134 entrées YAML et expose séparément le nombre déjà collecté. Ajout d’un onglet Config pour éditer les trois YAML avec validation et remplacement atomique. Les purges SQLite et Chroma sont séparées, bloquées pendant les tâches et protégées par une confirmation textuelle. Le catalogue passe de 13 à 8 catégories par fusion des familles publications/newsletters, frameworks/RAG/inférence et Ops/cloud.

## 11/08 — Consolidation documentaire

Les dix fichiers Markdown du dépôt ont été alignés sur l’état effectif du code : backend en quatre domaines, catalogue de 134 sources et 14 clés, Chroma distinct de SQLite, chunking 800/180 à partir de 400 caractères, retrieval 40/10, LangGraph avec mémoire volatile et déploiement Atlas sur le port 1207. Les commandes de synchronisation excluent désormais explicitement les données persistantes et les copies locales de configuration.

## 11/08 — Orchestration LangGraph et mémoire de session

Le domaine RAG est séparé en indexation, retrieval et agent. La génération LCEL stateless est remplacée par un graphe `retrieve → generate`, compilé avec `InMemorySaver`. Le navigateur fournit un UUID stable comme `thread_id`, permettant à ChatOllama d’exploiter l’historique récent sans mélanger les utilisateurs. Une façade `service.py` conserve les imports existants pendant la transition.

## 11/08 — Chunking récursif LangChain (réglage initial)

Le splitter sémantique LlamaIndex est remplacé par `RecursiveCharacterTextSplitter`, plus prévisible et moins coûteux pour les résumés RSS. Le premier réglage utilisait des blocs de 1 200 caractères avec 180 caractères de chevauchement ; la configuration active a ensuite été resserrée à 800 caractères, avec le même chevauchement et un seuil de découpe de 400 caractères. Les dépendances LlamaIndex sont supprimées et la version d’index est incrémentée afin de reconstruire automatiquement les chunks existants à la prochaine collecte.

## 11/08 — Refonte du pipeline RAG (état intermédiaire remplacé)

Le retrieval linéaire sur les vecteurs SQLite a d’abord été remplacé par un index Chroma cosine, avec segmentation LlamaIndex et génération LCEL. Cette étape a validé la self-query et le reranking distant sans charger de cross-encoder dans les 700 Mo d’Atlas. Le splitter LlamaIndex puis LCEL ont été remplacés le même jour par `RecursiveCharacterTextSplitter` et LangGraph, comme décrit dans les entrées plus récentes ci-dessus.

## 11/08 — Consolidation des packages backend

Les domaines à forte cohésion ont été regroupés : collecte, articles et stockage sous `feeds`; configuration, état partagé et santé sous `system`. Les responsabilités restent séparées par module dans chacun de ces packages, évitant à la fois la dispersion en sept petits dossiers et le retour à des fichiers monolithiques.

## 11/08 — Découpage du backend par domaine

Le fichier Flask monolithique est remplacé par un point d’entrée minimal et sept packages métier. Les routes publiques restent identiques et sont maintenant enregistrées par blueprints. La logique de collecte, de clustering et de RAG est importable et testable indépendamment. Le contexte Docker pointe sur `backend/`, tandis que le service Compose demeure nommé `api` pour ne pas casser le proxy nginx.

## 11/08 14:51 — Assainissement structurel du dépôt

Refactorisation conservatrice du frontend : `App.tsx` ne porte plus les vues, types, appels HTTP et composants d’articles. Ces responsabilités sont maintenant réparties entre `views/`, `components/`, `lib/` et `types.ts`. Suppression du diagnostic réseau temporaire, de l’ancien composant Tabs, de quatre composants UI sans appelant et de la dépendance Radix correspondante. L’API a été normalisée avec Black et sa seule variable morte détectée par Ruff a été retirée. Vérifications réussies : Ruff, Black, compilation Python, tests YAML, lint frontend et build Vite.

## 11/08 14:35 — Éditeur structuré du catalogue

La grille Sources est remplacée par un panneau hiérarchique adapté aux 13 catégories et 134 sources actuelles. Les catégories sont repliables et résument leur état avant ouverture. Les clés utilisent désormais des boutons issus du vocabulaire contrôlé commun à l’API, tandis que priorité, activation, limite, nom et URL restent directement éditables. Une inversion `keys`/`priorité` et quatre priorités laissées vides pendant l’édition du YAML ont été réparées pour rétablir son chargement.

## 11/08 14:00 — Priorisation des sources

Ajout d’une priorité obligatoire de 1 à 3 sur l’ensemble du catalogue. Comme les clés de veille, la priorité est résolue depuis le YAML lors de la lecture des articles : aucune migration de la base n’est nécessaire. Le dashboard matérialise P1 en rouge, P2 en vert et P3 sans accent coloré. Le catalogue est enrichi de frameworks agentiques, outils de sécurité/évaluation IA, institutions gouvernementales et portails de financement ; les pages sans syndication vérifiée restent désactivées.

## 11/08 13:10 — Catalogue de veille

Réorganisation des sources autour de familles fonctionnelles et ajout initial d’un vocabulaire contrôlé de 12 clés par source, étendu ensuite à 14 avec `Cybersécurité` et `Appels à projets`. L’API enrichit les articles à la lecture depuis la configuration, sans migration SQLite ; les anciens articles bénéficient donc immédiatement des clés. Ajout de tests de structure, d’un champ d’édition des clés dans la vue Sources et de pilules vertes dans Flux/Digest.

## 10/08 16:15 — Initialisation

- Analyse de l'ancien dépôt FULCRUM : application cyber/géopolitique, dashboard HTML statique et nombreux modules non pertinents pour la veille IA.
- Création de l'API RSS, de l'interface React et d'une configuration de sources IA dédiée.

## 10/08 16:20 — Validation fonctionnelle

- Build React et images Docker validés.
- Collecte de test réussie : 142 articles issus de 9 flux sans erreur.

## 10/08 16:25 — Déploiement Atlas

- Déploiement dans `/home/vika/argos`.
- Service publié sur `192.168.1.50:1207`.
- Healthchecks API et web validés.

## 10/08 16:30 — Nettoyage du dépôt

- Suppression de l'ancien code FULCRUM, de ses tests, rapports, bases et artefacts.
- Documentation du projet remplacée par les documents de référence dans `docs/`.

## 10/08 16:35 — Catalogue de sources

- Extension de `config/sources.yml` à 11 thématiques et 93 flux.
- Conservation de 9 sources éprouvées actives ; 84 candidates restent désactivées jusqu'au tri manuel.

## 10/08 16:40 — Documentation produit

- README enrichi : architecture, collecte, API, stockage SQLite, sauvegarde, exploitation et sécurité.
- Ajout de `IDEAS.md`, catalogue de pistes QoL, analytiques, visualisation, partage et administration.

## 10/08 17:25 — Extension opérationnelle

- Ajout des onglets Flux, Digest, Santé, Viz et Assistant WIP.
- Ajout de la santé par source, déduplication URL/similarité, rétention, alertes Telegram et clustering Ollama batché.
- Embeddings Nyx validés sur `nomic-embed-text-v2-moe:latest` (768 dimensions) ; endpoint assistant :11434 indisponible lors du test.

## 11/08 18:26 — Timeout de l’assistant et retrieval simplifié

- Le délai nginx de la route `POST /api/assistant` passe à 210 secondes, au-dessus du timeout Ollama de 180 secondes, pour éviter un HTTP 504 prématuré.
- Retrait des étiquettes `RAG` et `WIP` ainsi que du bandeau de disponibilité dans l’interface.
- L’envoi n’est plus bloqué par le diagnostic préalable de Nyx ; une éventuelle erreur est affichée après la requête.
- Suppression du reranker génératif : les résultats suivent désormais directement la similarité Chroma, puis sont dédupliqués par article.
- Vérifications réussies : lint et build frontend, validation Compose et `git diff --check`.

## 11/08 18:40 — Retrait de la visualisation

- Suppression de la vue Viz, de la heatmap, de la carte sémantique et de la gestion des clusters.
- Suppression du domaine backend `clustering`, de ses routes, de son état d’exécution et de la création de ses tables SQLite.
- Les anciennes tables de visualisation éventuellement présentes sur Atlas ne sont pas supprimées automatiquement.

## 11/08 19:00 — Navigation horizontale et retrait du Digest

- Suppression de la vue Digest et de son état local de dernière visite.
- Remplacement du panneau latéral par une barre d’onglets horizontale en pilules, selon le modèle d’Aede.
- Déplacement de Sources dans Config, avec deux sous-onglets : Sources et YAML et stockage.

## 11/08 19:20 — Audit global du dépôt

- Suppression de la façade RAG, des routes de compatibilité et des endpoints YAML doublonnés sans consommateur.
- Suppression du double diagnostic Nyx et de la double écriture de l’état d’indexation.
- Le polling ne remplace plus le catalogue en cours d’édition ; les YAML avancés sont chargés à la demande.
- Correction de la création de source invalide, de la remontée d’erreur des tests de flux et des valeurs IA obsolètes.
- Alignement du runtime, de l’exemple et de la documentation sur 24 candidats, 6 résultats et des chunks 1 200/180 à partir de 900 caractères.

## 11/08 19:35 — Regroupement des assistants

- Navigation réordonnée en Flux, Assistants, Santé et Config.
- Ajout sous le chatbot d’une synthèse sûre du bot Telegram : état, complétude de configuration, seuil et limite d’envoi.

## 11/08 19:50 — Homepage et synthèse IA

- Ajout de Homepage en première position et déplacement des quatre métriques depuis Flux.
- Ajout d’une route en lecture seule pour `data/summary.md`, avec date de modification.
- Rendu Markdown sûr dans la carte AI Summary avec état vide lorsque le fichier est absent.

## 11/08 20:10 — Agent LangGraph de synthèse P1

- Ajout du graphe `select → plan → draft_sections → compose → save` après toute indexation réussie.
- Regroupement structuré en cinq parties maximum avec conservation déterministe des signaux dans `Autres`.
- Retrieval Chroma et génération par partie, puis écriture atomique de `data/summary.md`.
- Reprise implicite des P1 après panne grâce à la date du dernier document effectivement sauvegardé.

## 11/08 20:30 — Centralisation des prompts

- Déplacement des quatre prompts LLM dans `config/prompt.yaml`.
- Ajout d’un chargeur/interpolateur partagé et d’une validation stricte des placeholders.
- Ajout du fichier Prompts à l’éditeur YAML de Config et au montage opérationnel Compose.

## 11/08 20:45 — Cycles automatiques dans Assistants

- Ajout d’une carte décrivant collecte, rescoring, embedding et synthèse P1.
- Horaires et rattrapage parsés depuis le timer systemd monté en lecture seule ; dernière exécution issue de SQLite.

## 11/08 21:00 — Filtres Source et Tags

- Ajout d’une seconde ligne dans Flux avec autocomplétion multi-source et dropdown multi-tag.
- Affichage des choix en pilules vertes supprimables ; combinaison avec catégorie, priorité, texte et tri.
- Union entre sources sélectionnées et intersection entre tags sélectionnés, sans exiger l’égalité exacte des tags.

## 11/08 22:45 — Livraison Telegram du rapport

- Suppression des notifications unitaires basées sur le score : Telegram est désormais réservé à `data/summary.md`.
- Pipeline rendue explicite : collecte et SQLite, embedding Chroma, agent LangGraph, puis livraison Telegram.
- Ajout d’un découpage sûr des longs rapports et d’une empreinte atomique permettant la reprise sans doublon après une panne.
- L’état Assistants expose la disponibilité, le rapport en attente et le dernier envoi sans divulguer les secrets.

## 11/08 23:05 — Taxonomie globale des tags

- Remplacement des 79 mots-clés répartis par catégorie par 18 tags globaux contrôlés et leurs alias.
- Détection homogène pour toutes les sources, avec limites de mots et dédoublonnage des alias vers un seul libellé visible.
- Suppression des mots-clés de catégorie dans l’éditeur Sources ; la taxonomie avancée reste éditable dans le YAML.
- Le rescoring de chaque collecte migre automatiquement les tags déjà enregistrés dans SQLite.

## 11/08 23:20 — Repli du planificateur de synthèse

- L’échec `OUTPUT_PARSING_FAILURE` de la sortie structurée Nyx ne bloque plus le rapport complet.
- Ajout d’un plan déterministe par catégorie, limité à cinq parties avec conservation du reste dans `Autres`.
- Le résultat expose `planning_mode` afin de distinguer planification LLM et repli.

## 11/08 23:30 — Tags globaux dans Flux

- Le dropdown de filtre est alimenté par les 18 libellés de la taxonomie YAML, et non par les anciennes valeurs rencontrées dans SQLite.
- Les cartes Flux affichent désormais leurs tags normalisés en plus des clés éditoriales de leur source.

## 11/08 23:45 — Progression de pipeline

- Remplacement de la barre limitée aux flux RSS par cinq plages pondérées allant du fetch à Telegram.
- Granularité source par source, article Chroma par article, partie de synthèse par partie et fragment Telegram par fragment.
- Ajout d’un polling léger de l’état chaque seconde uniquement pendant l’exécution.

## 11/08 23:55 — Tags en snake_case

- Conversion des 18 identifiants de tags globaux en `snake_case` ASCII.
- Validation du format à la sauvegarde du YAML ; les alias de détection conservent leur forme naturelle.
- Le prochain rescoring remplacera automatiquement les anciens libellés stockés dans SQLite.

## 12/08 00:05 — Hauteur responsive des filtres

- Les champs Recherche et Source de Flux utilisent une hauteur fluide basée sur `4vh`.
- La hauteur reste bornée entre la ligne de texte de base et les 36 px historiques.

## 12/08 00:20 — Favoris Homepage et filtre Flux

- Ajout d’une route bornée à 30 snapshots `good`, triés par date de récupération et indépendants de la purge des articles.
- Homepage affiche trois favoris à la fois dans une carte défilante et permet d’ouvrir le lecteur.
- Ajout en fin de seconde ligne Flux d’un toggle étoile cumulable avec tous les filtres existants.

## 12/08 00:35 — Simplification des libellés

- Retrait des textes d’aide redondants sur Homepage, Flux et Assistants.
- Santé affiche Services IA avant Collectes automatisées et borne la table des sources à cinq lignes défilantes.
- Simplification du sous-onglet Config en `YAML` et du résumé du catalogue en catégories, sources actives et tags.

## 12/08 00:50 — Cartes de santé opérationnelles

- Remplacement des métriques SQLite/doublons par dernier cycle, stockage `data/` total et signaux non dupliqués avec sous-total P1.
- Fusion des sources saines et en erreur dans une carte à deux valeurs colorées.
- Toutes les valeurs proviennent de SQLite, du catalogue ou du système de fichiers persistant.


## Instantané historique — 10/08/2026

- Le nom de l’application, les conteneurs, unités systemd et répertoire de déploiement sont désormais **Argos** (`/home/vika/argos`).
- La collecte planifiée est fournie par `systemd/argos-collect.{service,timer}` ; elle n’est pas activée automatiquement.
- La rétention SQLite est configurée dans `storage.retention_days`.
- Nyx était configuré sur `:11434` ; l’assistant utilisait déjà `qwen3.6:27b`.
- La route publique de collecte est `/api/refresh` ; `/api/collect` reste une compatibilité API.
## 12/08 08:44 — Historique daté des rapports

- Archivage UTC de chaque synthèse dans `data/reports/report_YYMMDD_HHMM.md`, avec date reprise dans le titre Markdown.
- Résolution commune du dernier rapport pour le seuil P1, Homepage et Telegram ; repli sur `data/summary.md` pour migrer sans perdre le seuil existant.
- Conservation de `data/summary.md` comme copie courante pour les intégrations historiques.
## 12/08 09:22 — Summarizer Telegram

- Insertion d’un graphe `load → summarize → save` entre la synthèse P1 et Telegram.
- Production persistante d’un texte sans Markdown ni références, titré `Rapport DD-MM HH:MM` et strictement limité à un message.
- Refus des sorties trop longues plutôt que découpage ; reprise d’envoi depuis l’artefact existant sans nouvel appel Nyx.
- Test de condensation basé sur le rapport réel de 53 Ko dans `data_example/report.md`.
## 12/08 09:35 — En-tête des favoris Homepage

- Retrait de l’étoile décorative de la carte Flux favoris, sans modifier les favoris ni leur filtre dans Flux.
## 12/08 09:45 — Téléchargement du dernier rapport

- Renommage de `AI Summary` en `Dernier rapport` sur Homepage.
- Ajout d’un bouton téléchargeant le dernier Markdown avec son nom daté `report_YYMMDD_HHMM.md` via une route fixe.

## 12/08 09:50 — Interface de chat multi-tour

- Reprise des principes de l’interface NEXUS : chronologie en bulles, zone de saisie fixe, défilement automatique et raccourci Entrée/Maj + Entrée.
- Remplacement de la réponse unique par tous les tours utilisateur/assistant, associés au même `session_id` LangGraph.
- Hauteur du chat portée à 42 rem, soit environ trois fois la carte précédente, et conservation de la chronologie dans le navigateur lors des changements d’onglet.
- Ajout d’une action Nouvelle conversation qui efface le checkpoint backend et renouvelle la session locale.

## 12/08 10:00 — Retrieval dédié à l’assistant

- Conservation des paramètres `rag` existants pour l’index partagé et le retrieval utilisé pendant la rédaction du rapport.
- Ajout de `assistant.rag` avec ses propres `candidate_k`, `final_k`, `query_model` et `session_message_limit`.
- Routage explicite du chatbot vers ce profil, sans modifier le profil du rapport.
- Compatibilité des anciens YAML : en l’absence de la nouvelle section, l’assistant hérite des limites et du modèle de requête de `rag`.

## 12/08 10:05 — Alignement du téléchargement Homepage

- Neutralisation locale de la marge basse du titre `Dernier rapport` afin de centrer verticalement son bouton de téléchargement.

## 12/08 10:23 — Réparation des flux AAP

- Conservation du catalogue Atlas récupéré par l’utilisateur, qui contient désormais 129 sources, sans réintroduire les cinq entrées qu’il avait retirées.
- Remplacement des sept pages HTML ou endpoints RSS obsolètes de la catégorie financements ; les huit sources sont maintenant actives.
- Validation directe par `fetch_source` des flux officiels ANR, EIC, HaDEA, REA, Commission R&I, EuroHPC, UKRI et NSF : HTTP 200, aucune erreur et 15 à 20 entrées sur la fenêtre historique de contrôle.
- Avec la fenêtre opérationnelle de sept jours, EIC, HaDEA, Commission R&I, UKRI et NSF fournissaient des éléments récents ; ANR, EuroHPC et REA restaient sains mais sans publication assez récente au moment du test.
