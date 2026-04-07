---
name: Simulation physics integrity
description: Simulation must use honest sensor-only AI and real physics - no omniscient shortcuts
type: feedback
---

Le bot ne doit utiliser QUE les donnees de ses capteurs (lasers VL53L0X en mm, TCRT5000 ligne). Pas de triche avec atan2 vers l'ennemi ou acces direct a la position adverse.

**Why:** Bruno a detecte que le mode SEARCH utilisait atan2(ene.y - bot.y, ...) pour s'orienter — ce n'est pas realiste. Un vrai robot tourne a l'aveugle jusqu'a ce qu'un laser detecte quelque chose.

**How to apply:** En mode SEARCH, rotation a vitesse fixe (spin aveugle). Toute logique de centrage/tracking doit passer par les lectures laser d1/d2. Les VL53L0X donnent des distances en mm — utiliser cette unite dans l'IA.
