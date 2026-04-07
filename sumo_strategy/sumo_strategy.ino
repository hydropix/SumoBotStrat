// =============================================================
// SumoBot Strategy — Arduino Mega 2560
// Port de la simulation optimisee (94.6% WR vs smart enemy)
// Machine a etats: SEARCH -> TRACK -> CHARGE -> EVADE -> CENTER
// =============================================================

#include <Wire.h>
#include <VL53L0X.h>
#include <avr/wdt.h>

// ===================== PINOUT =====================
// Moteur gauche (L298N)
#define ENA 10
#define IN1 9
#define IN2 8
// Moteur droit (L298N)
#define ENB 5
#define IN3 6
#define IN4 7
// Capteurs ligne TCRT5000
#define LINE_FL A0  // avant-gauche
#define LINE_FR A1  // avant-droit
#define LINE_R  A2  // arriere
// VL53L0X XSHUT
#define XSHUT_0 22  // centre
#define XSHUT_1 23  // gauche
#define XSHUT_2 24  // droite
// Interface
#define BTN_START 2  // bouton start (pull-up interne, GND pour demarrer)
#define LED_STATE 13 // LED onboard pour etat

// ===================== HARDWARE CONFIG =====================
#define SEUIL_BLANC 300       // a calibrer sur ring reel
#define LASER_RANGE 760       // mm (95% de portee max)
#define COUNTDOWN_MS 5000     // 5s reglementaire
#define MOTOR_DEADBAND 25     // PWM minimum pour que le moteur tourne
#define PWM_RAMP_STEP 30      // increment max par cycle (~60Hz = ~5ms/step)
#define BRAKE_MS 3            // freinage actif avant inversion de sens
#define LOOP_PERIOD_US 16667  // ~60Hz (16.67ms)

// ===================== STRATEGIE (simulation optimisee) =====================
const float KP            = 0.582;
const float SEARCH_PWM    = 0.899;
const float TRACK_PWM     = 0.99;
const float CHARGE_PWM    = 0.976;
const int   CHARGE_THRESH = 372;    // mm
const int   EVADE_FRONT_MS = 450;
const int   EVADE_REAR_MS  = 300;
const float EVADE_REV_RATIO = 0.45;
const float EVADE_PWM     = 0.964;
const float EDGE_STEER    = 0.453;
const int   CENTER_RETURN_MS = 350;
const int   CENTER_FILL   = 145;    // mm
const float FLANK_ANGLE   = 0.51;
const int   FLANK_THRESH  = 636;    // mm
const float FLANK_PWM     = 0.658;

// ===================== CAPTEURS VL53L0X =====================
VL53L0X laser0, laser1, laser2;
bool lasersOK = false;

// ===================== FILTRAGE CAPTEURS =====================
// Filtre median 3 echantillons pour lasers (elimine les outliers)
int laserBuf0[3], laserBuf1[3], laserBuf2[3];
byte laserIdx = 0;

int median3(int a, int b, int c) {
  if (a > b) { int t = a; a = b; b = t; }
  if (b > c) { int t = b; b = c; c = t; }
  if (a > b) { int t = a; a = b; b = t; }
  return b;
}

// Ligne: multi-sample pour reduire le bruit
bool readLinePin(int pin) {
  int sum = analogRead(pin) + analogRead(pin);
  return (sum / 2) < SEUIL_BLANC;
}

// ===================== ETAT IA =====================
enum State { WAIT_START, COUNTDOWN, SEARCH, TRACK, CHARGE, FLANK, EVADE, CENTER };
State aiState = WAIT_START;

// Evade
unsigned long evadeStart = 0;
int evadeDuration = 0;
int evadeDir = 1;
bool evadeRear = false;

// Center return
unsigned long centerStart = 0;

// Flank
int flankDir = 0;

// Countdown
unsigned long countdownStart = 0;

// Capteurs (valeurs filtrees)
int d0mm, d1mm, d2mm;
bool det0, det1, det2;
bool lineFL, lineFR, lineR;

// ===================== MOTEURS AVEC RAMPE =====================
int curPwmL = 0, curPwmR = 0;    // PWM actuel (-255..255)
int tgtPwmL = 0, tgtPwmR = 0;    // PWM cible

int rampToward(int current, int target, int step) {
  if (current < target) return min(current + step, target);
  if (current > target) return max(current - step, target);
  return current;
}

