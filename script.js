// --- CONFIGURATION PAR DÉFAUT (LFLG - Le Versoud) ---
const DEFAULT_VIEW = {
    latitude: 45.2178,
    longitude: 5.8492,
    zoom: 10.5,     // Environ 4500 FT
    pitch: 75,
    bearing: 0      // Plein Nord
};

window.currentViewState = { ...DEFAULT_VIEW };
const FT_CONSTANT = 65616797; 
let allAirspaces = []; // Stockage des données brutes pour le filtre

function altToZoom(altFt) { return Math.log2(FT_CONSTANT / altFt); }
function zoomToAlt(zoom) { return Math.round(FT_CONSTANT / Math.pow(2, zoom)); }

// --- COUCHES ---
const terrainLayer = new deck.TerrainLayer({
    id: 'terrain',
    elevationDecoder: {rScaler: 256, gScaler: 1, bScaler: 1 / 256, offset: -32768},
    elevationData: 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png',
    texture: 'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
    elevationMultiplier: 1.2
});

// Création de la couche GeoJson (vide au départ)
let airspaceLayer = new deck.GeoJsonLayer({ id: 'airspace' });

// --- CHARGEMENT DES DONNÉES ---
fetch('data.json')
    .then(res => res.json())
    .then(data => {
        allAirspaces = data.features;
        updateFloorFilter(40000); // Initialise avec tout afficher
    });

// --- MOTEUR ---
window.deckgl = new deck.Deck({
    container: 'map',
    viewState: window.currentViewState,
    controller: { maxPitch: 90 },
    layers: [terrainLayer],
    onViewStateChange: ({viewState}) => {
        window.currentViewState = viewState;
        window.deckgl.setProps({viewState: window.currentViewState});
        updateUI();
    }
});

// --- LOGIQUE DE FILTRE ---
window.updateFloorFilter = function(val) {
    const limit = parseInt(val);
    document.getElementById('filter-val').innerHTML = limit >= 40000 ? "Toutes" : limit + " FT";
    
    // On filtre les zones dont le plancher est inférieur à la limite choisie
    const filteredData = {
        type: "FeatureCollection",
        features: allAirspaces.filter(f => f.properties.floor_ft <= limit)
    };

    // On recrée la couche avec les données filtrées
    airspaceLayer = new deck.GeoJsonLayer({
        id: 'airspace',
        data: filteredData,
        stroked: true, filled: true, extruded: true, wireframe: true,
        getElevation: d => d.properties.thickness_m,
        getFillColor: d => d.properties.color,
        getLineColor: [255, 255, 255, 80],
        pickable: true,
        onHover: info => updateTooltip(info)
    });

    window.deckgl.setProps({ layers: [terrainLayer, airspaceLayer] });
};

// --- NAVIGATION & AUTO-REPEAT ---
let moveInterval = null;
window.startMove = function(latD, lonD) {
    if (moveInterval) return;
    moveCamera(latD, lonD);
    moveInterval = setInterval(() => moveCamera(latD, lonD), 50);
};
window.stopMove = function() { clearInterval(moveInterval); moveInterval = null; };

function moveCamera(latDiff, lonDiff) {
    window.currentViewState.latitude += latDiff;
    window.currentViewState.longitude += lonDiff;
    window.deckgl.setProps({ viewState: { ...window.currentViewState } });
}

window.recenter = function() {
    window.currentViewState = { ...DEFAULT_VIEW };
    window.deckgl.setProps({ viewState: { ...window.currentViewState } });
    updateUI();
};

window.updatePitch = function(val) {
    window.currentViewState.pitch = parseFloat(val);
    window.deckgl.setProps({ viewState: { ...window.currentViewState } });
};

window.updateAltitude = function(val) {
    window.currentViewState.zoom = altToZoom(parseFloat(val));
    window.deckgl.setProps({ viewState: { ...window.currentViewState } });
    updateUI();
};

function updateUI() {
    document.getElementById('pitch-slider').value = window.currentViewState.pitch;
    const currentAltFt = zoomToAlt(window.currentViewState.zoom);
    document.getElementById('alt-slider').value = currentAltFt;
    document.getElementById('alt-val').innerHTML = currentAltFt + " FT";
}

function updateTooltip(info) {
    const el = document.getElementById('tooltip');
    if (info.object) {
        const p = info.object.properties;
        el.innerHTML = `<strong>${p.name}</strong><br>Cl: ${p.class}<br>Alt: ${p.real_floor} / ${p.real_ceiling}`;
        el.style.display = 'block';
        el.style.left = (info.x + 15) + 'px';
        el.style.top = (info.y + 15) + 'px';
    } else { el.style.display = 'none'; }
}