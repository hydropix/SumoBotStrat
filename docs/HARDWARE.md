# Guide de montage hardware — SumoBot

Guide complet pour assembler le robot sumo de competition (categorie 500g-1kg) base sur Arduino Mega 2560.

## Liste des composants

| Composant | Modele | Quantite | Role |
| --------- | ------ | -------- | ---- |
| Microcontroleur | Arduino Mega 2560 | 1 | Cerveau du robot |
| Shield capteurs | Sensor Shield Mega | 1 | Distribution alimentation + connexion capteurs |
| Pont H | L298N | 1 | Pilotage moteurs |
| Moteurs DC | N20 12V 500RPM avec reducteur | 2 | Propulsion |
| Roues | Roues silicone pour N20 | 2 | Adherence sur dohyo |
| Roulette | Bille folle ou roulette omnidirectionnelle | 1 | Point d'appui arriere |
| Capteur distance | VL53L0X (breakout) | 3 | Detection ennemi (laser ToF) |
| Capteur ligne | TCRT5000 | 3 | Detection bordure blanche |
| IMU | MPU6050 (breakout) | 1 | Acceleration + gyroscope |
| Batterie | NiMH 7.2V 1100-1500mAh | 1 | Alimentation principale |
| Regulateur | Buck LM2596 (module reglable) | 1 | Conversion 7.2V → 5V |
| Bouton | Poussoir momentane | 1 | Demarrage match |
| Connecteurs | JST, Dupont, bornier a vis | - | Cablage |

## Schema d'alimentation

```text
Batterie NiMH 7.2V
    |
    +---> L298N (bornier 12V) ---- alimente les moteurs directement
    |         |
    |         +-- Jumper 5V ENLEVE (on utilise le buck externe)
    |
    +---> Buck LM2596 (Vin)
              |
              +-- Vout regle a 5.0V (mesurer au multimetre !)
              |
              +---> Arduino Mega pin 5V (PAS Vin, PAS barrel jack)
              +---> Shield capteurs (alimente VL53L0X, TCRT5000, MPU6050)
```

**ATTENTION** : Ne JAMAIS brancher 7.2V sur le pin 5V de l'Arduino. Toujours passer par le buck LM2596 regle a 5.0V.

### Reglage du LM2596

1. Brancher la batterie sur Vin du module LM2596
2. **Sans charge** (rien branche sur Vout), tourner le potentiometre avec un tournevis
3. Mesurer Vout au multimetre → ajuster a 5.0V (+/- 0.1V)
4. Brancher sur Arduino pin 5V seulement apres verification

## Cablage moteurs — L298N

### Connexions L298N → Arduino

```text
L298N              Arduino Mega
-----              -----------
ENA  ------------> Pin 10 (PWM)     Vitesse moteur gauche
IN1  ------------> Pin 9            Direction moteur gauche
IN2  ------------> Pin 8            Direction moteur gauche
IN3  ------------> Pin 6            Direction moteur droit
IN4  ------------> Pin 7            Direction moteur droit
ENB  ------------> Pin 5 (PWM)      Vitesse moteur droit
GND  ------------> GND Arduino
```

### Connexions L298N → Moteurs

```text
L298N              Moteurs N20
-----              ----------
OUT1, OUT2 ------> Moteur GAUCHE (2 fils)
OUT3, OUT4 ------> Moteur DROIT (2 fils)
12V  <------------ Batterie 7.2V (+)
GND  <------------ Batterie 7.2V (-)
```

### Jumper 5V du L298N

Le L298N a un jumper "5V enable" qui active son regulateur interne. **Enlever ce jumper** car on utilise le buck LM2596 externe pour alimenter l'Arduino. Le regulateur interne du L298N n'est pas assez fiable pour alimenter le Mega + tous les capteurs.

### Sens de rotation

Si un moteur tourne a l'envers, il suffit d'inverser ses 2 fils sur les borniers OUT du L298N. Pas besoin de modifier le code.

### Verification

Utiliser le sketch `test_moteur1/test_moteur1.ino` pour tester un moteur, puis `test_2moteurs/test_2moteurs.ino` pour tester les deux moteurs ensemble (avant, arriere, rotation gauche, rotation droite).

## Cablage capteurs de ligne — TCRT5000

Les TCRT5000 sont des capteurs infrarouge reflexifs. Ils renvoient une tension analogique basse sur surface blanche (bordure du dohyo) et haute sur surface noire (aire de combat).

### Connexions

