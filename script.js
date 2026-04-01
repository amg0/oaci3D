// ==========================================
// ⚙️ CONFIGURATION ET ÉTAT INITIAL (LFLG)
// ==========================================
const DEFAULT_VIEW = {
    latitude: 45.2178,  // Le Versoud
    longitude: 5.8492,
    zoom: 10.5,         // ~5500 FT
    pitch: 75,
    bearing: 0          // Nord
};

window.currentViewState = { ...DEFAULT_VIEW };

// Constante de conversion Pieds <-> Zoom (Mercator)
const FT_CONSTANT = 65616797; 

function altToZoom(altFt) { 
    return Math.log2(FT_CONSTANT / Math.max(altFt, 500)); 
}
function zoomToAlt(zoom) { 
    return Math.round(FT_CONSTANT / Math.pow(2, zoom)); 
}

// ==========================================
// 🗺️ COUCHES ET MOTEUR DECK.GL
// ==========================================
const terrainLayer = new deck.TerrainLayer({
    id: 'terrain',
    elevationDecoder: {rScaler: 256, gScaler: 1, bScaler: 1 / 256, offset: -32768},
    elevationData: 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png',
    texture: 'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
    elevationMultiplier: 1.2
});

let allAirspaces = [];

window.deckgl = new deck.Deck({
    container: 'map',
    viewState: window.currentViewState,
    controller: { maxPitch: 90 },
    layers: [terrainLayer],
    onViewStateChange: ({viewState}) => {
        // Limite FL400
        const minZoom = altToZoom(40000);
        if (viewState.zoom < minZoom) viewState.zoom = minZoom;
        
        window.currentViewState = viewState;
        window.deckgl.setProps({viewState: window.currentViewState});
        updateUI();
    }
});

// ==========================================
// 🕹️ LOGIQUE DE NAVIGATION AVANCÉE
// ==========================================
window.moveCamera = function(direction) {
    const step = 0.005;       // Précision des translations latérales
    const altStep = 150;      // Vitesse de l'ascenseur (FT)
    const rotStep = 2.5;      // Vitesse de rotation (Degrés)
    
    let newState = { ...window.currentViewState };
    
    const bearingRad = (newState.bearing * Math.PI) / 180;
    const pitchRad = (newState.pitch * Math.PI) / 180;

    // Fonction de compensation "Ascenseur" (Annule le recul optique du zoom)
    const getElevatorComp = (deltaAlt) => {
        return Math.abs(deltaAlt * 0.3048) * Math.tan(pitchRad) * 0.000009;
    };

    switch(direction) {
        // --- TRANSLATIONS RELATIVES ---
        case 'UP':
            newState.latitude += step * Math.cos(bearingRad);
            newState.longitude += step * Math.sin(bearingRad);
            break;
        case 'DOWN':
            newState.latitude -= step * Math.cos(bearingRad);
            newState.longitude -= step * Math.sin(bearingRad);
            break;
        case 'LEFT':
            newState.latitude += step * Math.cos(bearingRad - Math.PI/2);
            newState.longitude += step * Math.sin(bearingRad - Math.PI/2);
            break;
        case 'RIGHT':
            newState.latitude += step * Math.cos(bearingRad + Math.PI/2);
            newState.longitude += step * Math.sin(bearingRad + Math.PI/2);
            break;

        // --- ROTATIONS ---
        case 'ROTATE_LEFT':
            newState.bearing -= rotStep;
            break;
        case 'ROTATE_RIGHT':
            newState.bearing += rotStep;
            break;

        // --- MOUVEMENT VERTICAL PUR (ASCENSEUR) ---
        case 'CLIMB':
            let oldAltC = zoomToAlt(newState.zoom);
            let newAltC = Math.min(oldAltC + altStep, 40000);
            newState.zoom = altToZoom(newAltC);
            
            let compC = getElevatorComp(newAltC - oldAltC);
            // On AVANCE la cible pour contrer le recul optique de la montée
            newState.latitude += compC * Math.cos(bearingRad);
            newState.longitude += compC * Math.sin(bearingRad);
            break;
            
        case 'DESCENT':
            let oldAltD = zoomToAlt(newState.zoom);
            let newAltD = Math.max(oldAltD - altStep, 500);
            newState.zoom = altToZoom(newAltD);
            
            let compD = getElevatorComp(newAltD - oldAltD);
            // On RECULE la cible pour contrer l'avancée optique de la descente
            newState.latitude -= compD * Math.cos(bearingRad);
            newState.longitude -= compD * Math.sin(bearingRad);
            break;
    }

    window.currentViewState = newState;
    window.deckgl.setProps({ viewState: { ...window.currentViewState } });
    updateUI();
};

// --- GESTION AUTO-REPEAT ---
let moveInterval = null;
window.startMove = function(direction) {
    if (moveInterval) return;
    window.moveCamera(direction);
    moveInterval = setInterval(() => window.moveCamera(direction), 50);
};
window.stopMove = function() {
    clearInterval(moveInterval);
    moveInterval = null;
};

// ==========================================
// 🛠️ INTERFACE, FILTRES ET HUD
// ==========================================
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
    const label = document.getElementById('filter-val');
    if (label) label.innerHTML = limit >= 40000 ? "Toutes" : limit + " FT";
    
    // Filtrage dynamique des données
    const filteredData = {
        type: "FeatureCollection",
        features: allAirspaces.filter(f => f.properties.floor_ft <= limit)
    };

    const layer = new deck.GeoJsonLayer({
        id: 'airspace',
        data: filteredData,
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

    window.deckgl.setProps({ layers: [terrainLayer, layer] });
};

function updateUI() {
    const alt = zoomToAlt(window.currentViewState.zoom);
    const pSlider = document.getElementById('pitch-slider');
    const aSlider = document.getElementById('alt-slider');
    const aVal = document.getElementById('alt-val');
    
    if (pSlider) pSlider.value = window.currentViewState.pitch;
    if (aSlider) aSlider.value = alt;
    if (aVal) aVal.innerHTML = alt + " FT";
}

// ==========================================
// 📥 CHARGEMENT DES DONNÉES JSON (ANTI-CACHE)
// ==========================================
// On force le navigateur à télécharger la dernière version générée par Python
const noCacheUrl = 'data.json?v=' + new Date().getTime();

fetch(noCacheUrl)
    .then(res => res.json())
    .then(data => {
        allAirspaces = data.features;
        // On initialise le filtre avec la valeur actuelle du slider (ou 40000 par défaut)
        const slider = document.getElementById('filter-slider');
        window.updateFloorFilter(slider ? slider.value : 40000); 
    })
    .catch(err => console.error("Erreur de chargement du JSON:", err));

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