// 1. CONFIGURATION DE LA CAMÉRA
let currentViewState = {
    latitude: 45.36, 
    longitude: 5.32, 
    zoom: 8, 
    pitch: 75, 
    bearing: 90
};

// 2. COUCHES 3D
const terrainLayer = new deck.TerrainLayer({
    id: 'terrain',
    elevationDecoder: {rScaler: 256, gScaler: 1, bScaler: 1 / 256, offset: -32768},
    elevationData: 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png',
    texture: 'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
    elevationMultiplier: 1.2
});

// "airspaceData" est injectée automatiquement par le chargement de data.js dans index.html
const airspaceLayer = new deck.GeoJsonLayer({
    id: 'airspace',
    data: airspaceData, 
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

// 3. INITIALISATION DU MOTEUR
const deckgl = new deck.Deck({
    container: 'map',
    viewState: currentViewState, 
    controller: { maxPitch: 90 }, // Permet de regarder l'horizon
    layers: [terrainLayer, airspaceLayer],
    onViewStateChange: ({viewState}) => {
        // Synchronisation des sliders si on navigue à la souris
        currentViewState = viewState;
        deckgl.setProps({viewState: currentViewState}); 
        
        const pitchSlider = document.getElementById('pitch-slider');
        const zoomSlider = document.getElementById('zoom-slider');
        if (pitchSlider) pitchSlider.value = currentViewState.pitch;
        if (zoomSlider) zoomSlider.value = currentViewState.zoom;
    }
});

// 4. FONCTIONS DE CONTRÔLE (Boutons et Sliders)
function applyViewState() { 
    // On clone l'objet pour forcer la carte à se mettre à jour
    currentViewState = Object.assign({}, currentViewState);
    deckgl.setProps({viewState: currentViewState}); 
}

function moveCamera(latDiff, lonDiff) { 
    currentViewState.latitude += latDiff; 
    currentViewState.longitude += lonDiff; 
    applyViewState(); 
}

function updatePitch(val) { currentViewState.pitch = parseFloat(val); applyViewState(); }
function updateZoom(val) { currentViewState.zoom = parseFloat(val); applyViewState(); }

// 5. INFOBULLE
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