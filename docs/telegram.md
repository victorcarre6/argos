# Livraison du rapport par Telegram

Telegram est exclusivement la dernière étape de la collecte :

```text
RSS → SQLite et scoring → embeddings Chroma → synthèse → summarizer → Telegram
```

Argos n’envoie pas d’alertes article par article. Après la génération du rapport complet, le graphe `summarizer` demande à Nyx un condensé sans Markdown, URL ni références. Le résultat est sauvegardé à côté du rapport sous `telegram_YYMMDD_HHMM.txt`, avec le titre `Rapport DD-MM HH:MM`, puis envoyé comme un unique message texte.

## Configuration

1. Créer le bot avec [@BotFather](https://t.me/BotFather), puis lui envoyer un premier message depuis la conversation cible.
2. Consulter `https://api.telegram.org/bot<TOKEN>/getUpdates` et relever `message.chat.id`.
3. Sur Atlas, ajouter `TELEGRAM_BOT_TOKEN=<token>` dans `/home/vika/argos/.env`, avec des permissions `600`. Ne jamais placer le token dans Git, le YAML ou l’historique shell.
4. Dans `config/telegram.yaml`, renseigner `chat_id` et passer `enabled` à `true`.
5. Recréer l’API et déclencher une collecte :

```bash
cd /home/vika/argos
docker compose up -d --build api
curl --fail -X POST http://127.0.0.1:1207/api/refresh
docker compose logs --since 10m api
```

`summarizer.max_output_tokens` dans `config/ai.yaml` fixe le budget de génération et est transmis à Ollama sous le nom natif `num_predict`. `summarizer.reasoning` vaut `false` afin que Qwen réserve ce budget au contenu final ; ce réglage évite une réponse vide après un raisonnement ayant consommé tous les tokens. `max_message_chars` dans `config/telegram.yaml` fixe séparément la taille maximale du message complet (3 900 par défaut, plafonnée à 4 000). Si cette validation échoue ou si la réponse est vide, Nyx réessaie jusqu’à trois fois avec un budget réduit ; Argos ne tronque pas le texte. `bot_token_env` désigne la variable d’environnement contenant le token.

## Reprise après erreur

Après le message accepté, Argos écrit l’empreinte du condensé dans `data/summary.telegram.sha256`. Si Telegram est inaccessible ou rejette le message, cette empreinte n’est pas modifiée : l’artefact reste en attente et sera retenté au prochain cycle sans nouvel appel Nyx. Un condensé déjà livré n’est pas renvoyé.

La réponse de santé n’expose ni token ni identifiant de conversation. Les erreurs persistées omettent également l’URL authentifiée de l’API Telegram. La progression Flux réserve 5 % au summarizer puis les 3 derniers pour l’envoi unique.