```text
TCRT5000           Shield Sensor Mega (section ANALOG)
--------           ----------------------------------
Capteur #1 (avant-gauche)  --> A0 (S/V/G)
Capteur #2 (avant-droit)   --> A1 (S/V/G)
Capteur #3 (arriere)       --> A2 (S/V/G)
```

Sur le shield sensor Mega, chaque pin analogique a 3 broches alignees :

- **S** (Signal) : fil de signal du TCRT5000
- **V** (VCC) : 5V (alimente par le shield)
- **G** (GND) : masse

**IMPORTANT** : Brancher sur la section **ANALOG** du shield, pas sur la section PWM/Digital. Les deux se ressemblent, mais les pins analogiques sont sur le cote oppose.

### Placement physique

```text
        AVANT DU ROBOT
   ┌─────────────────────┐
   │  [TCRT#1]   [TCRT#2]│   <- Avant-gauche (A0) et avant-droit (A1)
   │      (A0)     (A1)  │      Montes a ~5mm du sol, depassant du chassis
   │                      │      de 5-10mm vers l'avant
   │                      │
   │                      │
   │       [TCRT#3]       │   <- Arriere (A2)
   │         (A2)         │      Monte au centre arriere
   └─────────────────────┘
        ARRIERE DU ROBOT
```

### Calibration

Le seuil par defaut est 300 (sur 1023). Valeur analogique :

- **< 300** : surface blanche (bordure) → DANGER, reculer
- **> 300** : surface noire (ring) → OK

Pour calibrer sur votre ring : utiliser `test_capteur_ligne/test_capteur_ligne.ino` et noter les valeurs lues sur le Serial Monitor (9600 baud) pour le blanc et le noir. Le seuil doit etre au milieu des deux valeurs.

## Cablage capteurs de distance — VL53L0X

Les VL53L0X sont des capteurs laser Time-of-Flight communiquant en I2C. Portee utile : ~800mm. Le robot en utilise 3 pour couvrir un cone de detection d'environ 60 degres.

### Probleme d'adresse I2C

Tous les VL53L0X ont la meme adresse I2C par defaut (0x29). Pour en utiliser 3 sur le meme bus, on utilise les pins XSHUT pour les allumer sequentiellement et leur attribuer des adresses uniques au demarrage.

### Connexions

```text
VL53L0X            Arduino Mega
-------            -----------
Tous les VL53L0X :
  VIN  ----------> 5V (via shield)
  GND  ----------> GND
  SDA  ----------> Pin 20 (SDA)
  SCL  ----------> Pin 21 (SCL)

XSHUT individuels :
  VL53L0X #0 (centre)  XSHUT --> Pin 22
  VL53L0X #1 (gauche)  XSHUT --> Pin 23
  VL53L0X #2 (droite)  XSHUT --> Pin 24
```

### Placement physique

```text
        AVANT DU ROBOT (vue de dessus)
              ┌───┐
             /  0  \          Laser #0 : centre, droit devant
            /       \
      ┌───┐           ┌───┐
      | 1 |           | 2 |  Laser #1 : gauche (~30 deg)
      └───┘           └───┘  Laser #2 : droite (~30 deg)
```

L'angle optimal entre les lasers lateraux et le centre est **~30 degres** (0.526 rad). C'est le resultat de l'optimisation Monte Carlo — des angles plus larges (60-90 deg) perdent la cible trop facilement.

### Sequence d'initialisation

Le code dans `sumo_strategy.ino` fait automatiquement :

1. Mettre les 3 XSHUT a LOW (tous les capteurs eteints)
2. Activer XSHUT #0 → init laser0 → adresse 0x30
3. Activer XSHUT #1 → init laser1 → adresse 0x31
4. Activer XSHUT #2 → init laser2 → adresse 0x32
5. Mode continu a 20ms par mesure (rapide)

### Recovery I2C

Si les 3 lasers tombent en timeout simultanement (bus I2C bloque), le code execute un recovery automatique : 16 clocks manuelles sur SCL puis reinitialisation complete.

## Cablage IMU — MPU6050

Le MPU6050 fournit les accelerations (chocs, soulèvement) et le gyroscope (rotation). Il partage le bus I2C avec les VL53L0X.

### Connexions

```text
MPU6050            Arduino Mega
-------            -----------
VCC  ------------> 5V (via shield)
GND  ------------> GND
SDA  ------------> Pin 20 (SDA)
SCL  ------------> Pin 21 (SCL)
AD0  ------------> GND (adresse 0x68, pas de conflit avec VL53L0X)
```

