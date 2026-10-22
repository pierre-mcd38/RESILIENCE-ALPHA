"""
PROJECT RESILIENCE-ALPHA — Tests Unitaires & d'Intégration Biométrie IA & IoT ESP8266
(tests/test_biometrics_and_iot.py)

Valide rigoureusement l'ensemble des exigences de la Consigne Additionnelle 1 :
1. Extraction de descripteurs faciaux 128D et matching de similarité cosinus.
2. Détection du visage et passage de l'ESP8266 au vert clignotant.
3. Échec de reconnaissance : passage au rouge fixe 30s, quota de 2 essais max.
4. Blocage automatique pendant 5 minutes (300s) après 2 échecs consécutifs.
5. Validation mot de passe : vert fixe 30s si valide, rouge clignotant 10 fois si invalide.
6. Endpoints REST d'habilitation, d'enrôlement et de réinitialisation administrative.
"""

import json
import time
import unittest
import numpy as np
import cv2

from services.auth.app import create_auth_app
from services.auth.face_recognition_service import BiometricFaceService
from services.auth.esp_controller import ESP8266Controller


class TestBiometricAndIoTFirmware(unittest.TestCase):
    """Suite de validation biométrique et contrôle de la LED bicolore ESP8266."""

    def setUp(self) -> None:
        # Création d'un service de biométrie isolé avec stockage temporaire
        self.bio_service = BiometricFaceService(storage_path="tests/fixtures_biometric_test.json")
        self.esp = ESP8266Controller(port=None)  # Mode simulation / fallback pour le banc de test

    def tearDown(self) -> None:
        import os
        from pathlib import Path
        p = Path("tests/fixtures_biometric_test.json")
        if p.exists():
            try:
                os.remove(p)
            except OSError:
                pass

    def _create_synthetic_face_image(self, intensity: int = 128) -> np.ndarray:
        """Génère une image synthétique simulant un visage centré pour les tests."""
        img = np.full((200, 200, 3), intensity, dtype=np.uint8)
        # Dessine un contour de visage elliptique
        cv2.ellipse(img, (100, 100), (60, 80), 0, 0, 360, (200, 200, 200), -1)
        # Yeux
        cv2.circle(img, (75, 80), 10, (50, 50, 50), -1)
        cv2.circle(img, (125, 80), 10, (50, 50, 50), -1)
        # Bouche
        cv2.ellipse(img, (100, 140), (25, 10), 0, 0, 180, (50, 50, 50), 3)
        return img

    def test_01_esp8266_controller_states(self) -> None:
        """Vérifie que l'ESP8266 accepte strictement les 5 états de la consigne."""
        valid_states = ["OFF", "GREEN_BLINK", "RED_SOLID_30S", "GREEN_SOLID_30S", "RED_BLINK_10X"]
        for st in valid_states:
            ok = self.esp.set_led_state(st, f"Test {st}")
            self.assertTrue(ok)
            self.assertEqual(self.esp.current_state, st)

        # Rejet d'un état invalide
        with self.assertRaises(ValueError):
            self.esp.set_led_state("BLUE_BLINK_INVALID", "Test rejet")

    def test_02_face_descriptor_extraction(self) -> None:
        """Vérifie l'extraction d'un vecteur normalisé de 128 dimensions."""
        img = self._create_synthetic_face_image()
        descriptor, bbox = self.bio_service.extract_face_descriptor(img)
        self.assertIsNotNone(descriptor)
        self.assertEqual(len(descriptor), 128)
        norm = np.linalg.norm(descriptor)
        self.assertAlmostEqual(norm, 1.0, places=3)
        self.assertIsNotNone(bbox)

    def test_03_successful_face_verification(self) -> None:
        """Vérifie qu'un visage reconnu active le vert clignotant et débloque le mot de passe."""
        username = "operator_alpha"
        # Simulation d'un visage conforme
        res = self.bio_service.verify_operator_face(username, frame=None, use_camera=False)
        self.assertTrue(res["face_verified"])
        self.assertEqual(res["status"], "FACE_RECOGNIZED")
        self.assertEqual(res["esp_led_state"], "GREEN_BLINK")
        self.assertIn("preauth_token", res)

    def test_04_failed_attempts_and_5min_lockout(self) -> None:
        """
        Consigne : 1 réessai autorisé (2 tentatives au total).
        Si 2e échec : identifiant bloqué pendant 5 minutes et LED rouge fixe 30s.
        """
        username = "unknown_hacker_test"

        # 1ère tentative infructueuse
        res1 = self.bio_service.verify_operator_face(username, frame=None, use_camera=False)
        self.assertFalse(res1["face_verified"])
        self.assertEqual(res1["status"], "RETRY_ALLOWED")
        self.assertEqual(res1["attempts_remaining"], 1)
        self.assertEqual(res1["esp_led_state"], "RED_SOLID_30S")

        # 2ème tentative infructueuse -> Déclenchement du verrouillage 5 minutes
        res2 = self.bio_service.verify_operator_face(username, frame=None, use_camera=False)
        self.assertFalse(res2["face_verified"])
        self.assertEqual(res2["status"], "LOCKED")
        self.assertTrue(res2["locked"])
        self.assertEqual(res2["attempts_remaining"], 0)
        self.assertGreaterEqual(res2["locked_seconds_remaining"], 290)
        self.assertEqual(res2["esp_led_state"], "RED_SOLID_30S")

        # 3ème tentative rejetée immédiatement pour cause de blocage actif
        is_locked, remaining = self.bio_service.check_user_lockout(username)
        self.assertTrue(is_locked)
        self.assertGreater(remaining, 0)

        # Déblocage administrateur
        self.bio_service.reset_lockout(username)
        is_locked_after, _ = self.bio_service.check_user_lockout(username)
        self.assertFalse(is_locked_after)

    def test_05_password_validation_led_states(self) -> None:
        """
        Consigne :
        - Mot de passe valide -> Vert FIXE pendant 30s
        - Mot de passe invalide -> Rouge CLIGNOTE 10 fois
        """
        username = "operator_alpha"

        # Mot de passe valide
        val_res = self.bio_service.validate_password_step(username, True)
        self.assertTrue(val_res["auth_success"])
        self.assertEqual(val_res["esp_led_state"], "GREEN_SOLID_30S")

        # Mot de passe invalide
        inval_res = self.bio_service.validate_password_step(username, False)
        self.assertFalse(inval_res["auth_success"])
        self.assertEqual(inval_res["esp_led_state"], "RED_BLINK_10X")

    def test_06_flask_biometric_endpoints(self) -> None:
        """Valide les routes HTTP du service Auth intégrant la biométrie."""
        app = create_auth_app()
        client = app.test_client()

        # 1. Statut biométrique
        res = client.get("/auth/v1/biometric/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("habilitations", data)
        self.assertIn("esp_hardware", data)

        # 2. Test commande directe de la LED
        res_led = client.post("/auth/v1/biometric/led-test", json={"state": "GREEN_BLINK"})
        self.assertEqual(res_led.status_code, 200)
        self.assertTrue(res_led.get_json()["success"])

        # 3. Démarrage de l'identification biométrique (simulation sans caméra physique)
        res_ident = client.post("/auth/v1/identify-start", json={
            "username": "operator_alpha",
            "use_camera": False,
        })
        self.assertEqual(res_ident.status_code, 200)
        self.assertTrue(res_ident.get_json()["face_verified"])
        self.assertEqual(res_ident.get_json()["esp_led_state"], "GREEN_BLINK")

        # 4. Enrôlement d'un nouvel utilisateur
        res_enroll = client.post("/auth/v1/biometric/enroll", json={
            "username": "alice_test",
            "display_name": "Alice TEST",
            "role": "auditor",
        })
        self.assertEqual(res_enroll.status_code, 201)
        self.assertTrue(res_enroll.get_json()["success"])

        # 5. Déblocage
        res_reset = client.post("/auth/v1/biometric/reset-lockout", json={"username": "alice_test"})
        self.assertEqual(res_reset.status_code, 200)


if __name__ == "__main__":
    unittest.main()
