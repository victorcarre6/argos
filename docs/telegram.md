# Bot Telegram interactif

Telegram est la dernière étape de la collecte :

```text
RSS → SQLite/scoring → Chroma → plan thématique → rapports 1…N + 5 → sommaire Telegram
```

Le planificateur crée de un à quatre axes principaux et réserve toujours le numéro `5` à `Autre`. Chaque partie possède un fichier texte daté ; leur fusion Markdown constitue le rapport principal affiché dans Argos. Le sommaire envoyé au bot reprend les titres et les descriptions courtes du plan, puis invite l’utilisateur à répondre par un chiffre.

La fin du sommaire utilise une phrase de `config/sentences.yaml`, choisie aléatoirement avec `randint` lors de la génération, puis ajoute l’instruction fixe pour répondre par un numéro ou utiliser `/download`. Le fichier est optionnel : s’il est absent ou sans phrase exploitable, seule l’instruction fixe est ajoutée. La phrase intégrée à l’artefact reste inchangée lors d’une reprise d’envoi.

## Configuration

1. Créer le bot avec [@BotFather](https://t.me/BotFather).
2. Chaque destinataire envoie `/start` au bot, puis relève son `message.chat.id` via `getUpdates` avant de démarrer Argos.
3. Placer uniquement `TELEGRAM_BOT_TOKEN=<token>` dans le `.env` d’Atlas.
4. Déclarer les conversations autorisées :

```yaml
enabled: true
bot_token_env: "TELEGRAM_BOT_TOKEN"
chat_ids:
  user1: "123456789"
  user2: "987654321"
max_message_chars: 3900
```

L’ancien champ unique `chat_id` reste accepté. Après démarrage, ne plus appeler manuellement `getUpdates` : une seule boucle de long polling doit consommer les messages du bot.

## Commandes

- `/start` et `/help` affichent le mode d’emploi.
- `/download` envoie comme document le fichier Markdown complet du dernier rapport.
- `1` à `4` renvoie l’axe principal correspondant s’il existe.
- `5` renvoie `Autre`.
- Plusieurs chiffres peuvent être demandés successivement.
- Une demande vise toujours le dernier rapport généré, y compris après la réception d’un nouveau sommaire.

Seuls les `chat_ids` configurés reçoivent une réponse. Une partie longue est découpée aux limites de paragraphes en plusieurs messages, sans nouvel appel LLM.

## Persistance et reprise

`data/summary.telegram.sha256` marque le dernier sommaire livré à tous les destinataires. `data/summary.telegram.offset` conserve le prochain update Telegram à lire afin qu’un redémarrage ne rejoue pas les anciennes commandes. L’offset n’avance qu’après le traitement réussi du message courant.

Les artefacts datés sont `telegram_YYMMDD_HHMM.txt` pour le sommaire et `telegram_YYMMDD_HHMM_part_N.txt` pour les parties. Les tests associés sont dans [`tests/test_telegram.py`](../tests/test_telegram.py), [`tests/test_summary_agent.py`](../tests/test_summary_agent.py) et [`tests/test_reports.py`](../tests/test_reports.py).

Lors d’une remise à zéro manuelle, arrêter d’abord le service API avant de supprimer SQLite, Chroma, rapports ou fichiers `summary.*`; supprimer une base ouverte peut provoquer une erreur SQLite `readonly database` ou `code 1032`. Les purges ordinaires doivent passer par Config.
