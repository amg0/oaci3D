// --- CONFIGURATION PAR DÉFAUT (LFLG) ---
const DEFAULT_VIEW = {
    latitude: 45.2178,
    longitude: 5.8492,
    zoom: 10.5,
    pitch: 75,
    bearing: 0 // Nord
};

window.currentViewState = { ...DEFAULT_VIEW };
const FT_CONSTANT = 65616797; 
let allAirspaces = [];

function altToZoom(altFt) { return Math.log2(FT_CONSTANT / altFt); }
function zoomToAlt(zoom) { return Math.round(FT_CONSTANT / Math.pow(2, zoom)); }

// --- MOTEUR ---
window.deckgl = new deck.Deck({
    container: 'map',
    viewState: window.currentViewState,
    controller: { maxPitch: 90 },
    layers: [],
    onViewStateChange: ({viewState}) => {
        window.currentViewState = viewState;
        window.deckgl.setProps({viewState: window.currentViewState});
        updateUI();
    }
});

// --- LOGIQUE DE DÉPLACEMENT RELATIF (TRIGONOMÉTRIE) ---
window.moveCamera = function(direction) {
    const step = 0.015; // Sensibilité du déplacement
    // Conversion du bearing en radians (0° est le Nord, rotation horaire)
    const angleRad = (window.currentViewState.bearing * Math.PI) / 180;

    let dLat = 0;
    let dLon = 0;

    switch(direction) {
        case 'UP':
            dLat = step * Math.cos(angleRad);
            dLon = step * Math.sin(angleRad);
            break;
        case 'DOWN':
            dLat = -step * Math.cos(angleRad);
            dLon = -step * Math.sin(angleRad);
            break;
        case 'LEFT':
            // On décale l'angle de -90° pour aller à gauche
            dLat = step * Math.cos(angleRad - Math.PI/2);
            dLon = step * Math.sin(angleRad - Math.PI/2);
            break;
        case 'RIGHT':
            // On décale l'angle de +90° pour aller à droite
            dLat = step * Math.cos(angleRad + Math.PI/2);
            dLon = step * Math.sin(angleRad + Math.PI/2);
            break;
    }

    window.currentViewState.latitude += dLat;
    window.currentViewState.longitude += dLon;
    window.deckgl.setProps({ viewState: { ...window.currentViewState } });
};

// --- AUTO-REPEAT ---
let moveInterval = null;
window.startMove = function(direction) {
    if (moveInterval) return;
    window.moveCamera(direction);
    moveInterval = setInterval(() => window.moveCamera(direction), 50);
};
window.stopMove = function() { clearInterval(moveInterval); moveInterval = null; };

// --- LE RESTE DES FONCTIONS (RECENTER, SLIDERS, TOOLTIP) ---
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

window.updateFloorFilter = function(val) {
    const limit = parseInt(val);
    document.getElementById('filter-val').innerHTML = limit >= 40000 ? "Toutes" : limit + " FT";
    const filteredData = {
        type: "FeatureCollection",
        features: allAirspaces.filter(f => f.properties.floor_ft <= limit)
    };
    // Re-création de la couche GeoJson (simplifié pour l'exemple)
    const layer = new deck.GeoJsonLayer({
        id: 'airspace',
        data: filteredData,
        stroked: true, filled: true, extruded: true, wireframe: true,
        getElevation: d => d.properties.thickness_m,
        getFillColor: d => d.properties.color,
        getLineColor: [255, 255, 255, 80],
        pickable: true,
        onHover: info => updateTooltip(info)
    });
    window.deckgl.setProps({ layers: [terrainLayer, layer] });
};

function updateUI() {
    document.getElementById('pitch-slider').value = window.currentViewState.pitch;
    const currentAltFt = zoomToAlt(window.currentViewState.zoom);
    document.getElementById('alt-slider').value = currentAltFt;
    document.getElementById('alt-val').innerHTML = currentAltFt + " FT";
}

// Couche terrain stable
const terrainLayer = new deck.TerrainLayer({
    id: 'terrain',
    elevationDecoder: {rScaler: 256, gScaler: 1, bScaler: 1 / 256, offset: -32768},
    elevationData: 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png',
    texture: 'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
    elevationMultiplier: 1.2
});

// Chargement initial
fetch('data.json').then(res => res.json()).then(data => {
    allAirspaces = data.features;
    window.updateFloorFilter(40000);
});

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