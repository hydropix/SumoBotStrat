// Test Phase 3 - Reaction moteurs sur detection ligne
// Capteur ligne A0, Moteurs sur L298N

#define CAPTEUR_LIGNE A0
#define SEUIL_BLANC 300

#define ENA 10
#define IN1 9
#define IN2 8
#define ENB 5
#define IN3 6
#define IN4 7

void setup() {
  pinMode(ENA, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(ENB, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  Serial.begin(9600);
  Serial.println("Test ligne + moteurs - pret");
  delay(2000);
}

void avancer(int vitesse) {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  analogWrite(ENA, vitesse);
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
  analogWrite(ENB, vitesse);
}

void reculer(int vitesse) {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  analogWrite(ENA, vitesse);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
  analogWrite(ENB, vitesse);
}

void stopMoteurs() {
  analogWrite(ENA, 0);
  analogWrite(ENB, 0);
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
}

void loop() {
  int valeur = analogRead(CAPTEUR_LIGNE);

  if (valeur < SEUIL_BLANC) {
    // Ligne blanche detectee -> reculer puis tourner
    Serial.print("LIGNE! (");
    Serial.print(valeur);
    Serial.println(") -> Recul + rotation");

    reculer(200);
    delay(500);

    // Rotation a droite pour s'eloigner du bord
    digitalWrite(IN1, HIGH);
    digitalWrite(IN2, LOW);
    analogWrite(ENA, 180);
    digitalWrite(IN3, LOW);
    digitalWrite(IN4, HIGH);
    analogWrite(ENB, 180);
    delay(400);

    stopMoteurs();
    delay(200);
  } else {
    // Pas de ligne -> avancer doucement
    avancer(150);
  }
}
