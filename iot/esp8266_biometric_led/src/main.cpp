/**
 * PROJECT RESILIENCE-ALPHA — Workshop 2026-27 / M2
 * Consigne Additionnelle 1 : Objet Connecte ESP8266 (ESP-12F)
 * 
 * Gestion de la LED Bicolore (Rouge/Vert) pour l'Authentification Biometrique + Mot de Passe :
 * 1. Par defaut : LED eteinte.
 * 2. Visage reconnu par IA : Vert clignotant jusqu'a saisie du mot de passe.
 * 3. Visage NON reconnu : Rouge fixe pendant 30 secondes puis extinction.
 * 4. Mot de passe VALIDE : Vert fixe pendant 30 secondes puis extinction.
 * 5. Mot de passe INVALIDE : Rouge clignote 10 fois puis extinction.
 * 
 * Controles acceptes :
 * - Via Wi-Fi (HTTP GET/POST sur /led?state=...)
 * - Via Port Serie USB (Commandes textuelles a 115200 baud : CMD:GREEN_BLINK, etc.)
 */

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

// Broches de la LED bicolore
#ifndef LED_GREEN_PIN
#define LED_GREEN_PIN 4   // D2 (GPIO4)
#endif

#ifndef LED_RED_PIN
#define LED_RED_PIN 5     // D1 (GPIO5)
#endif

// Type de LED : 1 pour Cathode Commune (HIGH=allume), 0 pour Anode Commune (LOW=allume)
#ifndef LED_COMMON_CATHODE
#define LED_COMMON_CATHODE 1
#endif

#if LED_COMMON_CATHODE
  #define PIN_ON  HIGH
  #define PIN_OFF LOW
#else
  #define PIN_ON  LOW
  #define PIN_OFF HIGH
#endif

// Identifiants Wi-Fi du Point d'Acces du PC Hote
const char* WIFI_SSID = "RESILIENCE-G2";
const char* WIFI_PASS = "Azerty38";

// Serveur Web sur port 80
ESP8266WebServer server(80);

// Etats de la machine a etats
enum LedState {
    STATE_OFF,
    STATE_GREEN_BLINKING,
    STATE_RED_SOLID_30S,
    STATE_GREEN_SOLID_30S,
    STATE_RED_BLINK_10X,
    STATE_DUAL_BLINK
};

LedState currentState = STATE_OFF;
unsigned long stateStartTime = 0;
unsigned long lastBlinkTime = 0;
bool blinkState = false;
int redBlinkCounter = 0;

// Allumage/Extinction physique des LED
void setPhysicalLeds(bool green, bool red) {
    digitalWrite(LED_GREEN_PIN, green ? PIN_ON : PIN_OFF);
    digitalWrite(LED_RED_PIN, red ? PIN_ON : PIN_OFF);
}

// Changement d'etat securise
void changeState(LedState newState, const char* reason = "") {
    currentState = newState;
    stateStartTime = millis();
    lastBlinkTime = millis();
    blinkState = false;
    redBlinkCounter = 0;

    Serial.print("[ESP-12F] Nouvel etat LED : ");
    switch (currentState) {
        case STATE_OFF:
            setPhysicalLeds(false, false);
            Serial.println("ETEINT (Nominal/Repos)");
            break;
        case STATE_GREEN_BLINKING:
            Serial.println("VERT CLIGNOTANT (Visage reconnu, attente mot de passe)");
            break;
        case STATE_RED_SOLID_30S:
            setPhysicalLeds(false, true);
            Serial.println("ROUGE FIXE 30s (Visage non reconnu / Bloque)");
            break;
        case STATE_GREEN_SOLID_30S:
            setPhysicalLeds(true, false);
            Serial.println("VERT FIXE 30s (Authentification reussie, acces Back-office valide)");
            break;
        case STATE_RED_BLINK_10X:
            Serial.println("ROUGE CLIGNOTANT 10x (Mot de passe invalide)");
            break;
        case STATE_DUAL_BLINK:
            Serial.println("BICOLORE CLIGNOTANT CONTINU (Vert & Rouge alternes)");
            break;
    }
    if (reason && strlen(reason) > 0) {
        Serial.print("   -> Declencheur : ");
        Serial.println(reason);
    }
}

