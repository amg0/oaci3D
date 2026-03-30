// --- CONFIGURATION ---
window.currentViewState = {
    latitude: 45.36,
    longitude: 5.32,
    zoom: 9.3, // Correspond à environ 3000m
    pitch: 75,
    bearing: 90
};

// Fonctions de conversion (Approximation France 45°N)
function altToZoom(alt) {
    return Math.log2(20000000 / alt);
}
function zoomToAlt(zoom) {
    return Math.round(20000000 / Math.pow(2, zoom));
}

// --- COUCHES ---
const terrainLayer = new deck.TerrainLayer({
    id: 'terrain',
    elevationDecoder: {rScaler: 256, gScaler: 1, bScaler: 1 / 256, offset: -32768},
    elevationData: 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png',
    texture: 'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
    elevationMultiplier: 1.2
});

const airspaceLayer = new deck.GeoJsonLayer({
    id: 'airspace',
    data: 'data.json',
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

// --- MOTEUR ---
window.deckgl = new deck.Deck({
    container: 'map',
    viewState: window.currentViewState,
    controller: { maxPitch: 90 },
    layers: [terrainLayer, airspaceLayer],
    onViewStateChange: ({viewState}) => {
        window.currentViewState = viewState;
        window.deckgl.setProps({viewState: window.currentViewState});
        updateUI();
    }
});

// --- UPDATE UI ---
function updateUI() {
    const pSlider = document.getElementById('pitch-slider');
    const aSlider = document.getElementById('alt-slider');
    const aVal = document.getElementById('alt-val');
    
    if (pSlider) pSlider.value = window.currentViewState.pitch;
    
    const currentAlt = zoomToAlt(window.currentViewState.zoom);
    if (aSlider) aSlider.value = currentAlt;
    if (aVal) aVal.innerHTML = currentAlt + " m";
}

// --- ACTIONS ---
window.moveCamera = function(latDiff, lonDiff) {
    window.currentViewState.latitude += latDiff;
    window.currentViewState.longitude += lonDiff;
    window.deckgl.setProps({ viewState: { ...window.currentViewState } });
};

window.updatePitch = function(val) {
    window.currentViewState.pitch = parseFloat(val);
    window.deckgl.setProps({ viewState: { ...window.currentViewState } });
};

window.updateAltitude = function(val) {
    const alt = parseFloat(val);
    window.currentViewState.zoom = altToZoom(alt);
    document.getElementById('alt-val').innerHTML = Math.round(alt) + " m";
    window.deckgl.setProps({ viewState: { ...window.currentViewState } });
};

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