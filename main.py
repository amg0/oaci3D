import requests
import re
import json
import webbrowser
import http.server
import socketserver

# --- PARSING ---
def parse_altitude_m(alt_str):
    alt_str = str(alt_str).upper()
    if 'SFC' in alt_str or 'GND' in alt_str: return 0
    match_fl = re.search(r'FL\s*(\d+)', alt_str)
    if match_fl: return int(match_fl.group(1)) * 100 * 0.3048
    match_ft = re.search(r'(\d+)', alt_str)
    if match_ft: return int(match_ft.group(1)) * 0.3048
    return 1000 

def build_floating_feature(zone, colors, max_alt_m):
    zone_class = zone.get('class', 'U')
    color = colors.get(zone_class[0] if zone_class else 'U', [150, 150, 150, 80])
    floor_m = zone.get('floor_m', 0)
    display_ceiling = min(zone.get('ceiling_m', 1500), max_alt_m)
    thickness_m = max(0, display_ceiling - floor_m)
    coords_3d = [[pt[0], pt[1], floor_m] for pt in zone['coords']]
    
    return {
        "type": "Feature",
        "properties": {
            "name": zone.get('name', 'Inconnu'),
            "class": zone_class,
            "thickness_m": thickness_m,
            "real_floor": zone.get('floor_txt', 'SFC'),
            "real_ceiling": zone.get('ceiling_txt', 'Inconnu'),
            "color": color
        },
        "geometry": {"type": "Polygon", "coordinates": [coords_3d]}
    }

def load_airspace_data(url, max_fl=115):
    print("📡 Mise à jour des données (data.json)...")
    try:
        response = requests.get(url)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Erreur réseau : {e}")
        return None
        
    lines = response.text.split('\n')
    features = []
    current_zone = None
    max_alt_m = max_fl * 100 * 0.3048
    colors = {
        'A': [255, 0, 0, 80], 'C': [255, 100, 0, 80], 'D': [0, 100, 255, 80],
        'E': [0, 200, 0, 80], 'R': [150, 0, 0, 100], 'P': [255, 0, 255, 100], 'Q': [200, 0, 0, 80]
    }

    for line in lines:
        line = line.strip()
        if not line or line.startswith('*'): continue
        if line.startswith('AC '):
            if current_zone and len(current_zone.get('coords', [])) >= 3:
                if current_zone.get('floor_m', 0) < max_alt_m:
                    features.append(build_floating_feature(current_zone, colors, max_alt_m))
            current_zone = {'class': line[3:].strip(), 'coords': []}
        elif line.startswith('AN ') and current_zone: current_zone['name'] = line[3:].strip()
        elif line.startswith('AL ') and current_zone:
            current_zone['floor_m'] = parse_altitude_m(line[3:].strip())
            current_zone['floor_txt'] = line[3:].strip()
        elif line.startswith('AH ') and current_zone:
            current_zone['ceiling_m'] = parse_altitude_m(line[3:].strip())
            current_zone['ceiling_txt'] = line[3:].strip()
        elif line.startswith('DP ') and current_zone:
            match = re.match(r'DP\s+(\d+):(\d+):(\d+)\s+([NS])\s+(\d+):(\d+):(\d+)\s+([EW])', line)
            if match:
                lat_d, lat_m, lat_s, lat_dir, lon_d, lon_m, lon_s, lon_dir = match.groups()
                lat = int(lat_d) + int(lat_m)/60 + int(lat_s)/3600
                if lat_dir == 'S': lat = -lat
                lon = int(lon_d) + int(lon_m)/60 + int(lon_s)/3600
                if lon_dir == 'W': lon = -lon
                current_zone['coords'].append([lon, lat])
    return {"type": "FeatureCollection", "features": features}

# --- ORCHESTRATEUR ---
if __name__ == "__main__":
    URL = "https://planeur-net.github.io/airspace/france.txt"
    geojson = load_airspace_data(URL, max_fl=115)

    if geojson:
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(geojson, f)
        print("✅ Fichier data.json actualisé.")

    PORT = 8000
    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    print(f"🌐 Lancement sur http://localhost:{PORT}")
    webbrowser.open(f"http://localhost:{PORT}")

    try:
        with ReusableTCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Serveur arrêté.")