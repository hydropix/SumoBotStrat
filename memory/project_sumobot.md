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
- Capteurs distance: VL53L0X x4 disponibles, 3 montes a l'avant (1 centre droit + 2 lateraux ±27°), 1 en spare
- IMU: MPU6050 (prevu, pas encore monte). Adresse I2C 0x68, partage bus avec VL53L0X. INT sur pin 2 ou 3.
- Buck converter: LM2596 (7.5V -> 5V)
- Shield sensor Mega (rangees S/V/G par pin)

## Pin Assignments

- ENA (PWM) -> Pin 10, IN1 -> Pin 9, IN2 -> Pin 8 (moteur gauche)
- ENB (PWM) -> Pin 5, IN3 -> Pin 6, IN4 -> Pin 7 (moteur droit)
- TCRT5000 #1 -> A0, #2 -> A1, #3 -> A2
- VL53L0X: SDA -> Pin 20, SCL -> Pin 21, XSHUT -> Pins 22, 23, 24
- MPU6050: SDA -> Pin 20, SCL -> Pin 21 (partage I2C), INT -> Pin 2

## Alimentation

- 7.5V direct -> L298N VCC -> moteurs (jumper auto-alim)
- 7.5V -> Buck -> 5V -> Arduino pin 5V (PAS VIN), capteurs, lasers
- GND commun partout

## Simulation — Ce que le systeme modelise

### Fichiers

- simulation/index.html : simulateur visuel (HTML + JS Canvas, zero dependance)
- simulation/headless.js : simulateur headless Node.js pour tests massifs
- simulation/montecarlo.js : optimisation Monte Carlo v1 (2 lasers, obsolete)
- simulation/montecarlo_v2.js : Monte Carlo v2, multi-profil ennemi (taille/masse/vitesse)

### Physique (identique headless et html)

- **Moteurs N20** : modele force-vitesse lineaire, couple stall 0.025 N.m, 312 RPM a vide a 7.5V
- **Traction per-wheel** : mu=0.6, chaque roue a sa propre limite de traction. Stall force 1.63N > traction 1.47N = patinage a plein regime
- **Masse/vitesse per-robot** : chaque robot a ses propres mass, inertia, stallForce, noLoadSpeed, tractionMax
- **Collision** : impulsions avec restitution 0.15, masses individuelles
- **Tilt per-wheel (soulevement directionnel)** :
  - Continu tant que l'attaquant pousse (base sur vitesse de fermeture + force moteur, pas juste l'impact)
  - Direction: cote = souleve la roue du cote impacte. Arriere = les 2 roues. Face a face = pas de tilt (lames s'opposent)
  - Effet: traction de la roue soulevee chute (x1.8 par rad de tilt), la roue au sol garde sa traction → le bot pivote
  - Decay: 3.0 rad/s (~0.23s pour retomber completement)
  - Perspective visuelle: cote souleve = plus grand (plus proche camera), cote au sol = plus petit, trapeze
- **Friction laterale** : forte (30 s⁻¹), empeche le derapage lateral. Reduite par le tilt.
- **Sub-stepping** : physique a 240Hz, IA a 60Hz

### Capteurs simules

- **3x VL53L0X avant** : 1 centre (0°) + 2 lateraux (±27°). Raycasting sur le cercle de collision ennemi. Portee 800mm.
- **centerFill** : si centre detecte mais pas un lateral, d0 + 165mm remplace le lateral manquant.
- **3x TCRT5000 ligne** : detection du bord blanc (2 avant coins, 1 arriere centre)
- **IMU (MPU6050) simule** :
  - Accelerometre (ax, ay) : calcule depuis delta vitesse dans le referentiel robot, en m/s²
  - Gyroscope (gz) : omega du robot en rad/s. Heading cumule par integration.
  - Tilt : lu depuis tiltL/tiltR du modele physique

### Ennemi

- **Basic** : 5 comportements aleatoires (WANDER, ORBIT, AGGRESSIVE, DODGE, ZIGZAG) a 85% PWM
- **Smart** (--smart / touche S) : omniscient, 8 tactiques (FLANK, MATADOR, RUSH, SHADOW, EDGE_TRAP, JUKE, BULL, EXPLOIT_EVADE). Scoring pondere + 30% randomness. Realisme humain: bruit steering ±6°, vitesse 82-100%, 12% hesitation.
- **Taille variable** (touche V) : taille 35-75mm, masse 0.3-0.8kg, vitesse 70-130% randomises a chaque round
- L'ennemi subit aussi le tilt (il peut etre souleve par le bot)

### IA du bot — Machine a etats

SEARCH → TRACK → CHARGE (+ EVADE prioritaire sauf edge-charge)
Apres EVADE → CENTER (retour centre 0.35s) → SEARCH
Etats IMU: TILT_ESC (recul si tilt >14°), IMPACT (spin vers source si choc lateral >1.5g)
Heading search: apres 360° de spin sans detection, deplacement vers le centre

### Config actuelle

```text
kp=1.0  laserAngle=0.47  centerFill=165  searchPwm=0.954
trackPwm=1.0  evadePwm=1.0  edgeSteer=0.245  chargeThreshold=300
centerReturnTime=0.35
```

## Resultats

- **91.2% pondere multi-profil** vs basic (3000 rounds, 8 profils taille/masse/vitesse)
- **74.6%** vs smart enemy avec IMU+tilt (+1.8% vs sans IMU)
- Pertes FLANK reduites de 18% grace a IMU (detection impact lateral)
- Contre ennemi 0.8kg+130% vitesse (~2x momentum): WR plafonne a ~67% (limite physique)

## Faiblesses restantes

1. **EDGE_TRAP (~60% des pertes vs smart)**: ennemi entre bot et centre, gagne au timeout
2. **Attaques hors-cone (~30%)**: RUSH/FLANK depuis angles morts, partiellement resolu par IMU
3. Pas de capteur arriere (VL53L0X spare disponible)
4. Pas de capteurs ligne lateraux

### Pistes d'amelioration

- VL53L0X arriere (spare dispo, cout 0) → elimine angle mort arriere
- 2x TCRT5000 lateraux → survie edge-trap
- Ne pas charger quand heading pointe vers l'exterieur pres du bord
- Mode "hold center" si match > 15s
- 2x IR LED+phototransistor flancs (detection laterale rapide)

## Progression (2026-04-07)

- Phase 0-2: OK - Alimentation, Arduino, moteurs testes
- Phase 3: EN COURS - capteurs ligne et distance
- Phase 4: A faire - integration strategie sumo sur Arduino
- Simulation visuelle + headless: DONE
- Monte Carlo v1 + v2: DONE
- 3e laser central: DONE
- Tilt per-wheel + IMU simule: DONE
- Physique per-robot (masse/vitesse/taille variable): DONE
- Smart enemy: DONE
- CENTER_RETURN: DONE

**Why:** Projet personnel de competition sumo bot, categorie 500g-1kg.
**How to apply:** Utiliser smart enemy + taille variable pour guider les ameliorations capteurs/algo, puis porter sur Arduino.