void applyMotor(int pwm, int pinEN, int pinA, int pinB) {
  // Deadband: en dessous du seuil, freiner plutot que chauffer
  if (abs(pwm) < MOTOR_DEADBAND) {
    digitalWrite(pinA, LOW);
    digitalWrite(pinB, LOW);
    analogWrite(pinEN, 0);
    return;
  }
  if (pwm > 0) {
    digitalWrite(pinA, HIGH); digitalWrite(pinB, LOW);
  } else {
    digitalWrite(pinA, LOW);  digitalWrite(pinB, HIGH);
  }
  analogWrite(pinEN, abs(pwm));
}

void updateMotors() {
  // Freinage actif si inversion de sens demandee
  if ((curPwmL > MOTOR_DEADBAND && tgtPwmL < -MOTOR_DEADBAND) ||
      (curPwmL < -MOTOR_DEADBAND && tgtPwmL > MOTOR_DEADBAND)) {
    // Brake: les deux pins HIGH pendant quelques ms
    digitalWrite(IN1, HIGH); digitalWrite(IN2, HIGH);
    analogWrite(ENA, 255);
    curPwmL = 0;
  }
  if ((curPwmR > MOTOR_DEADBAND && tgtPwmR < -MOTOR_DEADBAND) ||
      (curPwmR < -MOTOR_DEADBAND && tgtPwmR > MOTOR_DEADBAND)) {
    digitalWrite(IN3, HIGH); digitalWrite(IN4, HIGH);
    analogWrite(ENB, 255);
    curPwmR = 0;
  }

  // Rampe progressive
  curPwmL = rampToward(curPwmL, tgtPwmL, PWM_RAMP_STEP);
  curPwmR = rampToward(curPwmR, tgtPwmR, PWM_RAMP_STEP);

  applyMotor(curPwmL, ENA, IN1, IN2);
  applyMotor(curPwmR, ENB, IN3, IN4);
}

void setMotors(int left, int right) {
  tgtPwmL = constrain(left, -255, 255);
  tgtPwmR = constrain(right, -255, 255);
}

void stopMotors() {
  tgtPwmL = 0; tgtPwmR = 0;
  curPwmL = 0; curPwmR = 0;
  digitalWrite(IN1, LOW); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, LOW);
  analogWrite(ENA, 0); analogWrite(ENB, 0);
}

void brakeMotors() {
  // Freinage actif (court-circuit moteur via H-bridge)
  digitalWrite(IN1, HIGH); digitalWrite(IN2, HIGH); analogWrite(ENA, 255);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, HIGH); analogWrite(ENB, 255);
  curPwmL = 0; curPwmR = 0;
  tgtPwmL = 0; tgtPwmR = 0;
}

// ===================== I2C RECOVERY =====================
void i2cRecover() {
  // Si le bus I2C est bloque (SDA stuck LOW), generer des clocks manuellement
  Wire.end();
  pinMode(21, OUTPUT); // SCL
  for (int i = 0; i < 16; i++) {
    digitalWrite(21, HIGH); delayMicroseconds(5);
    digitalWrite(21, LOW);  delayMicroseconds(5);
  }
  digitalWrite(21, HIGH);
  Wire.begin();
  Wire.setClock(400000);
}

// ===================== INIT LASERS =====================
void initLasers() {
  pinMode(XSHUT_0, OUTPUT); digitalWrite(XSHUT_0, LOW);
  pinMode(XSHUT_1, OUTPUT); digitalWrite(XSHUT_1, LOW);
  pinMode(XSHUT_2, OUTPUT); digitalWrite(XSHUT_2, LOW);
  delay(10);

  // Init sequentielle avec adresses uniques
  digitalWrite(XSHUT_0, HIGH); delay(10);
  laser0.setTimeout(200);
  if (!laser0.init()) { Serial.println("ERR laser0"); return; }
  laser0.setAddress(0x30);
  laser0.setMeasurementTimingBudget(20000); // 20ms — rapide
  laser0.startContinuous(0);

  digitalWrite(XSHUT_1, HIGH); delay(10);
  laser1.setTimeout(200);
  if (!laser1.init()) { Serial.println("ERR laser1"); return; }
  laser1.setAddress(0x31);
  laser1.setMeasurementTimingBudget(20000);
  laser1.startContinuous(0);

  digitalWrite(XSHUT_2, HIGH); delay(10);
  laser2.setTimeout(200);
  if (!laser2.init()) { Serial.println("ERR laser2"); return; }
  laser2.setAddress(0x32);
  laser2.setMeasurementTimingBudget(20000);
  laser2.startContinuous(0);

  lasersOK = true;
  Serial.println("Lasers OK");
}

