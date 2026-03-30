import requests, re, json, webbrowser, http.server, socketserver

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
    # On utilise maintenant la limite FL400
    display_ceiling = min(zone.get('ceiling_m', 40000 * 0.3048), max_alt_m)
    thickness_m = max(0, display_ceiling - floor_m)
    coords_3d = [[pt[0], pt[1], floor_m] for pt in zone['coords']]
    return {
        "type": "Feature",
        "properties": {
            "name": zone.get('name', 'Inconnu'), "class": zone_class,
            "thickness_m": thickness_m, "real_floor": zone.get('floor_txt', 'SFC'),
            "real_ceiling": zone.get('ceiling_txt', 'Inconnu'), "color": color
        },
        "geometry": {"type": "Polygon", "coordinates": [coords_3d]}
    }

if __name__ == "__main__":
    print("📡 Mise à jour data.json (Filtre FL400)...")
    res = requests.get("https://planeur-net.github.io/airspace/france.txt")
    features = []
    current_zone = None
    colors = {'A': [255, 0, 0, 80], 'C': [255, 100, 0, 80], 'D': [0, 100, 255, 80], 'E': [0, 200, 0, 80], 'R': [150, 0, 0, 100], 'P': [255, 0, 255, 100], 'Q': [200, 0, 0, 80]}
    
    LIMIT_M = 12192 # FL400 en mètres

    for line in res.text.split('\n'):
        line = line.strip()
        if not line or line.startswith('*'): continue
        if line.startswith('AC '):
            if current_zone and len(current_zone.get('coords', [])) >= 3:
                if current_zone.get('floor_m', 0) < LIMIT_M:
                    features.append(build_floating_feature(current_zone, colors, LIMIT_M))
            current_zone = {'class': line[3:].strip(), 'coords': []}
        elif line.startswith('AN '): current_zone['name'] = line[3:].strip()
        elif line.startswith('AL '):
            current_zone['floor_m'] = parse_altitude_m(line[3:])
            current_zone['floor_txt'] = line[3:]
        elif line.startswith('AH '):
            current_zone['ceiling_m'] = parse_altitude_m(line[3:])
            current_zone['ceiling_txt'] = line[3:]
        elif line.startswith('DP '):
            match = re.match(r'DP\s+(\d+):(\d+):(\d+)\s+([NS])\s+(\d+):(\d+):(\d+)\s+([EW])', line)
            if match:
                lat_d, lat_m, lat_s, lat_dir, lon_d, lon_m, lon_s, lon_dir = match.groups()
                lat = int(lat_d) + int(lat_m)/60 + int(lat_s)/3600
                if lat_dir == 'S': lat = -lat
                lon = int(lon_d) + int(lon_m)/60 + int(lon_s)/3600
                if lon_dir == 'W': lon = -lon
                current_zone['coords'].append([lon, lat])

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)

    webbrowser.open("http://localhost:8000")
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", 8000), http.server.SimpleHTTPRequestHandler) as httpd:
        httpd.serve_forever()