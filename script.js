// 1. ÉTAT INITIAL
let currentViewState = {
    latitude: 45.36,
    longitude: 5.32,
    zoom: 8,
    pitch: 75,
    bearing: 90
};

// 2. DÉFINITION DES COUCHES
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

// 3. INITIALISATION DU MOTEUR DECK.GL
const deckgl = new deck.Deck({
    container: 'map',
    viewState: currentViewState, // Mode contrôlé
    controller: { maxPitch: 90 },
    layers: [terrainLayer, airspaceLayer],
    onViewStateChange: ({viewState}) => {
        // Cette fonction gère les mouvements à la SOURIS
        currentViewState = viewState;
        deckgl.setProps({viewState: currentViewState});
        updateUI();
    }
});

// 4. SYNC MAP & UI
function syncMap() {
    // Force Deck.gl à voir un nouvel objet pour déclencher le rendu
    currentViewState = { ...currentViewState };
    deckgl.setProps({ viewState: currentViewState });
    updateUI();
}

function updateUI() {
    const pSlider = document.getElementById('pitch-slider');
    const zSlider = document.getElementById('zoom-slider');
    if (pSlider) pSlider.value = currentViewState.pitch;
    if (zSlider) zSlider.value = currentViewState.zoom;
}

// 5. FONCTIONS EXPOSÉES AUX BOUTONS HTML
window.moveCamera = function(latDiff, lonDiff) {
    currentViewState.latitude += latDiff;
    currentViewState.longitude += lonDiff;
    syncMap();
};

window.updatePitch = function(val) {
    currentViewState.pitch = parseFloat(val);
    syncMap();
};

window.updateZoom = function(val) {
    currentViewState.zoom = parseFloat(val);
    syncMap();
};

// 6. GESTION DE L'INFOBULLE
function updateTooltip(info) {
    const el = document.getElementById('tooltip');
    if (info.object) {
        const p = info.object.properties;
        el.innerHTML = `<strong>${p.name}</strong><br>Cl: ${p.class}<br>Alt: ${p.real_floor} / ${p.real_ceiling}`;
        el.style.display = 'block';
        el.style.left = (info.x + 15) + 'px';
        el.style.top = (info.y + 15) + 'px';
    } else {
        el.style.display = 'none';
    }
}