// ===================== LECTURE CAPTEURS =====================
void readSensors() {
  // Ligne (double lecture pour filtrage)
  lineFL = readLinePin(LINE_FL);
  lineFR = readLinePin(LINE_FR);
  lineR  = readLinePin(LINE_R);

  if (!lasersOK) {
    d0mm = d1mm = d2mm = LASER_RANGE;
    det0 = det1 = det2 = false;
    return;
  }

  // Lasers: lecture brute dans buffer circulaire
  int r0 = laser0.readRangeContinuousMillimeters();
  int r1 = laser1.readRangeContinuousMillimeters();
  int r2 = laser2.readRangeContinuousMillimeters();

  // Timeout → portee max
  if (r0 > 8000 || laser0.timeoutOccurred()) r0 = LASER_RANGE;
  if (r1 > 8000 || laser1.timeoutOccurred()) r1 = LASER_RANGE;
  if (r2 > 8000 || laser2.timeoutOccurred()) r2 = LASER_RANGE;

  // Detecter I2C bloque (les 3 en timeout simultanement)
  if (laser0.timeoutOccurred() && laser1.timeoutOccurred() && laser2.timeoutOccurred()) {
    i2cRecover();
    initLasers();
  }

  // Buffer median
  laserBuf0[laserIdx] = r0;
  laserBuf1[laserIdx] = r1;
  laserBuf2[laserIdx] = r2;
  laserIdx = (laserIdx + 1) % 3;

  // Filtre median 3 points
  d0mm = median3(laserBuf0[0], laserBuf0[1], laserBuf0[2]);
  d1mm = median3(laserBuf1[0], laserBuf1[1], laserBuf1[2]);
  d2mm = median3(laserBuf2[0], laserBuf2[1], laserBuf2[2]);

  det0 = d0mm < LASER_RANGE;
  det1 = d1mm < LASER_RANGE;
  det2 = d2mm < LASER_RANGE;
}

// ===================== LED ETAT =====================
void updateLED() {
  switch (aiState) {
    case WAIT_START: digitalWrite(LED_STATE, (millis() / 500) % 2);  break; // blink lent
    case COUNTDOWN:  digitalWrite(LED_STATE, (millis() / 100) % 2);  break; // blink rapide
    case SEARCH:     digitalWrite(LED_STATE, LOW);   break;
    case EVADE:      digitalWrite(LED_STATE, HIGH);  break;
    default:         digitalWrite(LED_STATE, HIGH);  break; // engage = allumee
  }
}

// ===================== STRATEGIE =====================
void botAI() {
  const int maxPwm = 255;
  bool anyLaser = det0 || det1 || det2;
  unsigned long now = millis();

  int eff1 = det1 ? d1mm : (det0 ? d0mm + CENTER_FILL : LASER_RANGE);
  int eff2 = det2 ? d2mm : (det0 ? d0mm + CENTER_FILL : LASER_RANGE);

  // ========== EVADE ==========
  if (aiState == EVADE) {
    unsigned long elapsed = now - evadeStart;
    if ((int)elapsed >= evadeDuration) {
      aiState = CENTER;
      centerStart = now;
      return;
    }
    if (evadeRear) {
      int spd = maxPwm * EVADE_PWM;
      setMotors(spd, spd);
    } else {
      int revMs = evadeDuration * EVADE_REV_RATIO;
      if ((int)elapsed < revMs) {
        int spd = maxPwm * EVADE_PWM;
        setMotors(-spd, -spd);
      } else {
        int spd = maxPwm * 0.8;
        setMotors(evadeDir * spd, -evadeDir * spd);
      }
    }
    return;
  }

  // ========== CENTER RETURN ==========
  if (aiState == CENTER) {
    if ((int)(now - centerStart) >= CENTER_RETURN_MS) {
      aiState = SEARCH;
      return;
    }
    if (!lineFL && !lineFR && !lineR && !det0 && !det1 && !det2) {
      int spd = maxPwm * 0.7;
      setMotors(spd, spd);
      return;
    }
    aiState = SEARCH;
  }

  // ========== LIGNE ==========
  if (lineFL || lineFR || lineR) {
    bool fwdDet = det0 || det1 || det2;
    bool engaging = fwdDet && (aiState == CHARGE || aiState == TRACK);
    bool singleFront = (lineFL || lineFR) && !(lineFL && lineFR) && !lineR;

    if (engaging && singleFront) {
      int minD = 9999;
      if (det0 && d0mm < minD) minD = d0mm;
      if (det1 && d1mm < minD) minD = d1mm;
      if (det2 && d2mm < minD) minD = d2mm;

      float err = eff1 - eff2;
      float cor = KP * err;
      int base = (minD < CHARGE_THRESH) ? maxPwm * CHARGE_PWM : maxPwm * TRACK_PWM;
      int ec = lineFL ? (int)(maxPwm * EDGE_STEER) : -(int)(maxPwm * EDGE_STEER);
      setMotors(
        constrain(base + (int)cor + ec, -maxPwm, maxPwm),
        constrain(base - (int)cor - ec, -maxPwm, maxPwm)
      );
      aiState = CHARGE;
      return;
    }

    if (lineR && !lineFL && !lineFR) {
      evadeDuration = EVADE_REAR_MS;
      evadeRear = true;
    } else {
      evadeDuration = EVADE_FRONT_MS;
      evadeRear = false;
      if (lineFL && !lineFR)       evadeDir = 1;
      else if (lineFR && !lineFL)  evadeDir = -1;
      else                         evadeDir = (random(2) == 0) ? 1 : -1;
    }
    evadeStart = now;
    aiState = EVADE;
    return;
  }

  // ========== SEARCH / TRACK / CHARGE / FLANK ==========
  if (!anyLaser) {
    aiState = SEARCH;
    flankDir = 0;
    int spd = maxPwm * SEARCH_PWM;
    setMotors(spd, -spd);
  } else {
    int minD = 9999;
    if (det0 && d0mm < minD) minD = d0mm;
    if (det1 && d1mm < minD) minD = d1mm;
    if (det2 && d2mm < minD) minD = d2mm;

    float err = eff1 - eff2;
    float cor = KP * err;

    if (minD > FLANK_THRESH) {
      aiState = FLANK;
      if (flankDir == 0) {
        if (det1 && !det2)       flankDir = -1;
        else if (det2 && !det1)  flankDir = 1;
        else                     flankDir = (random(2) == 0) ? 1 : -1;
      }
      float arcCor = KP * err + flankDir * FLANK_ANGLE * 150.0;
      int base = maxPwm * FLANK_PWM;
      setMotors(
        constrain(base + (int)arcCor, -maxPwm, maxPwm),
        constrain(base - (int)arcCor, -maxPwm, maxPwm)
      );
    } else {
      flankDir = 0;
      int base;
      if (minD < CHARGE_THRESH) { aiState = CHARGE; base = maxPwm * CHARGE_PWM; }
      else                      { aiState = TRACK;  base = maxPwm * TRACK_PWM;  }
      setMotors(
        constrain(base + (int)cor, -maxPwm, maxPwm),
        constrain(base - (int)cor, -maxPwm, maxPwm)
      );
    }
  }
}

