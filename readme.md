# Carte VFR 3D 🛩️🗺️

Une application web interactive en 3D pour la visualisation des espaces aériens et du relief (VFR) en France. Conçue avec **deck.gl** pour le rendu 3D haute performance et **Python** pour le traitement dynamique des données aéronautiques.

## ✨ Fonctionnalités

* **Rendu 3D du relief :** Utilise les tuiles d'élévation AWS et les textures OpenStreetMap.
* **Espaces Aériens Extrudés :** Téléchargement dynamique et traitement du GeoJSON de l'espace aérien français. Les zones sont colorées par classe (A, C, D, E, TMA, Zones R/P/D) et extrudées en 3D selon leurs planchers et plafonds réels.
* **Interface de Pilotage (HUD) :**
    * Contrôle de l'altitude (jusqu'à 60 000 FT) et de l'inclinaison (Pitch).
    * Croix directionnelle (D-Pad) pour la navigation latérale et verticale.
    * Filtre dynamique pour masquer les zones aériennes au-dessus d'une certaine altitude.
    * Infobulles interactives (nom, classe, altitudes) au survol des zones.

## 🛠️ Architecture Technique

* **Frontend :** HTML5, CSS3, JavaScript (Vanilla), [deck.gl](https://deck.gl/).
* **Backend/Data :** Python 3 (modules standards `http.server`, `json`, `webbrowser` et le module externe `requests`).

## 📁 Structure du Projet

```text
.
├── index.html         # Interface utilisateur et structure du HUD
├── script.js          # Logique deck.gl, navigation caméra et filtres
└── main.py            # Script Python : télécharge/parse le GeoJSON, sert l'app et lance le navigateur
```

## 🚀 Installation et Lancement

1.  **Prérequis :** Assurez-vous d'avoir Python 3 installé sur votre machine.
2.  **Installer la dépendance requise :** Le script utilise la bibliothèque `requests` pour télécharger les données à jour.
    ```bash
    pip install requests
    ```
3.  **Lancer l'application :**
    Double-cliquez sur le fichier `main.py` ou lancez-le depuis votre terminal :
    ```bash
    python main.py
    ```
4.  **C'est prêt !** Le script va automatiquement :
    * Télécharger les données aéronautiques les plus récentes.
    * Générer le fichier de rendu `data.json`.
    * Démarrer un serveur web local sur le port 8000.
    * Ouvrir automatiquement votre navigateur par défaut sur `http://localhost:8000`.

## 📝 Sources des Données

* **Espaces Aériens :** Données GeoJSON fournies par [planeur-net.github.io](https://planeur-net.github.io/).
* **Relief :** Tuiles Terrarium d'Amazon Web Services (`elevation-tiles-prod`).
* **Cartographie :** OpenStreetMap.