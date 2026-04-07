---
name: Strategy Optimization Results - What Works and What Doesn't
description: Detailed log of all tested strategies and parameter changes with measured impact - prevents re-testing failed approaches
type: feedback
---

## POSITIF (garder, ne pas reverter)

### 3 lasers avant (centre + 2 lateraux en V) — IMPACT MAJEUR
- Ancien: 2 lasers a ±0.26 rad, kp=0.6 → 86.9% pondere multi-taille
- Nouveau: 3 lasers (centre droit + lateraux ±0.47 rad), kp=1.28 → **95.1% pondere** (+8.2%)
- Le laser central comble le trou entre les lateraux. Quand il detecte mais pas un lateral, sa distance + centerFill (165mm) remplace le lateral manquant.
- Avec le centre, on peut aller a ±27° sans degradation (ancien max etait ±17° sans centre).
- Robustesse multi-taille : S(35mm)=94.4%, D(55mm)=95.2%, XL(75mm)=95.3%. L'ancien s'effondrait a 78% sur XL.
- Monte Carlo v2 confirme: kp=0.6-1.3, laserAngle=0.40-0.48, centerFill=140-280 sont tous au plafond (94-95%).

### Edge-charge (ne pas EVADE sur 1 seul capteur avant pendant CHARGE) — IMPACT MAJEUR
- **+2-3% WR, timeouts /2** (de 26% a ~13%)
- Logique: si CHARGE/TRACK actif + ennemi detecte devant + 1 seul capteur avant sur la ligne → continuer a pousser avec correction de direction (edgeSteer).
- EVADE seulement si: les 2 capteurs avant sont dans le blanc, OU capteur arriere, OU pas en engagement.
- edgeSteer: 0.3/0.5/0.7 donnent des resultats quasi identiques. Le facteur cle est de NE PAS declencher EVADE.

### searchPwm=0.95 — impact modere
- +1% WR vs 0.75. Spin plus rapide = balayage plus rapide.
- 1.0 ne fait pas mieux que 0.95.

### trackPwm=0.9 — impact modere
- +1% WR vs 0.8. Ferme la distance plus vite.
- 0.95 est trop agressif (leger recul).

### evadePwm=0.85 — impact leger
- Reduit timeouts de ~2%. Evade plus rapide = retour au combat plus vite.

## NEGATIF (ne PAS re-tester)

### Capteurs lateraux a 90° — TOUJOURS NEGATIF
Teste sous 5 formes differentes, toutes pires que baseline:
1. **PIVOT state (spin pur vers detection laterale)** : 78.2% WR. Le bot oscille entre PIVOT et SEARCH.
2. **Direction hint continu** : 79.7% WR. Les lateraux detectent presque toujours (800mm portee, arene 385mm rayon) → flip-flop constant.
3. **Single-shot hint (1ere frame seulement)** : 88.2% WR. Neutre vs baseline.
4. **Close-range acquire (<250mm)** : 80.9% WR. ACQUIRE bloquant.
5. **Curved flank approach** : 83.4% WR. Toujours du drift parasite.
**Why:** Dans une arene de 77cm, le temps de rotation 90° pour face-to-face est trop long — l'ennemi bouge pendant le pivot. La portee 800mm cause des detections perpetuelles.

### Arc search (forward + spin au centre) — NEGATIF
- Derive hors portee laser. Le bot s'eloigne de la zone optimale.
- Teste avec fwdBias de 0.2 et 0.3: toujours pire.

### PD controller (ajout de kd) — CATASTROPHIQUE
- Amplifie le bruit laser → instabilite totale.

### Last-known direction search — NEUTRE
- La direction est perimee apres EVADE (le heading change). 89.6% vs 89.1% baseline = bruit statistique.

### Search direction reversal (inverser tous les 2-2.5s) — NEGATIF
- Empeche de completer un sweep complet. Combiné avec d'autres: toujours pire.

### Progressive speed ramp — NEUTRE/NEGATIF
- Perte tracking a mi-distance.

### chargePwm < 1.0 — TOUJOURS NEGATIF
- Force brute > precision en charge.

### chargeThreshold=300 — NEUTRE
- 88.4% vs 89.1% baseline. Pas de gain significatif.

### evade times plus courts (0.35/0.25) — NEGATIF
- 88.3% WR. Le bot ne recule pas assez loin du bord.

## Monte Carlo (150 configs, revalidation top 10 a 3000 rounds)
- Confirme que la config manuelle (kp=0.6, searchPwm=0.95, trackPwm=0.9, evadePwm=0.85, laserAngle=0.26) est au plafond.
- Aucune config random n'a battu le manual a 5000 rounds.
- Les parametres sont robustes: des configs tres differentes (kp 0.33-0.97) donnent toutes 93-95%.
- **Conclusion: c'est l'algo (edge-charge, laser V) qui drive la performance, pas le fine-tuning.**

**How to apply:** Avant de tester un changement, verifier ici qu'il n'a pas deja ete teste. Pour aller au-dela de 95%, il faut un changement structurel (nouveau capteur, nouvelle logique), pas du tuning.
