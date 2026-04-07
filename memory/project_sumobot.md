---
name: SumoBot Hardware Config & Progress
description: Arduino Mega sumo bot - hardware, wiring, pin assignments, build phases, simulation and current progress
type: project
---

Projet de robot sumo sur Arduino Mega 2560.

## Hardware
- Moteurs: N20 12V 500RPM x2 (alimentes a 7.5V via batterie)
- Driver: L298N (jumper auto-alimentation active)
- Batterie: NiMH 7.5V
- Masse cible: ~500g
- Capteurs ligne: TCRT5000 x3 (2 avant coins + 1 arriere centre)
- Capteurs distance: VL53L0X x4 disponibles, 2 montes a l'avant en V (±15°), 2 en spare
- Buck converter: LM2596 (7.5V -> 5V)
- Shield sensor Mega (rangees S/V/G par pin)

## Pin Assignments
- ENA (PWM) -> Pin 10, IN1 -> Pin 9, IN2 -> Pin 8 (moteur gauche)
- ENB (PWM) -> Pin 5, IN3 -> Pin 6, IN4 -> Pin 7 (moteur droit)
- TCRT5000 #1 -> A0, #2 -> A1, #3 -> A2
- VL53L0X: SDA -> Pin 20, SCL -> Pin 21, XSHUT -> Pins 22, 23, 24

## Alimentation
- 7.5V direct -> L298N VCC -> moteurs (jumper auto-alim)
- 7.5V -> Buck -> 5V -> Arduino pin 5V (PAS VIN), capteurs, lasers
- GND commun partout

## Simulation
- simulation/index.html : simulateur visuel (HTML + JS Canvas, zero dependance)
- simulation/headless.js : simulateur headless Node.js pour tests massifs
- simulation/montecarlo.js : optimisation Monte Carlo des parametres
- Physique SI: masse 0.5kg, modele moteur N20 a 7.5V (couple stall 0.025 N.m, 312 RPM a vide)
- Traction limitee: mu=0.6, roues patinent a plein regime (stall force 1.63N > traction 1.47N)
- Sub-stepping physique a 240Hz, IA a 60Hz

### Ennemi basic
5 comportements aleatoires (WANDER, ORBIT, AGGRESSIVE, DODGE, ZIGZAG) a 85% PWM.

### Ennemi smart (--smart / touche S)
Omniscient, telecommande. 8 tactiques: FLANK, MATADOR, RUSH, SHADOW, EDGE_TRAP, JUKE, BULL, EXPLOIT_EVADE. Selection contextuelle par scoring pondere + 30% randomness. Smart ON par defaut dans index.html.

Realisme humain:
- Bruit steering ±6° par frame (joystick imprécis)
- Variation vitesse 82-100% (throttle pas constant)
- 12% chance hesitation 80-220ms au changement de tactique

## Strategie IA bot
WinRate: **95.5%** vs basic, **62%** vs smart (3000 rounds).

### Config
```
--kp 0.6 --searchPwm 0.95 --trackPwm 0.9 --evadePwm 0.85 --edgeSteer 0.5 --laserAngle 0.26 --centerReturnTime 0.35
```

### Fonctionnalites cles
1. **Capteurs avant en V (±15°)** : cone de detection 3x plus large.
2. **Edge-charge** : 1 seul capteur avant sur la ligne pendant CHARGE = continuer a pousser.
3. **CENTER_RETURN** : apres chaque EVADE, 0.35s de conduite vers le centre avant de reprendre SEARCH. Abort si ligne ou ennemi detecte. Parametre tunable (--centerReturnTime).

### Machine a etats
SEARCH -> TRACK -> CHARGE avec EVADE prioritaire (sauf edge-charge).
Apres EVADE -> CENTER (retour centre) -> SEARCH.
En SEARCH pres du bord (>50% rayon), arc vers le centre. Au centre, pure spin.

## Faiblesses revelees par smart enemy (2026-04-07)
1. **EDGE_TRAP (63% des pertes)**: ennemi entre bot et centre, gagne au timeout. CENTER_RETURN aide (+7%) mais pas suffisant.
2. **Attaques hors-cone (32%)**: RUSH/FLANK depuis angle mort ±15°.
3. **EVADE exploitable (<1%)**: timing fixe previsible (quasi resolu par center return).

### Pistes d'amelioration non testees
- Capteurs lateraux VL53L0X (spare x2) a seuil court (<200mm) pour detecter flanking
- Ne pas charger quand heading pointe vers l'exterieur pres du bord
- Mode "hold center" si match > 15s (priorite position vs combat)
- EVADE adaptatif (duree variable, direction vers centre)

## Progression (2026-04-07)
- Phase 0-2: OK - Alimentation, Arduino, moteurs testes
- Phase 3: EN COURS - capteurs ligne et distance
- Phase 4: A faire - integration strategie sumo sur Arduino
- Simulation visuelle + headless: DONE
- Monte Carlo: DONE
- Optimisation vs basic: DONE (95.5%)
- Smart enemy: DONE (bot a 62% WR avec realisme humain)
- CENTER_RETURN: DONE (+7% vs smart)

**Why:** Projet personnel de competition sumo bot, categorie 500g-1kg.
**How to apply:** Utiliser smart enemy pour guider les ameliorations capteurs/algo, puis porter sur Arduino.
