# Collecte et indexation planifiées

Argos utilise un timer systemd sur Atlas plutôt qu’un `crontab`. Il offre des journaux dédiés et, avec `Persistent=true`, rejoue une occurrence manquée après un arrêt de l’hôte.

## Horaires

`systemd/argos-collect.timer` contient :

```ini
OnCalendar=*-*-* 10,14,18:00:00
Persistent=true
```

Les heures suivent le fuseau local d’Atlas. Le vérifier avec `timedatectl status`. Chaque déclenchement appelle `POST /api/refresh?trigger=systemd` ; le backend exécute ensuite `fetch → SQLite/scoring → embeddings Chroma → synthèse P1 → Telegram`. Le paramètre distingue les passages automatiques dans l’onglet **Santé**.

## Installation ou mise à jour sur Atlas

Après synchronisation du dépôt et reconstruction des conteneurs :

```bash
cd /home/vika/argos
sudo cp systemd/argos-collect.service /etc/systemd/system/
sudo cp systemd/argos-collect.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now argos-collect.timer
sudo systemctl restart argos-collect.timer
systemctl list-timers argos-collect.timer
systemd-analyze calendar '*-*-* 10,14,18:00:00'
```

## Test manuel et diagnostic

```bash
sudo systemctl start argos-collect.service
systemctl status argos-collect.service argos-collect.timer
journalctl -u argos-collect.service -n 100 --no-pager
curl --fail http://127.0.0.1:1207/api/refresh
curl --fail http://127.0.0.1:1207/api/rag/index/status
docker compose logs --since 30m api
```

Le service utilise un timeout HTTP de 20 secondes, mais il n’attend pas le traitement : le `202` confirme seulement que le thread a démarré. Une nouvelle requête pendant une collecte ne crée pas de second thread.

## Faut-il réinstaller les unités à chaque déploiement ?

Non. Un `rsync` suivi de `docker compose up -d --build` ne modifie pas les unités déjà copiées sous `/etc/systemd/system`. Il faut les recopier, lancer `daemon-reload` et redémarrer le timer uniquement lorsqu’un fichier dans `systemd/` change.

Cette version modifie `argos-collect.service` pour ajouter `trigger=systemd` : appliquer une fois la procédure d’installation ci-dessus. Pour les prochains changements limités à `backend/`, `web/` ou `config/`, aucune commande systemctl n’est nécessaire.

## Informations visibles dans Santé

Argos ne monte ni le journal systemd ni le socket Docker dans le conteneur. Cela évite de lui donner un accès privilégié à l’hôte. SQLite conserve à la place l’origine, le début, la fin, l’état, le bilan et l’erreur de chaque collecte. L’onglet **Santé** combine cet historique avec l’état persistant Chroma, le stockage total, les volumes de signaux et la santé des sources.

Les commandes hôte restent utiles pour diagnostiquer l’infrastructure :

```bash
curl --fail http://127.0.0.1:1207/api/rag/index/status
journalctl -u argos-collect.service -n 100 --no-pager
docker compose logs --since 30m api
```

## Nyx indisponible

1. Les articles sont d’abord enregistrés dans SQLite.
2. L’état RAG persistant passe à `pending=true`.
3. Argos tente la synchronisation Chroma.
4. Si Nyx échoue, l’erreur est conservée et la collecte RSS reste exploitable.
5. La collecte suivante — timer ou bouton **Collecter** — retente automatiquement.
6. Les fingerprints font sauter les chunks déjà à jour.

Une file externe n’est donc pas nécessaire. Après remise en ligne de Nyx, une collecte manuelle suffit pour accélérer la reprise.

## Rétention

`collection.max_age_days` définit l’âge maximal des entrées RSS ingérées, sauf si elles ne fournissent aucune date. `storage.retention_days` définit l’âge de purge des articles stockés. La purge précède la synchronisation Chroma ; les chunks sortis de la fenêtre sont supprimés lorsque la synchronisation suivante réussit entièrement.