// Traitement des requetes HTTP
void handleRoot() {
    String html = "<html><head><meta charset='utf-8'><title>ESP8266 Biometric LED</title></head>";
    html += "<body style='font-family:sans-serif;background:#0f172a;color:#f8fafc;padding:20px;'>";
    html += "<h2>PROJECT RESILIENCE-ALPHA — LED Bicolore IoT</h2>";
    html += "<p>Etat actuel : <b>" + String((int)currentState) + "</b></p>";
    html += "<ul>";
    html += "<li><a style='color:#38bdf8' href='/led?state=GREEN_BLINK'>1. Visage Reconnu (Vert Clignotant)</a></li>";
    html += "<li><a style='color:#f87171' href='/led?state=RED_SOLID_30S'>2. Visage Non Reconnu (Rouge Fixe 30s)</a></li>";
    html += "<li><a style='color:#4ade80' href='/led?state=GREEN_SOLID_30S'>3. Mot de Passe Valide (Vert Fixe 30s)</a></li>";
    html += "<li><a style='color:#fb7185' href='/led?state=RED_BLINK_10X'>4. Mot de Passe Invalide (Rouge Clignotant 10x)</a></li>";
    html += "<li><a style='color:#94a3b8' href='/led?state=OFF'>0. Eteindre (Repos)</a></li>";
    html += "</ul></body></html>";
    server.send(200, "text/html", html);
}

void handleLedControl() {
    String stateArg = "";
    if (server.hasArg("state")) {
        stateArg = server.arg("state");
    }

    if (stateArg == "GREEN_BLINK") {
        changeState(STATE_GREEN_BLINKING, "HTTP: Visage reconnu");
    } else if (stateArg == "RED_SOLID_30S") {
        changeState(STATE_RED_SOLID_30S, "HTTP: Visage rejete");
    } else if (stateArg == "GREEN_SOLID_30S") {
        changeState(STATE_GREEN_SOLID_30S, "HTTP: Mot de passe valide");
    } else if (stateArg == "RED_BLINK_10X") {
        changeState(STATE_RED_BLINK_10X, "HTTP: Mot de passe invalide");
    } else if (stateArg == "DUAL_BLINK" || stateArg == "POLICE") {
        changeState(STATE_DUAL_BLINK, "HTTP: Clignotement continu bicolore");
    } else if (stateArg == "OFF") {
        changeState(STATE_OFF, "HTTP: Extinction");
    } else {
        server.send(400, "application/json", "{\"error\":\"Invalid state\"}");
        return;
    }

    server.send(200, "application/json", "{\"status\":\"OK\",\"current_state\":" + String((int)currentState) + "}");
}

void handleStatus() {
    String json = "{\"service\":\"esp8266-biometric-led\",\"state\":";
    json += String((int)currentState);
    json += ",\"uptime_ms\":";
    json += String(millis());
    json += ",\"ip\":\"";
    json += WiFi.localIP().toString();
    json += "\"}";
    server.send(200, "application/json", json);
}

// Lecture des commandes sur le port Serie USB (ex: CMD:GREEN_BLINK)
void processSerialCommands() {
    if (Serial.available()) {
        String line = Serial.readStringUntil('\n');
        line.trim();
        if (line.startsWith("CMD:")) {
            String cmd = line.substring(4);
            if (cmd == "GREEN_BLINK") {
                changeState(STATE_GREEN_BLINKING, "Serial: Visage reconnu");
            } else if (cmd == "RED_SOLID_30S") {
                changeState(STATE_RED_SOLID_30S, "Serial: Visage rejete");
            } else if (cmd == "GREEN_SOLID_30S") {
                changeState(STATE_GREEN_SOLID_30S, "Serial: Mot de passe valide");
            } else if (cmd == "RED_BLINK_10X") {
                changeState(STATE_RED_BLINK_10X, "Serial: Mot de passe invalide");
            } else if (cmd == "DUAL_BLINK" || cmd == "POLICE") {
                changeState(STATE_DUAL_BLINK, "Serial: Clignotement bicolore continu");
            } else if (cmd == "OFF") {
                changeState(STATE_OFF, "Serial: Extinction");
            } else if (cmd == "TEST_PINS") {
                Serial.println("[ESP-12F] Test alternatif des broches (Vert 2s, Rouge 2s)...");
                setPhysicalLeds(true, false);
                delay(2000);
                setPhysicalLeds(false, true);
                delay(2000);
                setPhysicalLeds(false, false);
                Serial.println("[ESP-12F] Test termine.");
            }
        }
    }
}

