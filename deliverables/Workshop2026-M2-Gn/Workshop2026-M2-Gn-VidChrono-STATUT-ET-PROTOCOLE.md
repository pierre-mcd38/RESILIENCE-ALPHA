# Statut du Livrable Vidéo (`Workshop2026-M2-Gn-VidChrono.mp4`)

- **Statut actuel** : **`MANQUANT / BLOCKED (En attente de captation réelle avec le 2e PC)`**
- **Règle d'intégrité respectée** : Conformément aux instructions impératives du projet (*« ne pas fabriquer une vidéo faisant croire à un test réel ; si aucune captation réelle n'est disponible, indiquer le livrable manquant »*), aucun fichier `.mp4` synthétique ou truqué n'a été généré.

## Procédure de Captation Réelle en 60 Secondes Maximum
1. Relier le **PC Hôte (`HDV0-INF-P08`)** et le **PC Attaquant** sur le point d'accès mobile Windows `RESILIENCE-Gn` (`192.168.137.1`).
2. Suivre le conducteur seconde par seconde défini dans [`docs/demo-runbook.md`](../../docs/demo-runbook.md) :
   - `00s - 08s` : Transaction initiale réussie (`T0`) sur le Dashboard React (`http://192.168.137.1:3000`).
   - `08s - 18s` : Lancement de `scenarios/controlled_attack.py` depuis le PC Attaquant et observation de la dégradation.
   - `18s - 28s` : Détection par le modèle `IsolationForest` (`SUSPECT` $\to$ `INCIDENT`) et corrélation de l'IP source.
   - `28s - 38s` : Remédiation autonome par `executor` (blocage dynamique WAF `HTTP 403` + recyclage workers API).
   - `38s - 50s` : Sonde métier automatique + nouvelle transaction opérateur réussie (`T5`) sous attaque filtrée (`RECOVERED`).
   - `50s - 58s` : Vérification finale de l'invariant comptable et de la chaîne d'audit SHA-256.
3. Enregistrer l'écran en continu (sans coupe) via **OBS Studio** ou **Windows Game Bar (`Win + Alt + R`)** et enregistrer le fichier sous :
   `deliverables/Workshop2026-M2-Gn/Workshop2026-M2-Gn-VidChrono.mp4`.
