# SumoBotStrat

Un robot sumo autonome qui se bat tout seul sur un ring ! Il detecte son adversaire, le poursuit et essaie de le pousser hors de l'arene. Toute sa strategie a ete mise au point grace a un simulateur sur ordinateur, puis transferee sur le vrai robot.

![SumoBot MuJoCo simulation](python_ztyC2lxIAz-output.gif)

## C'est quoi un robot sumo ?

Le robot sumo, c'est un sport de robots : deux robots sont poses sur un ring circulaire noir (appele "dohyo"), et chacun doit pousser l'autre en dehors. Le ring a une bordure blanche que le robot doit detecter pour ne pas tomber lui-meme.

Notre robot pese entre 500g et 1kg et fonctionne avec une carte **Arduino Mega 2560** (une sorte de mini-ordinateur programmable).

## Notre approche : simuler avant de construire

Plutot que de programmer le robot a l'aveugle et de faire des dizaines d'essais physiques (ce qui prend du temps et casse le materiel), on a choisi une approche differente :

**1. On a cree un simulateur sur ordinateur** qui reproduit fidelement le comportement du robot : ses moteurs, ses capteurs, la physique des collisions, le ring...

**2. On a fait jouer le robot virtuel des milliers de matchs** contre differents types d'adversaires pour trouver les meilleurs reglages.

**3. On a transfere la strategie gagnante sur le vrai robot.**

```text
    ORDINATEUR                                         ROBOT REEL
 ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐
 │  Simulateur  │ --> │ Optimisation │ --> │  Code Arduino final  │
 │  (virtuel)   │     │ (des milliers│     │  (memes reglages)    │
 │              │     │  de matchs)  │     │                      │
 └──────────────┘     └──────────────┘     └──────────────────────┘
```

## Le simulateur

Le simulateur est un programme qui fait "comme si" le robot existait dans l'ordinateur. Il calcule tout : comment les roues tournent, comment le robot glisse sur le sol, ce que voient les capteurs...

Vous pouvez l'essayer directement dans votre navigateur :

