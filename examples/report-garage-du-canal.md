# Tests de l'agent — Garage du Canal

**5/5 scénarios réussis** · latence réseau : 110 ms médiane (ping websocket)

## ✅ Réservation complète d'une vidange

```
🤖 Garage du Canal, bonjour ! Je suis Léa, l'assistante. Je peux vous aider à prendre un rendez-vous ?
🧑 Bonjour, je voudrais faire une vidange demain matin.
🤖 Bonjour ! Demain, c'est le mardi 6 octobre. Je regarde les disponibilités pour une vidange.
  ⚙ check_availability({'service': 'vidange', 'date': '2026-10-06'}) -> {"ok": true, "date": "mardi 06/10", "service": "vidange", "duration_min": 30, "suggested_slots": ["08:30", "10:30", "14:15", "16:15"], "total_available": 32}
🤖 Alors, pour une vidange demain matin, mardi six octobre, j'ai un créneau à huit heures trente et un autre à dix heures trente. Lequel vous arrange le mieux ?
🧑 Neuf heures, c'est possible ?
🤖 D'accord, je vérifie si neuf heures est disponible pour la vidange demain.
  ⚙ check_availability({'service': 'vidange', 'date': '2026-10-06', 'time': '09:00'}) -> {"ok": true, "date": "mardi 06/10", "service": "vidange", "duration_min": 30, "suggested_slots": ["08:30", "10:30", "14:15", "16:15"], "total_available": 32, "requested_time": "09:00", "requested_time_available": true}
🤖 Oui, c'est tout à fait possible ! Neuf heures, c'est libre pour une vidange demain, mardi six octobre. On le prend ?
🧑 Jeanne Martin, 06 12 34 56 78, et ma plaque c'est AB-123-CD.
🤖 Parfait ! Donc, c'est un rendez-vous pour une vidange demain, mardi six octobre, à neuf heures, au nom de Jeanne Martin, avec le numéro zéro six, douze, trente-quatre, cinquante-six, soixante-dix-huit, et la plaque AB-123-CD. C'est bien ça ?
🧑 Oui, c'est parfait.
🤖 Super ! Je vous enregistre ça tout de suite.
  ⚙ book_appointment({'service': 'vidange', 'date': '2026-10-06', 'time': '09:00', 'customer_name': 'Jeanne Martin', 'phone': '***', 'extra': 'AB-123-CD'}) -> {"ok": true, "confirmation_code": "8UQGL", "spelled_code": "8 U Q G L", "date": "mardi 06/10", "time": "09:00", "service": "vidange"}
🤖 Votre rendez-vous est confirmé ! Le code de confirmation est Huit, U, Q, G, L.
🧑 Non merci, au revoir.
🤖 Merci de votre appel et à bientôt au Garage du Canal !
```

## ✅ Créneau déjà pris, l'agent propose une alternative

```
🤖 Garage du Canal, bonjour ! Je suis Léa, l'assistante. Je peux vous aider à prendre un rendez-vous ?
🧑 J'ai un voyant moteur allumé, je peux passer demain à neuf heures pour un diagnostic ?
🤖 Bien sûr. Je vérifie si le garage est disponible pour un diagnostic demain, mardi 6 octobre, à neuf heures.
  ⚙ check_availability({'service': 'diagnostic', 'date': '2026-10-06', 'time': '09:00'}) -> {"ok": true, "date": "mardi 06/10", "service": "diagnostic", "duration_min": 60, "suggested_slots": ["10:00", "11:30", "15:15", "16:45"], "total_available": 22, "requested_time": "09:00", "requested_time_available": false, "closest_slots": ["10:00"]}
🧑 D'accord, alors le premier créneau libre après.
🤖 Le premier créneau disponible pour un diagnostic demain, mardi 6 octobre, est à dix heures. Est-ce que cela vous convient ?
🧑 Paul Durand, 07 98 76 54 32, plaque EF-456-GH.
🤖 D'accord, je récapitule : un diagnostic pour demain, mardi 6 octobre, à dix heures, au nom de Paul Durand, avec le numéro zéro sept, quatre-vingt-dix-huit, soixante-seize, cinquante-quatre, trente-deux, et la plaque EF-456-GH. C'est bien ça ?
🧑 Oui, je confirme.
🤖 Parfait ! Je procède à la réservation.
  ⚙ book_appointment({'service': 'diagnostic', 'date': '2026-10-06', 'time': '10:00', 'customer_name': 'Paul Durand', 'phone': '***', 'extra': 'EF-456-GH'}) -> {"ok": true, "confirmation_code": "N3SPH", "spelled_code": "N 3 S P H", "date": "mardi 06/10", "time": "10:00", "service": "diagnostic"}
🤖 C'est noté ! Votre rendez-vous pour un diagnostic est confirmé pour demain, mardi 6 octobre, à dix heures. Votre code de confirmation est N 3 S P H. Je vous souhaite une bonne journée.
```

## ✅ Demande un dimanche

```
🤖 Garage du Canal, bonjour ! Je suis Léa, l'assistante. Je peux vous aider à prendre un rendez-vous ?
🧑 Est-ce que je peux venir dimanche pour changer mes pneus ?
🤖 Bonjour ! Alors, le dimanche, le garage est fermé. On est ouverts du lundi au samedi. Ça vous dirait de venir un autre jour ?
```

## ✅ Pas de réservation sans confirmation

```
🤖 Garage du Canal, bonjour ! Je suis Léa, l'assistante. Je peux vous aider à prendre un rendez-vous ?
🧑 Je veux une révision jeudi à quatorze heures.
  ⚙ check_availability({'service': 'revision', 'date': '2026-10-08', 'time': '14:00'}) -> {"ok": true, "date": "jeudi 08/10", "service": "revision", "duration_min": 90, "suggested_slots": ["08:30", "10:00", "14:15", "15:45"], "total_available": 24, "requested_time": "14:00", "requested_time_available": true}
🤖 Super ! Jeudi huit octobre à quatorze heures, c'est libre pour une révision. Ça vous va ?
🧑 Marc Petit, 06 11 22 33 44, plaque IJ-789-KL.
🤖 Parfait, je vous note pour une révision le jeudi huit octobre à quatorze heures. C'est bien ça ?
🧑 Attendez, finalement je vais en parler à ma femme, je rappellerai.
🤖 D'accord, pas de souci. N'hésitez pas à nous rappeler quand vous voulez. Bonne journée !
```

## ✅ Demande hors périmètre (devis)

```
🤖 Garage du Canal, bonjour ! Je suis Léa, l'assistante. Je peux vous aider à prendre un rendez-vous ?
🧑 Combien ça coûterait de changer l'embrayage d'une Clio 4 ?
🤖 Ah, l'embrayage d'une Clio 4, c'est une opération un peu plus complexe. Je n'ai pas les tarifs pour ça sous la main. Si vous voulez, je peux demander à un conseiller de vous rappeler pour vous faire un devis précis ?
```
