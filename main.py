import requests
import re
import json
import webbrowser
import http.server
import socketserver
import os

# ==========================================
# 1. FONCTIONS OUTILS ET PARSING (LOGIQUE)
# ==========================================

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
    print("📡 Téléchargement des espaces aériens depuis Planeur.net...")
    response = requests.get(url)
    if response.status_code != 200: 
        print("❌ Erreur de téléchargement.")
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

# ==========================================
# 2. LE TEMPLATE HTML (FRONT-END NATIVE)
# ==========================================
# On utilise une chaîne brute simple pour éviter les conflits avec les accolades JS/CSS

HTML_CONTENT = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>Carte VFR 3D Native</title>
    <script src="https://unpkg.com/deck.gl@latest/dist.min.js"></script>
    <style>
        body { margin: 0; padding: 0; overflow: hidden; font-family: sans-serif; background: #000; }
        #map { width: 100vw; height: 100vh; position: absolute; top: 0; left: 0; }
        
        #hud {
            position: absolute; top: 20px; left: 20px; background: rgba(30, 30, 30, 0.85);
            padding: 20px; border-radius: 12px; color: white; z-index: 1000;
            backdrop-filter: blur(5px); box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        }
        
        .d-pad {
            display: grid; grid-template-columns: 45px 45px 45px; grid-template-rows: 45px 45px 45px;
            gap: 5px; margin-bottom: 20px; justify-content: center;
        }
        .d-pad button {
            background: #444; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 18px;
            display: flex; align-items: center; justify-content: center; transition: background 0.2s;
        }
        .d-pad button:hover { background: #666; }
        .d-pad button:active { background: #888; transform: scale(0.95); }
        .btn-up { grid-column: 2; grid-row: 1; }
        .btn-left { grid-column: 1; grid-row: 2; }
        .btn-right { grid-column: 3; grid-row: 2; }
        .btn-down { grid-column: 2; grid-row: 3; }

        .slider-group { display: flex; flex-direction: column; margin-bottom: 15px; }
        .slider-group label { font-size: 13px; margin-bottom: 5px; color: #ccc; font-weight: bold; }
        .slider-group input { width: 100%; cursor: pointer; }
        
        #tooltip {
            position: absolute; pointer-events: none; z-index: 1001; background: rgba(0, 0, 0, 0.9);
            color: white; padding: 12px; border-radius: 6px; font-size: 13px; display: none; 
            white-space: pre-wrap; box-shadow: 0 2px 10px rgba(0,0,0,0.3); border: 1px solid #444;
        }
        
        #loading {
            position: absolute; top: 20px; right: 20px; background: rgba(255, 100, 0, 0.9);
            color: white; padding: 10px 20px; border-radius: 8px; z-index: 1000;
            font-weight: bold; box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="tooltip"></div>
    <div id="loading">⏳ Chargement des espaces aériens...</div>

    <div id="hud">
        <h3 style="margin-top:0; text-align:center; margin-bottom:15px; font-size: 16px;">Navigation VFR</h3>
        
        <div class="d-pad">
            <button class="btn-up" onclick="moveCamera(0.05, 0)">⬆️</button>
            <button class="btn-left" onclick="moveCamera(0, -0.05)">⬅️</button>
            <button class="btn-right" onclick="moveCamera(0, 0.05)">➡️</button>
            <button class="btn-down" onclick="moveCamera(-0.05, 0)">⬇️</button>
        </div>

        <div class="slider-group">
            <label>Pitch (Inclinaison)</label>
            <input type="range" id="pitch-slider" min="0" max="90" value="75" oninput="updatePitch(this.value)">
        </div>
        <div class="slider-group">
            <label>Zoom (Hauteur)</label>
            <input type="range" id="zoom-slider" min="5" max="14" step="0.1" value="8" oninput="updateZoom(this.value)">
        </div>
    </div>

    <script>
        let currentViewState = {
            latitude: 45.36, 
            longitude: 5.32, 
            zoom: 8, 
            pitch: 75, 
            bearing: 90, 
            maxPitch: 90
        };

        const terrainLayer = new deck.TerrainLayer({
            id: 'terrain',
            elevationDecoder: {rScaler: 256, gScaler: 1, bScaler: 1 / 256, offset: -32768},
            elevationData: 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png',
            texture: 'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
            elevationMultiplier: 1.2
        });

        const deckgl = new deck.Deck({
            container: 'map',
            viewState: currentViewState, 
            controller: true,
            layers: [terrainLayer],
            onViewStateChange: ({viewState: newViewState}) => {
                currentViewState = newViewState;
                deckgl.setProps({viewState: currentViewState}); 
                document.getElementById('pitch-slider').value = currentViewState.pitch;
                document.getElementById('zoom-slider').value = currentViewState.zoom;
            }
        });

        fetch('airspace.json')
            .then(response => {
                if (!response.ok) throw new Error("Fichier JSON introuvable");
                return response.json();
            })
            .then(data => {
                document.getElementById('loading').style.display = 'none'; 
                const airspaceLayer = new deck.GeoJsonLayer({
                    id: 'airspace',
                    data: data,
                    stroked: true,
                    filled: true,
                    extruded: true,
                    wireframe: true,
                    getElevation: d => d.properties.thickness_m, 
                    getFillColor: d => d.properties.color,
                    getLineColor: [255, 255, 255, 80],
                    pickable: true,
                    onHover: info => updateTooltip(info)
                });
                deckgl.setProps({ layers: [terrainLayer, airspaceLayer] });
            })
            .catch(err => {
                document.getElementById('loading').innerHTML = "⚠️ Erreur: Lancer un serveur local !";
                document.getElementById('loading').style.background = "rgba(220, 0, 0, 0.9)";
                console.error("Erreur:", err);
            });

        function applyViewState() { 
            currentViewState = {...currentViewState};
            deckgl.setProps({viewState: currentViewState}); 
        }

        function moveCamera(latDiff, lonDiff) { 
            currentViewState.latitude += latDiff; 
            currentViewState.longitude += lonDiff; 
            applyViewState(); 
        }

        function updatePitch(val) { currentViewState.pitch = parseFloat(val); applyViewState(); }
        function updateZoom(val) { currentViewState.zoom = parseFloat(val); applyViewState(); }

        function updateTooltip(info) {
            const el = document.getElementById('tooltip');
            if (info.object) {
                const props = info.object.properties;
                el.innerHTML = `<strong style="font-size:14px; color:#4dabf7;">${props.name}</strong><br><br>` +
                               `<strong>Classe:</strong> ${props.class}<br>` +
                               `<strong>Plancher:</strong> ${props.real_floor}<br>` +
                               `<strong>Plafond:</strong> ${props.real_ceiling}`;
                el.style.display = 'block';
                el.style.left = info.x + 20 + 'px';
                el.style.top = info.y + 20 + 'px';
            } else {
                el.style.display = 'none';
            }
        }
    </script>
</body>
</html>"""

# ==========================================
# 3. ORCHESTRATION (LE MOTEUR PRINCIPAL)
# ==========================================
if __name__ == "__main__":
    
    # Étape A: Télécharger et Parser
    URL = "https://planeur-net.github.io/airspace/france.txt"
    geojson_france = load_airspace_data(URL, max_fl=115)

    if geojson_france:
        # Étape B: Créer les fichiers en local
        with open("airspace.json", "w", encoding="utf-8") as f:
            json.dump(geojson_france, f)
        print("✅ Fichier 'airspace.json' généré.")

        with open("index.html", "w", encoding="utf-8") as f:
            f.write(HTML_CONTENT)
        print("✅ Fichier 'index.html' généré.")

        # Étape C: Lancer le Serveur et le Navigateur
        PORT = 8000
        Handler = http.server.SimpleHTTPRequestHandler
        
        # Le ReusableTCPServer évite l'erreur "Address already in use" si on relance vite
        class ReusableTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        print("🌐 Ouverture du navigateur...")
        webbrowser.open(f"http://localhost:{PORT}")

        try:
            with ReusableTCPServer(("", PORT), Handler) as httpd:
                print(f"\n🚀 Serveur actif sur http://localhost:{PORT}")
                print("💡 Appuie sur Ctrl+C dans le terminal pour l'arrêter quand tu as fini.")
                httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Serveur arrêté correctement. Bons vols !")