**[Lancer le simulateur](https://hydropix.github.io/SumoBotStrat/simulation/index.html)** (cliquez pour essayer !)

Dans le simulateur, vous verrez :
- Le ring noir avec sa bordure blanche
- Notre robot (en bleu) qui tourne, cherche, et attaque
- Un adversaire (en rouge) qu'on peut controler
- Les faisceaux laser qui detectent l'ennemi
- L'etat actuel du robot (recherche, poursuite, charge, esquive...)

### La regle d'or : pas de triche !

Le robot dans le simulateur n'a le droit d'utiliser **que** les informations qu'il aurait en vrai :
- Ses 3 capteurs laser pour "voir" l'adversaire (portee ~80 cm)
- Ses 3 capteurs de ligne pour detecter le bord du ring
- Son accelerometre/gyroscope pour sentir les chocs et sa rotation

Il n'a **pas le droit** de connaitre sa position exacte sur le ring, ni la position de l'ennemi. Comme ca, ce qui marche en simulation marchera aussi en vrai !

### Deux simulateurs complementaires

Le projet contient en fait **deux systemes de simulation** qui partagent la meme regle capteurs-uniquement :

**1. Simulateur JavaScript ([simulation/](simulation/))** — Simulation 2D legere (HTML + Canvas, zero dependance). C'est le simulateur utilise pour l'optimisation Monte Carlo massive et l'iteration rapide sur la strategie. Il tourne dans le navigateur ou en batch Node.js via [headless.js](simulation/headless.js) et [montecarlo.js](simulation/montecarlo.js).

**2. Simulateur MuJoCo ([simulation/mujoco/](simulation/mujoco/))** — Simulation physique 3D haute fidelite basee sur [MuJoCo](https://mujoco.org/) (Python). Permet de valider la strategie sur une physique rigide realiste (collisions, frottements, inertie 3D) avant le portage sur Arduino. Le GIF en haut du README montre ce simulateur en action.

Structure du simulateur MuJoCo :
- [models/](simulation/mujoco/models/) — modeles XML MuJoCo (arene, bot, ennemi, scene)
- [physics/](simulation/mujoco/physics/) — moteur de simulation et modele moteur N20
- [sensors/](simulation/mujoco/sensors/) — capteurs simules (ligne TCRT5000, laser VL53L0X, IMU MPU6050)
- [ai/](simulation/mujoco/ai/) — `bot_ai.py`, `enemy_ai.py`, parametres de strategie
- [runners/](simulation/mujoco/runners/) — `viewer.py` (interactif 3D), `headless.py` (batch), `montecarlo.py`

Installation et lancement du simulateur MuJoCo :

```bash
cd simulation/mujoco
setup.bat              # cree venv + installe mujoco, numpy
run_viewer.bat         # viewer 3D interactif
run_headless.bat       # batch de matchs headless
run_montecarlo.bat     # optimisation des parametres
```

## Comment on a trouve les meilleurs reglages : la methode Monte Carlo

Le robot a 16 reglages qu'on peut ajuster : a quelle vitesse il tourne pour chercher, a quelle vitesse il charge, a quel angle il attaque de cote, etc. Trouver la meilleure combinaison a la main serait impossible (il y a des milliards de possibilites).

On a donc utilise la **methode Monte Carlo** : c'est une technique qui consiste a essayer beaucoup de combinaisons au hasard et garder les meilleures. C'est un peu comme si vous lanciez des flechettes au hasard sur une cible, et qu'a chaque tour vous vous rapprochiez de la zone ou tombent les meilleures flechettes.

### Etape 1 — Chercher large

On genere **80 combinaisons de reglages** au hasard, et chacune joue **200 matchs** contre **12 adversaires differents** :
- Des adversaires de toutes tailles (petits, gros, legers, lourds, lents, rapides)
- Des adversaires "intelligents" qui traquent aussi notre robot

On garde les 8 meilleures combinaisons et on les reteste avec 800 matchs pour etre sur.

### Etape 2 — Affiner

Autour de la meilleure combinaison de l'etape 1, on genere **100 nouvelles combinaisons** proches (on ajuste legerement chaque reglage). On les reteste et on garde la meilleure.

### Etape 3 — Valider

On fait jouer le champion **3000 matchs** contre chaque type d'adversaire pour confirmer qu'il est vraiment bon partout.

### Resultats

| Adversaire | Victoires |
| ---------- | --------- |
| Adversaires basiques (8 types differents) | 99.7 a 100% |
| Adversaire intelligent (standard) | 92.5% |
| Adversaire intelligent + lourd + rapide | ~47% |

Le seul adversaire problematique est un ennemi a la fois intelligent, lourd et rapide. En competition reelle, ce scenario est tres rare.

## Comment le robot "reflechit" : la machine a etats

Le robot ne "pense" pas vraiment, mais il suit des regles precises. A chaque instant, il est dans un **etat** (une situation) et reagit en fonction de ce qu'il detecte. Voici ses 8 etats :

| Etat | Ce que fait le robot | Quand ? |
| ---- | -------------------- | ------- |
| **WAIT_START** | Attend qu'on appuie sur le bouton | Au demarrage |
| **COUNTDOWN** | Attend 5 secondes (reglementaire) | Apres le bouton |
| **SEARCH** | Tourne sur lui-meme pour scanner autour | Quand il ne voit rien |
| **FLANK** | Approche en arc de cercle (~30 deg) | Ennemi detecte mais loin (> 63 cm) |
| **TRACK** | Suit l'ennemi en ajustant sa direction | Ennemi detecte a moyenne distance |
| **CHARGE** | Fonce a pleine puissance ! | Ennemi proche (< 37 cm) |
| **EVADE** | Recule et tourne | Bord du ring detecte |
| **CENTER** | Avance tout droit pour revenir au centre | Apres une esquive |

En plus, le robot reagit aux chocs grace a son accelerometre :
- **Souleve par l'adversaire** : il recule et tourne pour se degager
- **Frappe sur le cote** : il tourne vers l'attaquant pour riposter
- **Frappe de face** : il esquive lateralement

## Ce qu'on a decouvert grace a la simulation

La simulation nous a permis de tester des idees et de garder seulement ce qui marche. Voici les decouvertes les plus importantes :

- **Les capteurs laser a 30 deg, c'est mieux que 90 deg.** On a teste avec les capteurs lateraux pointes a 90 degres (sur les cotes), mais le robot perdait trop souvent la cible. A 30 degres, il a un champ de vision plus concentre vers l'avant et gagne **8% de matchs en plus**.

- **Pousser meme au bord du ring, ca marche.** Normalement le robot recule quand il detecte le bord. Mais si l'ennemi est juste devant, on le laisse continuer a pousser. Ca reduit les matchs nuls de 26% a 13%.

- **Un controleur simple est meilleur qu'un controleur complique.** On a essaye un systeme de direction plus avance (controleur PD), mais le robot oscillait dans tous les sens. Le controleur simple (P) est stable et efficace.

## Les fichiers du projet

| Dossier | Contenu |
| ------- | ------- |
| `simulation/` | Le simulateur (ouvrir `index.html` dans un navigateur) |
| `simulation/montecarlo_v3.js` | Le programme d'optimisation Monte Carlo |
| `sumo_strategy/` | Le code final pour l'Arduino (le "cerveau" du robot) |
| `test_moteur1/` | Programme de test pour 1 moteur |
| `test_2moteurs/` | Programme de test pour 2 moteurs |
| `test_capteur_ligne/` | Programme de test pour les capteurs de bord |
| `test_ligne_moteurs/` | Programme de test : capteurs + moteurs ensemble |
| `docs/` | Schemas electriques et [guide de montage](docs/HARDWARE.md) |

## Essayer le simulateur

Ouvrir le lien ci-dessous dans un navigateur (Chrome, Firefox, Edge...). Rien a installer !

**[Lancer le simulateur](https://hydropix.github.io/SumoBotStrat/simulation/index.html)**

## Programmer le vrai robot

1. Installer [Arduino IDE](https://www.arduino.cc/en/software) sur votre ordinateur
2. Brancher l'Arduino Mega en USB
3. Ouvrir le fichier `sumo_strategy/sumo_strategy.ino`
4. Cliquer sur la fleche "Upload" pour envoyer le code sur le robot
5. Appuyer sur le bouton START du robot pour lancer le match !

## Construire le robot

Voir le **[guide de montage complet](docs/HARDWARE.md)** pour la liste des pieces et les instructions de cablage pas-a-pas.

## Licence

Voir [LICENSE](LICENSE).