### Donnees utilisees par l'IA

| Donnee MPU6050 | Utilisation |
| -------------- | ----------- |
| Acceleration X (avant/arriere) | Detection collision frontale (counter-dodge si < -18.8 m/s2) |
| Acceleration Y (laterale) | Detection impact lateral (spin si \|ay\| > 15 m/s2), direction de tilt |
| Gyroscope Z (vitesse angulaire) | Integration heading pour scan 360 deg en mode SEARCH |

## Bouton START

### Connexion

```text
Bouton             Arduino Mega
------             -----------
Broche 1 --------> Pin 2
Broche 2 --------> GND
```

Le pin 2 utilise le pull-up interne de l'Arduino (`INPUT_PULLUP`). Pas besoin de resistance externe. Le bouton est lu comme LOW quand presse.

### Fonctionnement

1. Robot sous tension → etat WAIT_START (LED clignote lentement)
2. Appui bouton → COUNTDOWN 5 secondes (LED clignote rapidement, reglementaire)
3. Fin countdown → GO, l'IA demarre en mode SEARCH

## Schema de cablage complet

```text
                    ┌─────────────────────┐
                    │   BATTERIE NiMH     │
                    │      7.2V           │
                    └────┬───────┬────────┘
                         │       │
                    (+)  │       │  (-)
                         │       │
              ┌──────────┤       ├──────────────────────┐
              │          │       │                      │
              v          v       v                      v
        ┌──────────┐  ┌────────────┐             ┌──────────┐
        │  L298N   │  │  LM2596    │             │   GND    │
        │  12V in  │  │  Vin       │             │  commun  │
        │          │  │  Vout=5V   │             │          │
        │ OUT1,2 ──┼──┼─> Mot. G  │             │          │
        │ OUT3,4 ──┼──┼─> Mot. D  │             │          │
        │          │  │            │             │          │
        │ ENA ─────┼──┼─> Mega 10 │             │          │
        │ IN1 ─────┼──┼─> Mega 9  │             │          │
        │ IN2 ─────┼──┼─> Mega 8  │             │          │
        │ IN3 ─────┼──┼─> Mega 6  │             │          │
        │ IN4 ─────┼──┼─> Mega 7  │             │          │
        │ ENB ─────┼──┼─> Mega 5  │             │          │
        └──────────┘  └─────┬──────┘             │          │
                            │ 5V                 │          │
                            v                    │          │
                   ┌──────────────────┐          │          │
                   │  ARDUINO MEGA    │          │          │
                   │  (pin 5V)        │<─────────┘          │
                   │                  │     GND             │
                   │  SHIELD SENSOR   │                     │
                   │  ┌─────────────┐ │                     │
                   │  │A0 ← TCRT #1│ │                     │
                   │  │A1 ← TCRT #2│ │                     │
                   │  │A2 ← TCRT #3│ │                     │
                   │  │20 SDA ─────┼─┼──> VL53L0X x3       │
                   │  │21 SCL ─────┼─┼──> + MPU6050        │
                   │  │22 XSHUT #0 │ │                     │
                   │  │23 XSHUT #1 │ │                     │
                   │  │24 XSHUT #2 │ │                     │
                   │  │ 2 ← BTN   │ │                     │
                   │  │13 → LED   │ │                     │
                   │  └─────────────┘ │                     │
                   └──────────────────┘                     │
                                                            │
                    Tous les GND relies ensemble ───────────┘
```

## Tableau recapitulatif du pinout

| Pin Arduino | Fonction | Composant |
| ----------- | -------- | --------- |
| 2 | Bouton START | Poussoir → GND |
| 5 | ENB (PWM moteur droit) | L298N |
| 6 | IN3 (direction moteur droit) | L298N |
| 7 | IN4 (direction moteur droit) | L298N |
| 8 | IN2 (direction moteur gauche) | L298N |
| 9 | IN1 (direction moteur gauche) | L298N |
| 10 | ENA (PWM moteur gauche) | L298N |
| 13 | LED etat | LED onboard |
| 20 (SDA) | Bus I2C data | VL53L0X x3 + MPU6050 |
| 21 (SCL) | Bus I2C clock | VL53L0X x3 + MPU6050 |
| 22 | XSHUT laser centre | VL53L0X #0 |
| 23 | XSHUT laser gauche | VL53L0X #1 |
| 24 | XSHUT laser droite | VL53L0X #2 |
| A0 | Capteur ligne avant-gauche | TCRT5000 #1 |
| A1 | Capteur ligne avant-droit | TCRT5000 #2 |
| A2 | Capteur ligne arriere | TCRT5000 #3 |
| 5V | Alimentation 5V (depuis buck) | LM2596 Vout |
| GND | Masse commune | Tous composants |

