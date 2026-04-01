import requests
import re
import json
import webbrowser
import http.server
import socketserver
import threading
import sys

# ==========================================
# ⚙️ CONFIGURATION ET CONSTANTES
# ==========================================
PORT = 8000
AIRSPACE_URL = "https://planeur-net.github.io/airspace/france.txt"
FL_LIMIT = 300  # Plafond de l'espace aérien à afficher (FL300)
DATA_FILE = "data.json"

# Couleurs des zones [R, G, B, Opacité]
ZONE_COLORS = {
    'A': [255, 0, 0, 95],      # Rouge (Interdit/Strict)
    'C': [255, 120, 0, 95],    # Orange
    'D': [0, 120, 255, 95],    # Bleu (TMA/CTR)
    'E': [0, 200, 0, 85],      # Vert
    'R': [200, 0, 0, 120],     # Rouge foncé (Restreint)
    'P': [255, 0, 255, 120],   # Violet (Prohibé)
    'Q': [200, 0, 0, 95],      # Danger
    'U': [150, 150, 150, 75]   # Gris (Inconnu/Autre)
}

# Constantes de conversion
FT_TO_M = 0.3048
M_TO_FT = 3.28084

# ==========================================
# 🛠️ LOGIQUE DE CALCUL ET PARSING
# ==========================================

def parse_altitude_m(alt_str):
    """Analyse les chaînes OpenAir et retourne une altitude en mètres."""
    alt_str = str(alt_str).upper().strip()
    if not alt_str or 'SFC' in alt_str or 'GND' in alt_str: 
        return 0
    
    # Cas Flight Level (ex: FL115)
    match_fl = re.search(r'FL\s*(\d+)', alt_str)
    if match_fl: 
        return int(match_fl.group(1)) * 100 * FT_TO_M
    
    # Cas Pieds (ex: 3500 FT)
    match_ft = re.search(r'(\d+)', alt_str)
    if match_ft: 
        return int(match_ft.group(1)) * FT_TO_M
    
    return 1000 # Valeur de secours

def build_feature(zone, max_alt_m):
    """Construit un objet GeoJSON 3D pour une zone donnée."""
    z_class = zone.get('class', 'U')
    color = ZONE_COLORS.get(z_class[0] if z_class else 'U', ZONE_COLORS['U'])
    
    floor_m = zone.get('floor_m', 0)
    ceiling_m = zone.get('ceiling_m', 10000)
    
    # Calcul des métadonnées pour le JS
    floor_ft = int(floor_m * M_TO_FT)
    
    # Épaisseur pour l'extrusion Deck.gl
    display_ceiling = min(ceiling_m, max_alt_m)
    thickness_m = max(0, display_ceiling - floor_m)
    
    # Coordonnées 3D : [Longitude, Latitude, Altitude_Plancher]
    coords_3d = [[pt[0], pt[1], floor_m] for pt in zone['coords']]
    
    return {
        "type": "Feature",
        "properties": {
            "name": zone.get('name', 'Inconnu'),
            "class": z_class,
            "thickness_m": thickness_m,
            "floor_ft": floor_ft,
            "real_floor": zone.get('floor_txt', 'SFC'),
            "real_ceiling": zone.get('ceiling_txt', 'Inconnu'),
            "color": color
        },
        "geometry": {
            "type": "Polygon", 
            "coordinates": [coords_3d]
        }
    }

def process_airspaces():
    """Récupère et transforme les données OpenAir."""
    print(f"📡 Récupération des données OpenAir (Limite FL{FL_LIMIT})...")
    limit_m = FL_LIMIT * 100 * FT_TO_M
    
    try:
        res = requests.get(AIRSPACE_URL, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"❌ Erreur de téléchargement : {e}")
        return False

    features = []
    current_zone = None

    for line in res.text.split('\n'):
        line = line.strip()
        if not line or line.startswith('*'): continue
        
        if line.startswith('AC '): # Nouvelle Zone (Classe)
            if current_zone and len(current_zone.get('coords', [])) >= 3:
                if current_zone.get('floor_m', 0) < limit_m:
                    features.append(build_feature(current_zone, limit_m))
            current_zone = {'class': line[3:].strip(), 'coords': []}
        
        elif line.startswith('AN ') and current_zone: # Nom
            current_zone['name'] = line[3:].strip()
        
        elif line.startswith('AL ') and current_zone: # Plancher
            current_zone['floor_m'] = parse_altitude_m(line[3:])
            current_zone['floor_txt'] = line[3:].strip()
            
        elif line.startswith('AH ') and current_zone: # Plafond
            current_zone['ceiling_m'] = parse_altitude_m(line[3:])
            current_zone['ceiling_txt'] = line[3:].strip()
            
        elif line.startswith('DP ') and current_zone: # Point
            m = re.match(r'DP\s+(\d+):(\d+):(\d+)\s+([NS])\s+(\d+):(\d+):(\d+)\s+([EW])', line)
            if m:
                lat = int(m.group(1)) + int(m.group(2))/60 + int(m.group(3))/3600
                if m.group(4) == 'S': lat = -lat
                lon = int(m.group(5)) + int(m.group(6))/60 + int(m.group(7))/3600
                if m.group(8) == 'W': lon = -lon
                current_zone['coords'].append([lon, lat])

    # Enregistrement du fichier JSON
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)
    
    print(f"✅ {DATA_FILE} mis à jour avec {len(features)} zones.")
    return True

# ==========================================
# 🚀 SERVEUR ET EXÉCUTION
# ==========================================

if __name__ == "__main__":
    # 1. Mise à jour des données au lancement
    process_airspaces()

    # 2. Préparation du serveur HTTP
    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler)
    except Exception as e:
        print(f"❌ Impossible de lancer le serveur sur le port {PORT}: {e}")
        sys.exit(1)

    # 3. Lancement du serveur en arrière-plan (Thread Daemon)
    # daemon=True permet d'arrêter le serveur dès que le script Python s'arrête
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    
    print("\n" + "="*50)
    print(f"🚀 CARTE VFR 3D DISPONIBLE : http://localhost:{PORT}")
    print(f"📍 Point de vue initial : LFLG (Grenoble Le Versoud)")
    print("="*50)
    
    webbrowser.open(f"http://localhost:{PORT}")

    # 4. Interface de contrôle dans le terminal
    print("\n[SYSTÈME] Le serveur tourne. La carte est active.")
    print("[SYSTÈME] Appuie sur [ENTRÉE] dans ce terminal pour quitter proprement.")
    
    try:
        input() # Attente utilisateur
    except KeyboardInterrupt:
        pass

    print("\n🛑 Signal d'arrêt reçu. Fermeture du serveur...")
    httpd.shutdown()
    httpd.server_close()
    print("👋 À bientôt pour un prochain vol !")