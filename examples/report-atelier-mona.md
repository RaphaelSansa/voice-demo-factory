# Tests de l'agent — Atelier Mona

**3/3 scénarios réussis** · latence réseau : 110 ms médiane (ping websocket)

## ✅ Coupe femme samedi

```
🤖 Atelier Mona, bonjour ! Je suis Camille, l'assistante. Je peux vous aider à prendre un rendez-vous ?
🧑 Bonjour, je voudrais une coupe femme samedi matin.
🤖 Bonjour, je peux regarder les disponibilités pour une coupe femme ce samedi 10 octobre. À quelle heure souhaiteriez-vous venir ?
🧑 Dix heures, s'il vous plaît.
  ⚙ check_availability({'service': 'coupe_femme', 'date': '2026-10-10', 'time': '10:00'}) -> {"ok": true, "date": "samedi 10/10", "service": "coupe_femme", "duration_min": 45, "suggested_slots": ["09:00", "11:15", "13:30", "15:45"], "total_available": 34, "requested_time": "10:00", "requested_time_available": true}
🤖 Oui, c'est tout à fait possible. Le samedi dix octobre à dix heures, c'est libre pour une coupe femme. Pourriez-vous me donner votre nom et votre numéro de téléphone, s'il vous plaît ?
🧑 Claire Bernard, 06 55 44 33 22.
🤖 Très bien, je récapitule : une coupe femme ce samedi dix octobre à dix heures, au nom de Claire Bernard. Votre numéro de téléphone est le zéro six, cinquante-cinq, quarante-quatre, trente-trois, vingt-deux. Est-ce bien cela ?
🧑 Oui, parfait.
  ⚙ book_appointment({'service': 'coupe_femme', 'date': '2026-10-10', 'time': '10:00', 'customer_name': 'Claire Bernard', 'phone': '***'}) -> {"ok": true, "confirmation_code": "HZXCX", "spelled_code": "H Z X C X", "date": "samedi 10/10", "time": "10:00", "service": "coupe femme"}
🤖 C'est noté. Votre rendez-vous est confirmé. Le code de confirmation est H Z X C X.
```

## ✅ Salon fermé le lundi

```
🤖 Atelier Mona, bonjour ! Je suis Camille, l'assistante. Je peux vous aider à prendre un rendez-vous ?
🧑 Vous avez de la place aujourd'hui pour une couleur ?
🤖 Je suis désolée, le salon est fermé le lundi. Je ne pourrai pas vous proposer de rendez-vous pour une couleur aujourd'hui.
```

## ✅ Question pratique, pas de réservation

```
🤖 Atelier Mona, bonjour ! Je suis Camille, l'assistante. Je peux vous aider à prendre un rendez-vous ?
🧑 Vous utilisez des produits testés sur les animaux ?
🤖 Non, nous n'utilisons aucun produit testé sur les animaux. Notre gamme est entièrement végane.
```