## Ordre de montage recommande

### Etape 1 — Alimentation

1. Souder les fils de la batterie NiMH (connecteur adapte, pas de soudure directe sur les cellules)
2. Brancher le buck LM2596 : Vin sur batterie, regler Vout a 5.0V au multimetre
3. Connecter Vout du buck sur le pin 5V de l'Arduino Mega (+ GND sur GND)
4. Verifier : l'Arduino s'allume normalement sur batterie

### Etape 2 — Moteurs

1. Fixer les moteurs N20 au chassis, monter les roues silicone
2. Connecter les moteurs aux borniers OUT1/OUT2 et OUT3/OUT4 du L298N
3. Brancher 12V/GND du L298N sur la batterie (en parallele avec le buck)
4. **Enlever le jumper 5V** du L298N
5. Cabler ENA→10, IN1→9, IN2→8, IN3→6, IN4→7, ENB→5
6. Upload `test_moteur1/test_moteur1.ino` → verifier que le moteur gauche tourne
7. Upload `test_2moteurs/test_2moteurs.ino` → verifier avant/arriere/rotation

### Etape 3 — Capteurs de ligne

1. Monter le shield sensor sur l'Arduino Mega
2. Brancher les 3 TCRT5000 sur A0, A1, A2 (section ANALOG du shield : S/V/G)
3. Fixer les capteurs au chassis : 2 a l'avant (gauche/droite), 1 a l'arriere
4. Upload `test_capteur_ligne/test_capteur_ligne.ino`
5. Ouvrir Serial Monitor (9600 baud), presenter une surface blanche et noire
6. Noter les valeurs, ajuster `SEUIL_BLANC` si necessaire (defaut: 300)
7. Upload `test_ligne_moteurs/test_ligne_moteurs.ino` → le robot recule sur la ligne blanche

### Etape 4 — Capteurs de distance

1. Brancher les 3 VL53L0X sur le bus I2C : SDA→20, SCL→21, VCC→5V, GND
2. Brancher les XSHUT : laser0→22, laser1→23, laser2→24
3. Monter les capteurs a l'avant du robot : centre + 2 lateraux a ~30 degres
4. Verifier l'init dans le Serial Monitor ("Lasers OK" au boot)

### Etape 5 — IMU

1. Brancher le MPU6050 sur le bus I2C (memes SDA/SCL que les VL53L0X)
2. AD0 → GND (adresse 0x68)
3. Monter l'IMU au centre du robot, bien fixe (pas de vibrations)

### Etape 6 — Bouton et finalisation

1. Brancher le bouton entre Pin 2 et GND
2. Upload `sumo_strategy/sumo_strategy.ino`
3. La LED onboard (pin 13) clignote lentement → en attente
4. Appui bouton → LED clignote vite (5s countdown) → GO

## Conseils de montage

### Masse commune (GND)

**Critique** : tous les composants doivent partager le meme GND. Un GND mal connecte entre l'Arduino et le L298N cause des comportements erratiques des moteurs. Verifier a l'ohmmetre que tous les GND sont bien relies.

### Poids

Budget masse pour rester sous 1kg :

- Arduino Mega + shield : ~55g
- L298N : ~30g
- Moteurs N20 x2 + roues : ~40g
- Batterie NiMH 7.2V : ~150-200g
- Chassis + lame : ~300-400g
- Capteurs + cablage : ~50g

### Vibrations

Les VL53L0X et le MPU6050 sont sensibles aux vibrations. Utiliser de la mousse ou du double-face epais pour les isoler du chassis metallique.

### Bus I2C

Le bus I2C est partage entre 4 composants (3x VL53L0X + MPU6050). Si le bus est instable :

- Garder les fils I2C courts (< 15cm)
- Ajouter des resistances de pull-up 4.7k entre SDA→5V et SCL→5V (certains breakouts les ont deja)
- Le code inclut un recovery automatique (16 clocks sur SCL) en cas de blocage

### Watchdog

Le firmware active un watchdog de 500ms. Si le code plante ou boucle, l'Arduino redemarrera automatiquement. Ne pas ajouter de `delay()` superieurs a 400ms dans le code.
