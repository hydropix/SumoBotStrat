# SumoBot - Robot Sumo Arduino Mega

## Projet
Robot sumo de compétition (catégorie 500g-1kg) basé sur Arduino Mega 2560.

## Architecture matérielle
- **Moteurs** : N20 12V 500RPM x2, pilotés par L298N (jumper auto-alim)
- **Alimentation** : Batterie NiMH 7.2V → Buck LM2596 → 5V (Arduino pin 5V, capteurs)
- **Capteurs ligne** : TCRT5000 x3 sur pins analogiques A0, A1, A2 (via shield sensor Mega)
- **Capteurs distance** : VL53L0X x4 en I2C (SDA=20, SCL=21, XSHUT=22,23,24)

## Pinout
| Fonction | Pin |
|----------|-----|
| ENA (PWM moteur gauche) | 10 |
| IN1 (dir moteur gauche) | 9 |
| IN2 (dir moteur gauche) | 8 |
| IN3 (dir moteur droit) | 6 |
| IN4 (dir moteur droit) | 7 |
| ENB (PWM moteur droit) | 5 |
| TCRT5000 #1 | A0 |
| TCRT5000 #2 | A1 |
| TCRT5000 #3 | A2 |
| VL53L0X SDA | 20 |
| VL53L0X SCL | 21 |
| VL53L0X XSHUT | 22, 23, 24 |

## Structure du projet
- `test_moteur1/` - Test un moteur (Phase 2)
- `test_2moteurs/` - Test deux moteurs (Phase 2)
- `test_capteur_ligne/` - Lecture TCRT5000 (Phase 3)
- `test_ligne_moteurs/` - Réaction moteurs sur ligne (Phase 3)

## Conventions code
- Langage : C++ Arduino
- Serial à 9600 baud pour debug
- Seuil ligne blanche : 300 (à calibrer sur ring réel)
- PWM moteurs : 0-255 (150 = croisière, 200+ = combat)

## Câblage
- Shield sensor Mega : brancher capteurs sur rangées S/V/G
- Capteurs analogiques (TCRT5000) sur section ANALOG du shield, pas PWM
- GND commun obligatoire entre tous les composants
- Ne JAMAIS brancher 7.2V sur pin 5V Arduino
