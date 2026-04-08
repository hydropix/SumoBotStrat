# SumoBotStrat

Robot sumo de competition (categorie 500g-1kg) base sur Arduino Mega 2560, dont la strategie a ete entierement developpee et optimisee par simulation avant d'etre portee sur le hardware reel.

## Concept

L'approche de ce projet est **simulation-first** : plutot que de coder directement sur le robot et iterer par essais physiques, toute la strategie est developpee dans un simulateur physique fidele, optimisee par recherche Monte Carlo, puis portee sur Arduino.

```text
Simulateur physique (JS)  -->  Optimisation Monte Carlo  -->  Port Arduino (C++)
     60Hz / 240Hz sub             12 profils ennemis            Machine a etats
     Moteurs + friction           16 parametres                 Capteurs reels
     Capteurs simules             3 phases de raffinement       Watchdog + I2C recovery
```

## Architecture du simulateur

Le simulateur reproduit fidelement la physique du robot :
- **Moteurs DC** : modele couple/vitesse avec stallTorque et noLoadOmega
- **Friction** : coefficient mu=0.6 (pneus silicone sur dohyo), amortissement lateral
- **Arena** : ring circulaire 77cm de diametre avec bordure blanche 22mm
- **Capteurs** : 3x lasers VL53L0X (centre + 2 lateraux a ~30 deg), 3x TCRT5000 (ligne), IMU MPU6050

Deux versions du simulateur :
- [simulation/index.html](simulation/index.html) — Version visuelle interactive avec telemetrie temps reel, controle des parametres par sliders, et mode ennemi manuel
- [simulation/headless.js](simulation/headless.js) — Version headless Node.js pour tests batch (`node headless.js --rounds 500`)

### Contrainte capteurs-uniquement

Regle stricte : l'IA du bot (botAI) n'utilise **que** les donnees disponibles sur le robot reel. Sont interdits : position absolue (x,y), heading global, etat de l'ennemi (sauf via lasers), donnees internes de la simulation. Cela garantit que ce qui fonctionne en simulation fonctionnera sur le hardware.

## Optimisation Monte Carlo

La recherche des parametres optimaux se fait en 3 phases successives :

### Phase 1 — Recherche large (montecarlo_v3.js)

- **80 configurations** generees aleatoirement dans des plages larges
- **200 rounds** par config contre **12 profils ennemis** :
  - 8 profils basiques (tailles/masses/vitesses variees : S-light-slow, XL-heavy-fast, etc.)
  - 4 profils "smart" (IA intelligente avec tracking, poids x2-x4 dans le score)
- Score pondere : les victoires contre ennemis smart comptent 2-4x plus
- **Top 8** revalide a 800 rounds pour confirmer

### Phase 2 — Raffinement (montecarlo_v3_refine.js)

- Plages resserrees a +/-20-40% autour du meilleur de Phase 1
- **100 configurations**, 250 rounds chacune
- **Top 10** revalide a 1500 rounds
- Convergence vers la config optimale finale

### Phase 3 — Validation finale

- Test du champion a 3000 rounds contre chaque profil individuellement
- Verification des cas limites (ennemi lourd+rapide, petit+agile)

### 16 parametres optimises

| Categorie | Parametres |
| --------- | ---------- |
| **Deplacement** | kp (gain steering), searchPwm, trackPwm, chargePwm, chargeThreshold |
| **Evasion** | evadePwm, edgeSteer, centerFill |
| **Flanking** | flankAngle, flankThreshold, flankPwm, flankEnabled |
| **Counter-dodge** | counterThresh, counterDodgeTime, counterPwm |
| **Tilt escape** | tiltEscapeSpin |

### Resultats obtenus

| Scenario | Win Rate |
| -------- | -------- |
| vs Ennemis basiques (8 profils) | 99.7-100% |
| vs Smart enemy (standard) | 92.5% |
| vs Smart-heavy-fast (m=0.7, s=1.2) | ~47% |

La faiblesse contre l'ennemi smart+lourd+rapide est connue — cet adversaire combine IA omnisciente et momentum eleve, un scenario extreme rarement rencontre en competition reelle.

## Machine a etats (8 etats)