// Machine a etats non bloquante dans loop()
void updateStateMachine() {
    unsigned long now = millis();

    switch (currentState) {
        case STATE_OFF:
            setPhysicalLeds(false, false);
            break;

        case STATE_GREEN_BLINKING:
            // Vert clignote toutes les 350 ms jusqu'a reception mot de passe
            if (now - lastBlinkTime >= 350) {
                lastBlinkTime = now;
                blinkState = !blinkState;
                setPhysicalLeds(blinkState, false);
            }
            break;

        case STATE_RED_SOLID_30S:
            // Rouge fixe pendant 30 secondes (30000 ms) puis s'eteint
            setPhysicalLeds(false, true);
            if (now - stateStartTime >= 30000) {
                changeState(STATE_OFF, "Timeout 30s rouge ecoule");
            }
            break;

        case STATE_GREEN_SOLID_30S:
            // Vert fixe pendant 30 secondes (30000 ms) puis s'eteint
            setPhysicalLeds(true, false);
            if (now - stateStartTime >= 30000) {
                changeState(STATE_OFF, "Timeout 30s vert ecoule");
            }
            break;

        case STATE_RED_BLINK_10X:
            // Clignote en rouge 10 fois (cycle 250ms ON / 250ms OFF = 500ms par clignotement)
            if (now - lastBlinkTime >= 250) {
                lastBlinkTime = now;
                blinkState = !blinkState;
                setPhysicalLeds(false, blinkState);
                if (!blinkState) {
                    redBlinkCounter++;
                    if (redBlinkCounter >= 10) {
                        changeState(STATE_OFF, "Fin des 10 clignotements rouges");
                    }
                }
            }
            break;

        case STATE_DUAL_BLINK:
            // Clignote en continu en alternant Vert et Rouge (style gyrophare bicolore, 250ms)
            if (now - lastBlinkTime >= 250) {
                lastBlinkTime = now;
                blinkState = !blinkState;
                setPhysicalLeds(blinkState, !blinkState);
            }
            break;
    }
}

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\n\n=======================================================");
    Serial.println("  PROJECT RESILIENCE-ALPHA : ESP8266 Biometric LED");
    Serial.println("  Workshop EPSI 2026-27 — Consigne Additionnelle 1");
    Serial.println("=======================================================");

    pinMode(LED_GREEN_PIN, OUTPUT);
    pinMode(LED_RED_PIN, OUTPUT);
    setPhysicalLeds(false, false);

    // Initialisation Wi-Fi
    Serial.print("[WiFi] Connexion au point d'acces : ");
    Serial.println(WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.persistent(true);

    // IP statique recommandee pour correspondre a ESP_WIFI_URL (192.168.137.50)
    IPAddress staticIP(192, 168, 137, 50);
    IPAddress gateway(192, 168, 137, 1);
    IPAddress subnet(255, 255, 255, 0);
    IPAddress dns(192, 168, 137, 1);
    WiFi.config(staticIP, gateway, subnet, dns);

    WiFi.begin(WIFI_SSID, WIFI_PASS);

    // Tentative de connexion Wi-Fi non bloquante au demarrage
    unsigned long startAttempt = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < 10000) {
        delay(300);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.print("[WiFi] Connecte avec succes ! IP locale : ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("[WiFi] En attente du reseau RESILIENCE-G2 (Les commandes Serie USB restent 100% actives).");
    }

    server.on("/", handleRoot);
    server.on("/led", handleLedControl);
    server.on("/status", handleStatus);
    server.begin();
    Serial.println("[HTTP] Serveur REST actif sur le port 80");

    // Clignotement de bienvenue (Vert puis Rouge 500ms) pour prouver le bon fonctionnement
    setPhysicalLeds(true, false);
    delay(400);
    setPhysicalLeds(false, true);
    delay(400);
    setPhysicalLeds(false, false);
    Serial.println("[INIT] Pret a recevoir les evenements de reconnaissance faciale !");
}

void loop() {
    // Reconnexion automatique si perte de signal Wi-Fi
    static unsigned long lastWifiCheck = 0;
    if (WiFi.status() != WL_CONNECTED && (millis() - lastWifiCheck > 5000)) {
        lastWifiCheck = millis();
        WiFi.reconnect();
    }
    server.handleClient();
    processSerialCommands();
    updateStateMachine();
}
