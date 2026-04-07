// Test Phase 2 - Deux moteurs via L298N
// Moteur gauche : ENA=10 (PWM), IN1=9, IN2=8
// Moteur droit  : ENB=5  (PWM), IN3=6, IN4=7

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
  Serial.println("Test 2 moteurs - pret");
  delay(2000);
}

void moteurGauche(int vitesse, bool avant) {
  digitalWrite(IN1, avant ? HIGH : LOW);
  digitalWrite(IN2, avant ? LOW : HIGH);
  analogWrite(ENA, vitesse);
}

void moteurDroit(int vitesse, bool avant) {
  digitalWrite(IN3, avant ? HIGH : LOW);
  digitalWrite(IN4, avant ? LOW : HIGH);
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
  // Avancer tout droit
  Serial.println("Avancer");
  moteurGauche(180, true);
  moteurDroit(180, true);
  delay(2000);

  stopMoteurs();
  delay(1000);

  // Reculer
  Serial.println("Reculer");
  moteurGauche(180, false);
  moteurDroit(180, false);
  delay(2000);

  stopMoteurs();
  delay(1000);

  // Tourner a gauche (droit avance, gauche recule)
  Serial.println("Tourner gauche");
  moteurGauche(150, false);
  moteurDroit(150, true);
  delay(1500);

  stopMoteurs();
  delay(1000);

  // Tourner a droite (gauche avance, droit recule)
  Serial.println("Tourner droite");
  moteurGauche(150, true);
  moteurDroit(150, false);
  delay(1500);

  stopMoteurs();
  delay(1000);

  // Courbe douce a gauche (droit plus vite)
  Serial.println("Courbe gauche");
  moteurGauche(100, true);
  moteurDroit(200, true);
  delay(2000);

  stopMoteurs();
  delay(3000);

  Serial.println("--- Cycle termine ---");
}
