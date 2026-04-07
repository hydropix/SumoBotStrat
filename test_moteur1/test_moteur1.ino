// Test Phase 2 - Un moteur via L298N
// Pins : ENA=10 (PWM), IN1=9, IN2=8

#define ENA 10
#define IN1 9
#define IN2 8

void setup() {
  pinMode(ENA, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  Serial.begin(9600);
  Serial.println("Test moteur 1 - pret");
  delay(2000);
}

void avancer(int vitesse) {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  analogWrite(ENA, vitesse);
}

void reculer(int vitesse) {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  analogWrite(ENA, vitesse);
}

void stop() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  analogWrite(ENA, 0);
}

void loop() {
  // Avant lent
  Serial.println("Avant 50%");
  avancer(128);
  delay(2000);

  stop();
  delay(1000);

  // Avant rapide
  Serial.println("Avant 100%");
  avancer(255);
  delay(2000);

  stop();
  delay(1000);

  // Arriere lent
  Serial.println("Arriere 50%");
  reculer(128);
  delay(2000);

  stop();
  delay(1000);

  // Arriere rapide
  Serial.println("Arriere 100%");
  reculer(255);
  delay(2000);

  stop();
  delay(3000);

  Serial.println("--- Cycle termine ---");
}
