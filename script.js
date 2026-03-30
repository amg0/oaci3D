// --- CONFIGURATION ---
const DEFAULT_VIEW = {
    latitude: 45.36,
    longitude: 5.32,
    zoom: 10.2, // ~5500 FT
    pitch: 75,
    bearing: 90
};

window.currentViewState = { ...DEFAULT_VIEW };
const FT_CONSTANT = 65616797; 

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

const airspaceLayer = new deck.GeoJsonLayer({
    id: 'airspace',
    data: 'data.json',
    stroked: true, filled: true, extruded: true, wireframe: true,
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
        // Limite FL400 (zoom min)
        const minZoom = altToZoom(40000); 
        if (viewState.zoom < minZoom) viewState.zoom = minZoom;
        
        window.currentViewState = viewState;
        window.deckgl.setProps({viewState: window.currentViewState});
        updateUI();
    }
});

// --- AUTO-REPEAT LOGIC ---
let moveInterval = null;

window.startMove = function(latD, lonD) {
    if (moveInterval) return;
    // Execute une fois puis repete
    moveCamera(latD, lonD);
    moveInterval = setInterval(() => moveCamera(latD, lonD), 50); // 20 images par seconde
};

window.stopMove = function() {
    clearInterval(moveInterval);
    moveInterval = null;
};

// --- ACTIONS ---
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
    let altFt = parseFloat(val);
    window.currentViewState.zoom = altToZoom(altFt);
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