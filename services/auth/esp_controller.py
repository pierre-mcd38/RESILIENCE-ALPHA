"""
PROJECT RESILIENCE-ALPHA — Contrôleur de l'Objet Connecté ESP8266 (services/auth/esp_controller.py)
Pilote la LED Bicolore (Rouge/Vert) sur l'ESP-12F conformément à la Consigne Additionnelle 1 :
- Liaison Série USB directe (COM6 @ 115200 baud) avec reconnexion automatique.
- Liaison HTTP Wi-Fi de secours (http://<esp_ip>/led?state=...).
- Machine à états miroir pour synchronisation de l'état vers le Back-office.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, Optional
import requests

try:
    import serial
except ImportError:
    serial = None

logger = logging.getLogger("esp8266_controller")


class ESP8266Controller:
    """Gestionnaire de communication Série et Wi-Fi avec l'objet connecté ESP8266."""

    STATE_OFF = "OFF"
    STATE_GREEN_BLINK = "GREEN_BLINK"
    STATE_RED_SOLID_30S = "RED_SOLID_30S"
    STATE_GREEN_SOLID_30S = "GREEN_SOLID_30S"
    STATE_RED_BLINK_10X = "RED_BLINK_10X"

    def __init__(
        self,
        port: str = "COM6",
        baudrate: int = 115200,
        wifi_url: Optional[str] = None,
    ) -> None:
        self.port = os.environ.get("ESP_SERIAL_PORT", port)
        self.baudrate = baudrate
        self.wifi_url = wifi_url or os.environ.get("ESP_WIFI_URL", "http://192.168.137.50")
        self.current_state = self.STATE_OFF
        self.last_transition_time = time.time()
        self.last_trigger_reason = "Initialisation"
        self._lock = threading.Lock()
        self._serial_conn: Optional[Any] = None

    def _get_serial(self) -> Optional[Any]:
        if serial is None or not self.port:
            return None
        with self._lock:
            if self._serial_conn is not None:
                try:
                    if self._serial_conn.is_open:
                        return self._serial_conn
                    else:
                        self._serial_conn.open()
                        if self._serial_conn.is_open:
                            return self._serial_conn
                except Exception:
                    self._serial_conn = None

            try:
                self._serial_conn = serial.Serial(self.port, self.baudrate, timeout=0.5)
                time.sleep(0.05)
                return self._serial_conn
            except Exception as e:
                # Port peut être temporairement inaccessible ou occupé
                logger.debug(f"Connexion série {self.port} indisponible: {e}")
                self._serial_conn = None
                return None

    def set_led_state(self, state: str, reason: str = "") -> Dict[str, Any]:
        """
        Envoie l'ordre de changement d'état à l'ESP8266 (Série + HTTP Wi-Fi).
        Garantit que la commande passe même si l'un des canaux est hors-ligne.
        """
        valid_states = {
            self.STATE_OFF,
            self.STATE_GREEN_BLINK,
            self.STATE_RED_SOLID_30S,
            self.STATE_GREEN_SOLID_30S,
            self.STATE_RED_BLINK_10X,
        }
        if state not in valid_states:
            raise ValueError(f"État LED inconnu : {state}")

        self.current_state = state
        self.last_transition_time = time.time()
        self.last_trigger_reason = reason
        serial_ok = False
        wifi_ok = False

        # 1. Envoi via Port Série USB (COM6)
        conn = self._get_serial()
        if conn:
            try:
                cmd = f"CMD:{state}\n"
                conn.write(cmd.encode("utf-8"))
                conn.flush()
                serial_ok = True
                logger.info(f"[ESP-12F Série] Ordre envoyé : {cmd.strip()} ({reason})")
            except Exception as e:
                logger.warning(f"[ESP-12F Série] Erreur envoi : {e}")
                self._serial_conn = None

        # 2. Envoi via HTTP Wi-Fi si configuré
        if self.wifi_url:
            try:
                r = requests.get(
                    f"{self.wifi_url}/led",
                    params={"state": state},
                    headers={"Connection": "close"},
                    timeout=0.8,
                )
                if r.status_code == 200:
                    wifi_ok = True
                    logger.info(f"[ESP-12F Wi-Fi] Ordre acquitté : {state}")
            except Exception:
                pass

        return {
            "state": self.current_state,
            "timestamp": time.time(),
            "trigger_reason": reason,
            "serial_dispatched": serial_ok,
            "wifi_dispatched": wifi_ok,
            "hardware_port": self.port,
        }

    def get_status(self) -> Dict[str, Any]:
        """Retourne l'état courant de la LED et les canaux matériels."""
        return {
            "current_state": self.current_state,
            "last_transition_time": self.last_transition_time,
            "last_trigger_reason": self.last_trigger_reason,
            "serial_port": self.port,
            "wifi_url": self.wifi_url,
            "hardware_connected": self._get_serial() is not None,
        }


# Instance singleton globale
esp_controller = ESP8266Controller()