```text
                    +-----------+
                    | WAIT_START|  (bouton)
                    +-----+-----+
                          |
                    +-----v-----+
                    | COUNTDOWN |  (5s reglementaire)
                    +-----+-----+
                          |
              +-----------v-----------+
              |        SEARCH         |  Rotation sur place
              |  (spin + scan IMU)    |  jusqu'a detection laser
              +-----------+-----------+
                          |
            +-------------v-------------+
            |                           |
    +-------v-------+          +--------v-------+
    |     FLANK     |          |     TRACK      |
    | Arc ~29 deg   |          | P-controller   |
    | si >636mm     |          | kp=0.582       |
    +-------+-------+          +--------+-------+
            |                           |
            +-------------+-------------+
                          |
                  +-------v-------+
                  |    CHARGE     |
                  | Pleine puiss. |
                  | si <372mm     |
                  +-------+-------+
                          |
                  +-------v-------+
                  |     EVADE     |  Ligne detectee
                  | Recul + pivot |  --> recul puis pivot
                  +-------+-------+
                          |
                  +-------v-------+
                  |    CENTER     |  Retour centre
                  | 350ms tout    |  puis retour SEARCH
                  | droit         |
                  +-------+-------+
```

Etats reactifs supplementaires (IMU) :

- **TILT_ESC** : robot souleve detecte par accelZ → recul + spin
- **IMPACT** : choc lateral (|imuAy|>15) → spin vers la source 250ms
- **COUNTER** : collision frontale (imuAx<-18.8) → esquive laterale 212ms

## Ajustements et decisions cles

Decisions validees par Monte Carlo :

- **3 lasers a 30 deg** plutot que 90 deg : +8.2% win rate (95.1% pondere). Les capteurs a 90 deg (78-88%) perdent la cible trop facilement
- **Edge-charge** : continuer a pousser si ennemi en vue malgre la detection de bord. Reduit les timeouts de 26% a 13%
- **searchPwm=0.95** et **trackPwm=0.9** : gains confirmes de +1% WR chacun
- **Controleur P simple** (kp=0.582) : un PD (avec terme derive) a ete catastrophique — instabilite totale
- **chargeThreshold=372mm** : seuil optimal. En dessous de 300mm, impact negatif

## Structure du projet

```text
SumoBotStrat/
├── simulation/
│   ├── index.html              Simulateur visuel interactif
│   ├── headless.js             Simulateur headless (Node.js)
│   ├── montecarlo_v3.js        Recherche Monte Carlo large
│   ├── montecarlo_v3_refine.js Raffinement Monte Carlo
│   ├── montecarlo.js           v1 (archive)
│   └── montecarlo_v2.js        v2 (archive)
├── sumo_strategy/
│   └── sumo_strategy.ino       Strategie finale Arduino Mega
├── test_moteur1/               Test Phase 2 : 1 moteur
├── test_2moteurs/              Test Phase 2 : 2 moteurs
├── test_capteur_ligne/         Test Phase 3 : capteur TCRT5000
├── test_ligne_moteurs/         Test Phase 3 : ligne + moteurs
├── docs/
│   ├── schema_electrique.svg   Schema electrique
│   ├── schema_mecanique.svg    Schema mecanique
│   └── HARDWARE.md             Guide de montage complet
└── CLAUDE.md                   Regles du projet (capteurs-only, pinout)
```

## Demarrage rapide

### Simulateur visuel

Ouvrir `simulation/index.html` dans un navigateur. Aucune dependance requise.

### Monte Carlo

```bash
cd simulation
node montecarlo_v3.js          # Phase 1 : recherche large
node montecarlo_v3_refine.js   # Phase 2 : raffinement
node headless.js --rounds 3000 # Validation finale
```

### Arduino

1. Ouvrir `sumo_strategy/sumo_strategy.ino` dans Arduino IDE
2. Selectionner Board: Arduino Mega 2560, Port: COMx
3. Installer la librairie `VL53L0X` par Pololu
4. Upload et connecter le bouton START sur pin 2

## Hardware

Voir [docs/HARDWARE.md](docs/HARDWARE.md) pour le guide de montage complet avec schemas de cablage detailles.

## Licence

Voir [LICENSE](LICENSE).
