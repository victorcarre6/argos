# Livraison du rapport par Telegram

Telegram est exclusivement la dernière étape de la collecte :

```text
RSS → SQLite et scoring → embeddings Chroma → synthèse LangGraph → Telegram
```

Argos n’envoie plus d’alertes article par article. Après la génération, le contenu complet de `data/summary.md` est envoyé comme message texte. Les rapports dépassant la limite Telegram sont découpés aux frontières de paragraphes, puis de lignes ou de mots.

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

`max_message_chars` fixe la taille maximale visée pour chaque fragment (3 900 par défaut). `bot_token_env` désigne la variable d’environnement contenant le token.

## Reprise après erreur

Après le dernier fragment accepté, Argos écrit l’empreinte du rapport dans `data/summary.telegram.sha256`. Si Telegram est inaccessible ou rejette un fragment, cette empreinte n’est pas modifiée : le rapport reste visible comme étant en attente et sera retenté après la synthèse du prochain cycle manuel ou automatique. Un rapport déjà livré n’est jamais renvoyé tant que `summary.md` ne change pas.

La réponse de santé n’expose ni token ni identifiant de conversation. Les erreurs persistées omettent également l’URL authentifiée de l’API Telegram. La progression Flux réserve les derniers 5 % de la pipeline à cette livraison et avance fragment par fragment.