// ===================== SETUP =====================
void setup() {
  // Moteurs
  pinMode(ENA, OUTPUT); pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(ENB, OUTPUT); pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  stopMotors();

  // Capteurs ligne
  pinMode(LINE_FL, INPUT);
  pinMode(LINE_FR, INPUT);
  pinMode(LINE_R,  INPUT);

  // Bouton start + LED
  pinMode(BTN_START, INPUT_PULLUP);
  pinMode(LED_STATE, OUTPUT);

  Serial.begin(9600);
  Serial.println(F("SumoBot v1.0"));

  // I2C
  Wire.begin();
  Wire.setClock(400000);
  initLasers();

  // Init filtre median (remplir le buffer)
  for (int i = 0; i < 3; i++) {
    laserBuf0[i] = LASER_RANGE;
    laserBuf1[i] = LASER_RANGE;
    laserBuf2[i] = LASER_RANGE;
  }

  // Seed random
  randomSeed(analogRead(A5));

  // Watchdog 500ms — reset si le code bloque
  wdt_enable(WDTO_500MS);

  aiState = WAIT_START;
  Serial.println(F("En attente du bouton START..."));
}

// ===================== LOOP =====================
void loop() {
  unsigned long loopStart = micros();

  wdt_reset();

  // Attente bouton start
  if (aiState == WAIT_START) {
    updateLED();
    if (digitalRead(BTN_START) == LOW) {
      delay(50); // debounce
      if (digitalRead(BTN_START) == LOW) {
        countdownStart = millis();
        aiState = COUNTDOWN;
        Serial.println(F("COUNTDOWN 5s..."));
      }
    }
    return;
  }

  // Countdown
  if (aiState == COUNTDOWN) {
    updateLED();
    stopMotors();
    if (millis() - countdownStart >= COUNTDOWN_MS) {
      aiState = SEARCH;
      Serial.println(F("GO!"));
    }
    return;
  }

  // Lecture capteurs
  readSensors();

  // IA
  botAI();

  // Appliquer moteurs avec rampe
  updateMotors();

  // LED
  updateLED();

  // Cadencer la boucle a ~60Hz
  unsigned long elapsed = micros() - loopStart;
  if (elapsed < LOOP_PERIOD_US) {
    delayMicroseconds(LOOP_PERIOD_US - elapsed);
  }
}
