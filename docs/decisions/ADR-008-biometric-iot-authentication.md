# ADR-008 : Authentification Renforcée Biométrique IA et Contrôle Matériel IoT (Consigne Additionnelle 1)

## 1. Statut
**ACCEPTÉ ET IMPLÉMENTÉ** (Conforme aux exigences impératives de la Consigne Additionnelle 1 — Workshop EPSI 2026-27 / Bac+5 M2).

## 2. Contexte et Problématique
Dans le cadre de l'épreuve de résilience de **PROJECT RESILIENCE-ALPHA**, une mise en demeure d'urgence (Consigne Additionnelle 1) impose le durcissement physique et biométrique de l'accès au back-office d'administration et de gestion des paiements :
1. **Déclenchement automatique de la caméra USB** connectée au PC Hôte lors de la saisie de l'identifiant.
2. **Reconnaissance faciale par IA légère** :
   - *Visage reconnu* : la LED bicolore de l'objet connecté ESP8266 clignote en vert jusqu'à la saisie du mot de passe ; le champ mot de passe est débloqué.
   - *Visage non reconnu* : la LED bicolore passe au rouge fixe pendant 30 secondes ; la caméra s'éteint ; le champ nom d'utilisateur est réinitialisé ; un seul réessai est autorisé (2 tentatives au total) avant un verrouillage strict de l'identifiant pendant 5 minutes (300 secondes).
3. **Contrôle du mot de passe** :
   - *Valide* : la LED bicolore passe au vert fixe pendant 30 secondes puis s'éteint ; l'accès au back-office est ouvert.
   - *Invalide* : la LED bicolore clignote 10 fois en rouge puis s'éteint ; le cycle complet d'identification recommence.
4. **Back-office** : interface d'administration permettant de gérer les habilitations biométriques, les profils enrôlés et de débloquer administrativement un compte verrouillé.
5. **Microcontrôleur ESP8266 (ESP-12F)** : micrologiciel développé sous JetBrains CLion + PlatformIO, pilotant une LED bicolore (Vert GPIO4 / D2, Rouge GPIO5 / D1) et connecté au réseau local / point d'accès Wi-Fi `RESILIENCE-G2`.

## 3. Architecture Technique et Choix d'Ingénierie

### 3.1 Détection et Extraction Biométrique Embarquée (OpenCV Haar Cascade + Sobel 128D)
- **Détection de visage** : classifieur en cascade de Haar (`haarcascade_frontalface_default.xml`) avec égalisation d'histogramme pour l'immunité aux variations d'éclairage.
- **Descripteur facial 128D** : calcul des gradients spatiaux de Sobel sur le masque normalisé de 128×128 pixels, condensé par pooling moyen et normalisé en norme \(L_2\).
- **Matching cosinus** : similarité cosinus \(\cos(\theta) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2}\) comparée au seuil calibré \(\tau = 0.70\).
- **Confinement matériel** : capture de la trame via OpenCV (`cv2.VideoCapture(0)`) puis libération immédiate (`cap.release()`) pour garantir que la caméra physique est éteinte dès la décision prise.

### 3.2 Automate Asynchrone de la LED Bicolore ESP-12F
Le micrologiciel C++ embarqué (`iot/esp8266_biometric_led/src/main.cpp`) implémente une machine à 5 états non bloquante régulée par `millis()` :

| État | Couleur / Comportement | Condition de déclenchement | Durée / Fin |
| :--- | :--- | :--- | :--- |
| `STATE_OFF` | Éteinte | Repos / initialisation / fin de temporisation | Permanente |
| `STATE_GREEN_BLINKING` | Vert clignotant (500 ms ON / 500 ms OFF) | Visage reconnu avec succès par l'IA | Jusqu'à saisie du mot de passe |
| `STATE_RED_SOLID_30S` | Rouge fixe continu | Visage non reconnu / compte bloqué | 30 secondes chrono, puis `STATE_OFF` |
| `STATE_GREEN_SOLID_30S` | Vert fixe continu | Mot de passe correct et JWT émis | 30 secondes chrono, puis `STATE_OFF` |
| `STATE_RED_BLINK_10X` | Rouge clignotant rapide (100 ms ON / 100 ms OFF) | Mot de passe invalide | 10 cycles complets, puis `STATE_OFF` |

### 3.3 Double Canal de Pilotage (Série USB COM6 + HTTP REST Wi-Fi)
Pour garantir une démonstration infaillible en toute circonstance :
1. **Canal primaire local USB** : commandes textuelles envoyées à 115 200 bauds sur le port série USB CH340 (`COM6`) (`CMD:GREEN_BLINK`, `CMD:RED_SOLID_30S`, etc.).
2. **Canal réseau Wi-Fi** : serveur Web HTTP REST embarqué sur l'ESP8266 (`http://192.168.137.50/led?state=...`), interrogeable depuis le réseau isolé `RESILIENCE-G2`.

### 3.4 Sécurité et Règle Anti-Force-Brute
- Compteur en mémoire protégé par verrou réentrant (`threading.RLock`).
- Après le 1er échec : état `RETRY_ALLOWED` (`attempts_remaining = 1`), réinitialisation du nom d'utilisateur dans le formulaire.
- Après le 2e échec : état `LOCKED`, verrouillage strict de 300 secondes (`lockout_seconds_remaining`), rejet de toute requête d'authentification avec code HTTP 423 (Locked).
- Déblocage administratif disponible pour les opérateurs SOC autorisés (`POST /auth/v1/biometric/reset-lockout`).

## 4. Preuves de Validation
- Tests unitaires et d'intégration validés (`tests/test_biometrics_and_iot.py` : 6/6 tests réussis).
- Synthèse globale du banc de recette (`tests/run_all_tests.py` : 21 tests exécutés, 0 échec).
- Micrologiciel compilé avec PlatformIO Core CLI et flashé sur ESP-12F sur `COM6` avec succès.
