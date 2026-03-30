import requests
import re
import json
import webbrowser
import http.server
import socketserver
import threading
import sys

# ==========================================
# 1. LOGIQUE DE PARSING AÉRONAUTIQUE
# ==========================================

def parse_altitude_m(alt_str):
    """Convertit les altitudes OpenAir (SFC, FL, FT) en mètres."""
    alt_str = str(alt_str).upper().strip()
    if not alt_str or 'SFC' in alt_str or 'GND' in alt_str: 
        return 0
    # Cas Flight Level : FL115 -> 11500 ft -> mètres
    match_fl = re.search(r'FL\s*(\d+)', alt_str)
    if match_fl: 
        return int(match_fl.group(1)) * 100 * 0.3048
    # Cas Pieds : 3500 [FT] -> mètres
    match_ft = re.search(r'(\d+)', alt_str)
    if match_ft: 
        return int(match_ft.group(1)) * 0.3048
    return 1000 

def build_floating_feature(zone, colors, max_alt_m):
    """Crée une entité GeoJSON 3D avec les métadonnées pour le filtrage JS."""
    zone_class = zone.get('class', 'U')
    # Choix de la couleur selon la classe (A, C, D, R, P, etc.)
    color = colors.get(zone_class[0] if zone_class else 'U', [150, 150, 150, 80])
    
    floor_m = zone.get('floor_m', 0)
    ceiling_m = zone.get('ceiling_m', 2000)
    
    # On calcule le plancher en pieds pour le slider de filtrage JS
    floor_ft = int(floor_m / 0.3048)
    
    # On limite l'affichage au plafond max (FL400)
    display_ceiling = min(ceiling_m, max_alt_m)
    thickness_m = max(0, display_ceiling - floor_m)
    
    # Construction des coordonnées 3D [Long, Lat, Altitude_Plancher]
    coords_3d = [[pt[0], pt[1], floor_m] for pt in zone['coords']]
    
    return {
        "type": "Feature",
        "properties": {
            "name": zone.get('name', 'Inconnu'),
            "class": zone_class,
            "thickness_m": thickness_m,
            "floor_ft": floor_ft, # Utilisé par le slider de filtrage
            "real_floor": zone.get('floor_txt', 'SFC'),
            "real_ceiling": zone.get('ceiling_txt', 'Inconnu'),
            "color": color
        },
        "geometry": {
            "type": "Polygon", 
            "coordinates": [coords_3d]
        }
    }

def update_airspace_data(url, limit_fl=400):
    """Télécharge, parse et sauvegarde les zones dans data.json."""
    print(f"📡 Téléchargement des zones (Filtre FL{limit_fl})...")
    limit_m = limit_fl * 100 * 0.3048
    
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"❌ Erreur de connexion : {e}")
        return False

    features = []
    current_zone = None
    colors = {
        'A': [255, 0, 0, 90], 'C': [255, 120, 0, 90], 'D': [0, 120, 255, 90],
        'E': [0, 200, 0, 80], 'R': [200, 0, 0, 110], 'P': [255, 0, 255, 110], 
        'Q': [200, 0, 0, 90], 'U': [150, 150, 150, 70]
    }

    for line in res.text.split('\n'):
        line = line.strip()
        if not line or line.startswith('*'): continue
        
        if line.startswith('AC '): # Classe
            if current_zone and len(current_zone.get('coords', [])) >= 3:
                if current_zone.get('floor_m', 0) < limit_m:
                    features.append(build_floating_feature(current_zone, colors, limit_m))
            current_zone = {'class': line[3:].strip(), 'coords': []}
        
        elif line.startswith('AN ') and current_zone: # Nom
            current_zone['name'] = line[3:].strip()
        
        elif line.startswith('AL ') and current_zone: # Plancher (Low)
            current_zone['floor_m'] = parse_altitude_m(line[3:])
            current_zone['floor_txt'] = line[3:].strip()
            
        elif line.startswith('AH ') and current_zone: # Plafond (High)
            current_zone['ceiling_m'] = parse_altitude_m(line[3:])
            current_zone['ceiling_txt'] = line[3:].strip()
            
        elif line.startswith('DP ') and current_zone: # Coordonnées
            m = re.match(r'DP\s+(\d+):(\d+):(\d+)\s+([NS])\s+(\d+):(\d+):(\d+)\s+([EW])', line)
            if m:
                lat = int(m.group(1)) + int(m.group(2))/60 + int(m.group(3))/3600
                if m.group(4) == 'S': lat = -lat
                lon = int(m.group(5)) + int(m.group(6))/60 + int(m.group(7))/3600
                if m.group(8) == 'W': lon = -lon
                current_zone['coords'].append([lon, lat])

    # Sauvegarde finale
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)
    print(f"✅ data.json généré ({len(features)} zones).")
    return True

# ==========================================
# 2. SERVEUR ET LANCEUR
# ==========================================

if __name__ == "__main__":
    # URL Planeur.net pour la France
    AIRSPACE_URL = "https://planeur-net.github.io/airspace/france.txt"
    
    # 1. Mise à jour des données
    if not update_airspace_data(AIRSPACE_URL, limit_fl=400):
        print("⚠️ Impossible de mettre à jour les données. Utilisation du cache si existant.")

    # 2. Configuration du serveur
    PORT = 8000
    Handler = http.server.SimpleHTTPRequestHandler
    
    # Autorise la réutilisation du port immédiatement après l'arrêt
    socketserver.TCPServer.allow_reuse_address = True
    
    try:
        httpd = socketserver.TCPServer(("", PORT), Handler)
    except Exception as e:
        print(f"❌ Erreur port {PORT} : {e}")
        sys.exit(1)

    # 3. Lancement du serveur dans un thread séparé (Daemon)
    # daemon=True permet au thread de s'arrêter dès que le script principal s'arrête
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    
    print(f"\n🚀 CARTE 3D ACTIVE : http://localhost:{PORT}")
    print("📍 Position par défaut : LFLG (Le Versoud)")
    webbrowser.open(f"http://localhost:{PORT}")

    # 4. Boucle d'attente utilisateur
    print("\n" + "="*50)
    print("  LE SERVEUR TOURNE. GARDE CETTE FENÊTRE OUVERTE.")
    print("  POUR ARRÊTER : Appuie sur [ENTRÉE] ici.")
    print("="*50 + "\n")
    
    try:
        input() # Attend que l'utilisateur appuie sur Entrée
    except KeyboardInterrupt:
        pass

    print("🛑 Arrêt en cours...")
    httpd.shutdown()
    httpd.server_close()
    print("👋 Serveur éteint. Bon vol !")