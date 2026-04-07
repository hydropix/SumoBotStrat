// Test Phase 3 - Capteur ligne TCRT5000
// AO → A0

#define CAPTEUR_LIGNE A0

void setup() {
  Serial.begin(9600);
  Serial.println("Test capteur ligne TCRT5000");
  Serial.println("Passe le capteur au-dessus de surfaces blanches et noires");
  Serial.println("---");
}

void loop() {
  int valeur = analogRead(CAPTEUR_LIGNE);

  Serial.print("Valeur: ");
  Serial.print(valeur);
  Serial.print(" -> ");

  if (valeur < 300) {
    Serial.println("BLANC (bord du ring !)");
  } else {
    Serial.println("NOIR (ring OK)");
  }

  delay(200);
}
