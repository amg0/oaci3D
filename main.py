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
GEOJSON_URL = "https://planeur-net.github.io/airspace/france.geojson"
FL_LIMIT = 400  
DATA_FILE = "data.json"

# [Rouge, Vert, Bleu, Opacité]
ZONE_COLORS = {
    # Lettres simples (Classes de vol)
    'A': [255, 0, 0, 95],      
    'C': [255, 120, 0, 95],    
    'D': [0, 120, 255, 95],    # Bleu standard
    'E': [0, 200, 0, 85],      
    'U': [150, 150, 150, 75],  # Gris par défaut
    
    # Mots entiers (Types spécifiques)
    'TMA': [100, 200, 255, 95],    # Bleu clair
    'CTA': [100, 200, 255, 95]     # Bleu clair
}

FT_TO_M = 0.3048
M_TO_FT = 3.28084

# ==========================================
# 🛠️ LOGIQUE DE CALCUL ET PARSING
# ==========================================

def get_prop(props, keys, default):
    for k in keys:
        if k in props and props[k] is not None:
            return props[k]
    return default

def parse_altitude_m(alt_raw):
    if isinstance(alt_raw, dict):
        val = float(alt_raw.get('value', 0))
        unit = str(alt_raw.get('unit', '')).upper()
        
        if unit == 'FL': return int(val * 100 * FT_TO_M)
        elif unit in ['F', 'FT']: return int(val * FT_TO_M)
        elif unit == 'M': return int(val)
        return 1000

    alt_str = str(alt_raw).upper().strip()
    if not alt_str or 'SFC' in alt_str or 'GND' in alt_str: return 0
    match_fl = re.search(r'FL\s*(\d+)', alt_str)
    if match_fl: return int(match_fl.group(1)) * 100 * FT_TO_M
    match_ft = re.search(r'(\d+)', alt_str)
    if match_ft: return int(match_ft.group(1)) * FT_TO_M
    return 1000 

def format_altitude_text(alt_raw):
    if isinstance(alt_raw, dict):
        val = alt_raw.get('value', 0)
        unit = str(alt_raw.get('unit', '')).upper()
        ref = str(alt_raw.get('reference', '')).upper()
        if unit == 'FL': return f"FL {int(val)}"
        else: return f"{int(val)} {unit} {ref}".strip()
    return str(alt_raw)

def add_z_to_coordinates(coords, z_value):
    if isinstance(coords[0], (int, float)): 
        return [coords[0], coords[1], z_value]
    else:
        return [add_z_to_coordinates(c, z_value) for c in coords]

def process_geojson():
    print(f"📡 Téléchargement du GeoJSON source...")
    limit_m = FL_LIMIT * 100 * FT_TO_M
    
    try:
        res = requests.get(GEOJSON_URL, timeout=15)
        res.raise_for_status()
        source_data = res.json()
    except Exception as e:
        print(f"❌ Erreur de téléchargement : {e}")
        return False

    features_3d = []

    for feat in source_data.get('features', []):
        props = feat.get('properties', {})
        geom = feat.get('geometry')
        if not geom: continue

        name = get_prop(props, ['name', 'NAME', 'Name'], 'Inconnu')
        
        raw_class = get_prop(props, ['class', 'CLASS', 'Class'], 'U')
        raw_type = get_prop(props, ['type', 'TYPE', 'Type'], '')
        
        full_class = str(raw_class).upper().strip()
        full_type = str(raw_type).upper().strip()
        
        floor_raw = get_prop(props, ['lowerCeiling', 'lowerLimit', 'lower', 'LOWER', 'floor', 'FLOOR', 'bottom'], 'SFC')
        ceiling_raw = get_prop(props, ['upperCeiling', 'upperLimit', 'upper', 'UPPER', 'ceiling', 'CEILING', 'top'], '10000 FT')

        floor_m = parse_altitude_m(floor_raw)
        ceiling_m = parse_altitude_m(ceiling_raw)
        
        if floor_m >= limit_m:
            continue

        floor_ft = int(floor_m * M_TO_FT)
        display_ceiling = min(ceiling_m, limit_m)
        thickness_m = max(0, display_ceiling - floor_m)
        
        floor_txt = format_altitude_text(floor_raw)
        ceiling_txt = format_altitude_text(ceiling_raw)
        
        # --- LOGIQUE DE COULEUR ---
        # A. On détermine la couleur de base via la CLASSE
        if full_class in ZONE_COLORS:
            color = ZONE_COLORS[full_class]
        else:
            class_letter = full_class[0] if full_class else 'U'
            color = ZONE_COLORS.get(class_letter, ZONE_COLORS['U'])

        # B. OVERRIDE : Règle stricte pour les TYPES
        if full_type == 'RMZ' or full_type == 'TMZ':
            color = [150, 150, 150, 75]  # Gris discret pour RMZ/TMZ
        else:
            type_letter = full_type[0] if full_type else ''
            if type_letter in ['R', 'P', 'D']:
                color = [255, 0, 0, 120]  # Rouge vif pour Restreint/Prohibé/Danger
            
        # Création d'un libellé propre pour l'infobulle
        display_text = full_class
        if full_type and full_type != full_class:
            if full_class == 'U':
                display_text = full_type
            else:
                display_text = f"{full_type} (Class {full_class})"

        geom['coordinates'] = add_z_to_coordinates(geom['coordinates'], floor_m)

        feat['properties'] = {
            "name": str(name),
            "class": display_text,
            "thickness_m": thickness_m,
            "floor_ft": floor_ft,
            "real_floor": floor_txt,
            "real_ceiling": ceiling_txt,
            "color": color
        }
        
        features_3d.append(feat)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features_3d}, f)
    
    print(f"✅ {DATA_FILE} généré ({len(features_3d)} zones traitées avec succès).")
    return True

# ==========================================
# 🚀 SERVEUR ET EXÉCUTION
# ==========================================

if __name__ == "__main__":
    process_geojson()

    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler)
    except Exception as e:
        print(f"❌ Erreur port {PORT}: {e}")
        sys.exit(1)

    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    
    print("\n" + "="*50)
    print(f"🚀 CARTE VFR 3D DISPONIBLE : http://localhost:{PORT}")
    print("="*50)
    
    webbrowser.open(f"http://localhost:{PORT}")

    print("\n[SYSTÈME] Le serveur tourne. Appuie sur [ENTRÉE] ici pour quitter.")
    
    try:
        input()
    except KeyboardInterrupt:
        pass

    print("\n🛑 Fermeture du serveur...")
    httpd.shutdown()
    httpd.server_close()
    print("👋 À bientôt !")