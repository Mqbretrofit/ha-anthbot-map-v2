import { TRANSLATION_COMPLEMENTS } from "./i18n-complements.js?v=138";

export const LANGUAGES = [
  ["auto", "Automatic / Automatikus"],
  ["en", "English"], ["hu", "Magyar"], ["de", "Deutsch"],
  ["fr", "Français"], ["es", "Español"], ["it", "Italiano"],
  ["pt", "Português"], ["nl", "Nederlands"], ["pl", "Polski"],
  ["cs", "Čeština"], ["sk", "Slovenčina"], ["ro", "Română"],
  ["da", "Dansk"], ["sv", "Svenska"], ["no", "Norsk"],
  ["fi", "Suomi"], ["zh-CN", "简体中文"], ["zh-TW", "繁體中文"],
  ["tr", "Türkçe"], ["th", "ไทย"], ["vi", "Tiếng Việt"],
  ["ko", "한국어"], ["km", "ខ្មែរ"],
];

const en = {
  language: "Language", automatic: "Automatic", waiting: "Waiting for map entity",
  status: "Status", control: "Control", settings: "Settings", robotSettings: "Robot settings",
  interfaceSettings: "Interface settings", diagnostics: "Diagnostics",
  map: "Map", expand: "Click for large view", close: "Close", zoomIn: "Zoom in", zoomOut: "Zoom out",
  zones: "Zones", zone: "Zone", forbidden: "No-go", position: "Position", heading: "Direction",
  start: "START", startLabel: "Start", startSub: "Mow entire area",
  stop: "STOP", stopLabel: "Stop", stopSub: "Stop all tasks",
  home: "HOME", homeLabel: "Dock", homeSub: "Return to dock", zoneStart: "Start zone mowing",
  outerEdgeLabel: "Outer edge", outerEdgeSub: "Mow the outer lawn boundary",
  dockEdgeLabel: "Dock surroundings", dockEdgeSub: "Mow around the charging dock",
  cloud: "Cloud connection", cloudSub: "Refresh data and commands",
  mqttOnline: "📡 MQTT: online", mqttOffline: "📡 MQTT: offline",
  customDirection: "Custom direction", rainDelay: "Delay after rain", volume: "Volume",
  mowCount: "Mowing passes", visualObstacle: "Visual obstacle detection",
  visualObstacleLevel: "Obstacle sensitivity", low: "Low", medium: "Medium", high: "High",
  rainDetection: "Rain detection", customCutDirection: "Custom mowing direction",
  showZones: "Show zones", showBoundary: "Show boundary", showNoGoZones: "Show no-go zones", showNoGoLabels: "Show no-go labels", mapOnly: "Map only",
  themeBackground: "Use Home Assistant theme", glassBackground: "Glass background", transparentBackground: "Transparent background", battery: "Battery",
  charging: "Charging", connection: "Connection", cutHeight: "Cutting height",
  mowedArea: "Mowed area", mowingTime: "Mowing time", totalArea: "Total area", error: "Error",
  bladeLife: "Cutting components life", lineLife: "Cutting line life", dockContact: "Dock contact life",
  lastUpdate: "Last update", firmware: "Firmware", gpsLatitude: "GPS latitude", gpsLongitude: "GPS longitude",
  calibration: "Calibration", mapFit: "Map alignment",
  robotFit: "Robot calibration", mowingPathFit: "Mowing path calibration", robotDirection: "Robot direction", boundaryFit: "Boundary alignment", yamlCopy: "Copy YAML",
  up: "Up", left: "Left", right: "Right", down: "Down", narrower: "Narrower",
  wider: "Wider", shorter: "Shorter", taller: "Taller", rotation: "Rotation", reset: "Reset",
  switchMissing: "Switch entity not found", operationFailed: "Operation failed",
  settingFailed: "Setting failed", status_on: "on", status_off: "off", status_standby: "standby",
  status_paused: "paused", status_charging: "charging", status_mowing: "mowing",
  status_returning_to_dock: "returning to dock", status_mapping: "mapping",
  status_positioning: "positioning", status_sleeping: "sleeping", status_unknown: "unknown",
  mowingHistoryEmpty: "No completed mowing sessions yet.",
  mowingHistoryTotalCount: "Total sessions", mowingHistoryTotalArea: "Total mowed area",
  mowingHistoryArea: "Mowed area", mowingHistoryProgress: "Mowing progress",
  mowingHistoryDuration: "Duration", mowingHistoryMode: "Mowing mode",
  mowingHistoryStartedBy: "Start reason", mowingHistoryRawFields: "Other fields",
  mowingHistoryUnknownTime: "Unknown time",
  mowingModeZones: "Zones", mowingModeGlobal: "Entire lawn",
  mowingModeEdge: "Outer edge", mowingModeDockEdge: "Dock surroundings",
  mowingSourceApp: "App", mowingSourceSchedule: "Schedule",
  mowingSourceButton: "Robot button", mowingSourceVoice: "Voice",
  close: "Close", mowingHistoryDetailLoading: "Loading…",
  mowingHistoryDetailUnavailable: "No visual data available for this session.",
};

const translations = {
  en,
  hu: {
    language: "Nyelv", automatic: "Automatikus", waiting: "Várakozás a térkép entitásra",
    status: "Állapot", control: "Vezérlés", settings: "Beállítások", robotSettings: "Robot beállítások",
    interfaceSettings: "Felület beállítások", diagnostics: "Diagnosztika",
    map: "Térkép", expand: "Kattints a nagy nézethez", close: "Bezárás", zoomIn: "Nagyítás", zoomOut: "Kicsinyítés",
    zones: "Zónák", forbidden: "Tiltott", position: "Pozíció", heading: "Irány",
    start: "INDÍTÁS", startLabel: "Indítás", startSub: "Teljes terület nyírása",
    stop: "LEÁLLÍTÁS", stopLabel: "Leállítás", stopSub: "Minden feladat leállítása",
    home: "TÖLTŐ", homeLabel: "Töltő", homeSub: "Vissza a töltőre", zoneStart: "Zónavágás indítása",
    outerEdgeLabel: "Külső szegély", outerEdgeSub: "A gyep külső határának körbevágása",
    dockEdgeLabel: "Töltő környéke", dockEdgeSub: "A töltőállomás körüli nyírás",
    cloud: "Felhőkapcsolat", cloudSub: "Adatok és parancsok frissítése",
    mqttOnline: "📡 MQTT: online", mqttOffline: "📡 MQTT: offline",
    customDirection: "Egyedi irány", rainDelay: "Eső utáni várakozás", volume: "Hangerő",
    mowCount: "Nyírások száma", visualObstacle: "Vizuális akadályérzékelés",
    visualObstacleLevel: "Akadályérzékelés szintje", low: "Alacsony", medium: "Közepes", high: "Magas",
    rainDetection: "Esőérzékelés", customCutDirection: "Egyedi vágási irány",
    showZones: "Zónák megjelenítése", showBoundary: "Határvonal megjelenítése", showNoGoZones: "Tiltott zónák megjelenítése", showNoGoLabels: "Tiltott zóna feliratok", mapOnly: "Csak térkép",
    themeBackground: "HA téma használata", glassBackground: "Üveg háttér", transparentBackground: "Átlátszó háttér", battery: "Akkumulátor",
    charging: "Töltés", connection: "Kapcsolat", cutHeight: "Vágási magasság", mowedArea: "Nyírt terület",
    mowingTime: "Nyírási idő", totalArea: "Összterület", error: "Hiba",
    bladeLife: "Vágókések élettartama", lineLife: "Damilszál élettartama", dockContact: "Töltőérintkező élettartama",
    lastUpdate: "Utolsó frissítés", calibration: "Kalibrálás", mapFit: "Térkép illesztése",
    robotFit: "Robot kalibráció", mowingPathFit: "Nyírási útvonal kalibráció", robotDirection: "Robot iránya", boundaryFit: "Határvonal illesztése", yamlCopy: "YAML másolása",
    up: "Fel", left: "Balra", right: "Jobbra", down: "Le", narrower: "Keskenyebb",
    wider: "Szélesebb", shorter: "Alacsonyabb", taller: "Magasabb", rotation: "Forgatás", reset: "Alaphelyzet",
    switchMissing: "Nem található kapcsoló entitás", operationFailed: "A művelet sikertelen",
    settingFailed: "A beállítás sikertelen", status_on: "be", status_off: "ki", status_standby: "készenlét",
    status_paused: "szünet", status_charging: "töltés", status_mowing: "nyírás",
    status_returning_to_dock: "vissza a töltőre", status_mapping: "térképezés",
    status_positioning: "pozicionálás", status_sleeping: "alvás", status_unknown: "ismeretlen",
    zone: "Zóna",
    mowingHistoryEmpty: "Még nincs befejezett nyírás.",
    mowingHistoryTotalCount: "Összes alkalom", mowingHistoryTotalArea: "Összesen lenyírt terület",
    mowingHistoryArea: "Lenyírt terület", mowingHistoryProgress: "Nyírási folyamat",
    mowingHistoryDuration: "Időtartam", mowingHistoryMode: "Nyírási mód",
    mowingHistoryStartedBy: "Indítás indoka", mowingHistoryRawFields: "Egyéb mezők",
    mowingHistoryUnknownTime: "Ismeretlen időpont",
    mowingModeZones: "Zónák", mowingModeGlobal: "Teljes terület",
    mowingModeEdge: "Külső szegély", mowingModeDockEdge: "Töltő környéke",
    mowingSourceApp: "Alkalmazás", mowingSourceSchedule: "Ütemezés",
    mowingSourceButton: "Robot gomb", mowingSourceVoice: "Hang",
    close: "Bezárás", mowingHistoryDetailLoading: "Betöltés…",
    mowingHistoryDetailUnavailable: "Ehhez a nyíráshoz nincs elérhető képi adat.",
  },
  de: { language:"Sprache", automatic:"Automatisch", status:"Status", control:"Steuerung", settings:"Einstellungen", diagnostics:"Diagnose", map:"Karte", zones:"Zonen", forbidden:"Sperrgebiet", position:"Position", heading:"Richtung", startLabel:"Start", startSub:"Gesamte Fläche mähen", stopLabel:"Stopp", stopSub:"Alle Aufgaben stoppen", homeLabel:"Ladestation", homeSub:"Zur Ladestation", zoneStart:"Zonenmähen starten", cloud:"Cloud-Verbindung", customDirection:"Benutzerdefinierte Richtung", rainDelay:"Wartezeit nach Regen", volume:"Lautstärke", rainDetection:"Regenerkennung", showZones:"Zonen anzeigen", showBoundary:"Grenze anzeigen", battery:"Akku", charging:"Laden", connection:"Verbindung", cutHeight:"Schnitthöhe", mowedArea:"Gemähte Fläche", mowingTime:"Mähzeit", totalArea:"Gesamtfläche", error:"Fehler", calibration:"Kalibrierung", yamlCopy:"YAML kopieren" , zone:"Zone", mowingHistoryEmpty:"Noch keine abgeschlossenen Mähvorgänge.", mowingHistoryTotalCount:"Anzahl der Mähvorgänge", mowingHistoryTotalArea:"Insgesamt gemähte Fläche", mowingHistoryArea:"Gemähte Fläche", mowingHistoryProgress:"Mähfortschritt", mowingHistoryDuration:"Dauer", mowingHistoryMode:"Mähmodus", mowingHistoryStartedBy:"Startgrund", mowingHistoryRawFields:"Weitere Felder", mowingHistoryUnknownTime:"Unbekannter Zeitpunkt", mowingModeZones:"Zonen", mowingModeGlobal:"Gesamte Fläche", mowingModeEdge:"Außenkante", mowingModeDockEdge:"Bereich um die Ladestation", mowingSourceApp:"App", mowingSourceSchedule:"Zeitplan", mowingSourceButton:"Roboter-Taste", mowingSourceVoice:"Sprache", mowingHistoryDetailLoading:"Laden…", mowingHistoryDetailUnavailable:"Für diese Sitzung sind keine Bilddaten verfügbar." },
  fr: { language:"Langue", automatic:"Automatique", status:"État", control:"Commande", settings:"Réglages", diagnostics:"Diagnostic", map:"Carte", zones:"Zones", forbidden:"Zone interdite", position:"Position", heading:"Direction", startLabel:"Démarrer", startSub:"Tondre toute la zone", stopLabel:"Arrêter", stopSub:"Arrêter toutes les tâches", homeLabel:"Station", homeSub:"Retour à la station", zoneStart:"Démarrer la tonte de zone", cloud:"Connexion cloud", customDirection:"Direction personnalisée", rainDelay:"Délai après pluie", volume:"Volume", rainDetection:"Détection de pluie", showZones:"Afficher les zones", showBoundary:"Afficher la limite", battery:"Batterie", charging:"Charge", connection:"Connexion", cutHeight:"Hauteur de coupe", mowedArea:"Surface tondue", mowingTime:"Temps de tonte", totalArea:"Surface totale", error:"Erreur", calibration:"Étalonnage", yamlCopy:"Copier le YAML" , zone:"Zone", mowingHistoryEmpty:"Aucune tonte terminée pour l'instant.", mowingHistoryTotalCount:"Nombre de tontes", mowingHistoryTotalArea:"Surface totale tondue", mowingHistoryArea:"Surface tondue", mowingHistoryProgress:"Progression de la tonte", mowingHistoryDuration:"Durée", mowingHistoryMode:"Mode de tonte", mowingHistoryStartedBy:"Motif de démarrage", mowingHistoryRawFields:"Autres champs", mowingHistoryUnknownTime:"Heure inconnue", mowingModeZones:"Zones", mowingModeGlobal:"Toute la zone", mowingModeEdge:"Bordure extérieure", mowingModeDockEdge:"Autour de la station", mowingSourceApp:"Application", mowingSourceSchedule:"Programmation", mowingSourceButton:"Bouton du robot", mowingSourceVoice:"Voix", mowingHistoryDetailLoading:"Chargement…", mowingHistoryDetailUnavailable:"Aucune donnée visuelle disponible pour cette session." },
  es: { language:"Idioma", automatic:"Automático", status:"Estado", control:"Control", settings:"Ajustes", diagnostics:"Diagnóstico", map:"Mapa", zones:"Zonas", forbidden:"Zona prohibida", position:"Posición", heading:"Dirección", startLabel:"Iniciar", startSub:"Cortar toda el área", stopLabel:"Detener", stopSub:"Detener todas las tareas", homeLabel:"Base", homeSub:"Volver a la base", zoneStart:"Iniciar corte de zona", cloud:"Conexión a la nube", customDirection:"Dirección personalizada", rainDelay:"Espera tras lluvia", volume:"Volumen", rainDetection:"Detección de lluvia", showZones:"Mostrar zonas", showBoundary:"Mostrar límite", battery:"Batería", charging:"Cargando", connection:"Conexión", cutHeight:"Altura de corte", mowedArea:"Área cortada", mowingTime:"Tiempo de corte", totalArea:"Área total", error:"Error", calibration:"Calibración", yamlCopy:"Copiar YAML" , zone:"Zona", mowingHistoryEmpty:"Aún no hay cortes completados.", mowingHistoryTotalCount:"Total de cortes", mowingHistoryTotalArea:"Área total cortada", mowingHistoryArea:"Área cortada", mowingHistoryProgress:"Progreso del corte", mowingHistoryDuration:"Duración", mowingHistoryMode:"Modo de corte", mowingHistoryStartedBy:"Motivo de inicio", mowingHistoryRawFields:"Otros campos", mowingHistoryUnknownTime:"Hora desconocida", mowingModeZones:"Zonas", mowingModeGlobal:"Área completa", mowingModeEdge:"Borde exterior", mowingModeDockEdge:"Alrededores de la base", mowingSourceApp:"Aplicación", mowingSourceSchedule:"Programación", mowingSourceButton:"Botón del robot", mowingSourceVoice:"Voz", mowingHistoryDetailLoading:"Cargando…", mowingHistoryDetailUnavailable:"No hay datos visuales disponibles para esta sesión." },
  it: { language:"Lingua", automatic:"Automatico", status:"Stato", control:"Controllo", settings:"Impostazioni", diagnostics:"Diagnostica", map:"Mappa", zones:"Zone", forbidden:"Zona vietata", position:"Posizione", heading:"Direzione", startLabel:"Avvia", startSub:"Taglia tutta l'area", stopLabel:"Stop", stopSub:"Ferma tutte le attività", homeLabel:"Base", homeSub:"Ritorna alla base", zoneStart:"Avvia taglio zona", cloud:"Connessione cloud", customDirection:"Direzione personalizzata", rainDelay:"Attesa dopo pioggia", volume:"Volume", rainDetection:"Rilevamento pioggia", showZones:"Mostra zone", showBoundary:"Mostra confine", battery:"Batteria", charging:"Ricarica", connection:"Connessione", cutHeight:"Altezza di taglio", mowedArea:"Area tagliata", mowingTime:"Tempo di taglio", totalArea:"Area totale", error:"Errore", calibration:"Calibrazione", yamlCopy:"Copia YAML" , zone:"Zona", mowingHistoryEmpty:"Nessun taglio completato finora.", mowingHistoryTotalCount:"Numero di tagli", mowingHistoryTotalArea:"Area totale tagliata", mowingHistoryArea:"Area tagliata", mowingHistoryProgress:"Avanzamento del taglio", mowingHistoryDuration:"Durata", mowingHistoryMode:"Modalità di taglio", mowingHistoryStartedBy:"Motivo di avvio", mowingHistoryRawFields:"Altri campi", mowingHistoryUnknownTime:"Ora sconosciuta", mowingModeZones:"Zone", mowingModeGlobal:"Area completa", mowingModeEdge:"Bordo esterno", mowingModeDockEdge:"Intorno alla base", mowingSourceApp:"App", mowingSourceSchedule:"Pianificazione", mowingSourceButton:"Pulsante del robot", mowingSourceVoice:"Voce", mowingHistoryDetailLoading:"Caricamento…", mowingHistoryDetailUnavailable:"Nessun dato visivo disponibile per questa sessione." },
  pt: { language:"Idioma", automatic:"Automático", status:"Estado", control:"Controlo", settings:"Definições", diagnostics:"Diagnóstico", map:"Mapa", zones:"Zonas", forbidden:"Zona proibida", position:"Posição", heading:"Direção", startLabel:"Iniciar", startSub:"Cortar toda a área", stopLabel:"Parar", stopSub:"Parar todas as tarefas", homeLabel:"Base", homeSub:"Voltar à base", zoneStart:"Iniciar corte da zona", cloud:"Ligação à nuvem", customDirection:"Direção personalizada", rainDelay:"Espera após chuva", volume:"Volume", rainDetection:"Deteção de chuva", showZones:"Mostrar zonas", showBoundary:"Mostrar limite", battery:"Bateria", charging:"A carregar", connection:"Ligação", cutHeight:"Altura de corte", mowedArea:"Área cortada", mowingTime:"Tempo de corte", totalArea:"Área total", error:"Erro", calibration:"Calibração", yamlCopy:"Copiar YAML" , zone:"Zona", mowingHistoryEmpty:"Ainda não há cortes concluídos.", mowingHistoryTotalCount:"Total de cortes", mowingHistoryTotalArea:"Área total cortada", mowingHistoryArea:"Área cortada", mowingHistoryProgress:"Progresso do corte", mowingHistoryDuration:"Duração", mowingHistoryMode:"Modo de corte", mowingHistoryStartedBy:"Motivo de início", mowingHistoryRawFields:"Outros campos", mowingHistoryUnknownTime:"Hora desconhecida", mowingModeZones:"Zonas", mowingModeGlobal:"Área completa", mowingModeEdge:"Borda exterior", mowingModeDockEdge:"Arredores da base", mowingSourceApp:"Aplicação", mowingSourceSchedule:"Agendamento", mowingSourceButton:"Botão do robô", mowingSourceVoice:"Voz", mowingHistoryDetailLoading:"A carregar…", mowingHistoryDetailUnavailable:"Não há dados visuais disponíveis para esta sessão." },
  nl: { language:"Taal", automatic:"Automatisch", status:"Status", control:"Bediening", settings:"Instellingen", diagnostics:"Diagnose", map:"Kaart", zones:"Zones", forbidden:"Verboden zone", position:"Positie", heading:"Richting", startLabel:"Start", startSub:"Hele gebied maaien", stopLabel:"Stop", stopSub:"Alle taken stoppen", homeLabel:"Laadstation", homeSub:"Terug naar laadstation", zoneStart:"Zonemaaien starten", cloud:"Cloudverbinding", customDirection:"Aangepaste richting", rainDelay:"Wachttijd na regen", volume:"Volume", rainDetection:"Regendetectie", showZones:"Zones tonen", showBoundary:"Grens tonen", battery:"Accu", charging:"Laden", connection:"Verbinding", cutHeight:"Maaihoogte", mowedArea:"Gemaaid gebied", mowingTime:"Maaiduur", totalArea:"Totale oppervlakte", error:"Fout", calibration:"Kalibratie", yamlCopy:"YAML kopiëren" , zone:"Zone", mowingHistoryEmpty:"Nog geen voltooide maaibeurten.", mowingHistoryTotalCount:"Aantal maaibeurten", mowingHistoryTotalArea:"Totaal gemaaid gebied", mowingHistoryArea:"Gemaaid gebied", mowingHistoryProgress:"Maaivoortgang", mowingHistoryDuration:"Duur", mowingHistoryMode:"Maaimodus", mowingHistoryStartedBy:"Startreden", mowingHistoryRawFields:"Overige velden", mowingHistoryUnknownTime:"Onbekend tijdstip", mowingModeZones:"Zones", mowingModeGlobal:"Hele gebied", mowingModeEdge:"Buitenrand", mowingModeDockEdge:"Rond het laadstation", mowingSourceApp:"App", mowingSourceSchedule:"Schema", mowingSourceButton:"Robotknop", mowingSourceVoice:"Stem", mowingHistoryDetailLoading:"Laden…", mowingHistoryDetailUnavailable:"Geen visuele gegevens beschikbaar voor deze sessie." },
  pl: {
    language: "Język", automatic: "Automatycznie", waiting: "Oczekiwanie na encję mapy",
    status: "Stan", control: "Sterowanie", settings: "Ustawienia",
    robotSettings: "Ustawienia robota", interfaceSettings: "Ustawienia interfejsu",
    diagnostics: "Diagnostyka", map: "Mapa", expand: "Kliknij, aby powiększyć",
    close: "Zamknij", zoomIn: "Powiększ", zoomOut: "Pomniejsz",
    zones: "Strefy", forbidden: "Strefa zakazana", position: "Pozycja", heading: "Kierunek",
    start: "START", startLabel: "Start", startSub: "Koś cały obszar",
    stop: "STOP", stopLabel: "Stop", stopSub: "Zatrzymaj wszystkie zadania",
    home: "BAZA", homeLabel: "Stacja", homeSub: "Powrót do stacji",
    zoneStart: "Rozpocznij koszenie strefy",
    outerEdgeLabel: "Zewnętrzna krawędź", outerEdgeSub: "Koszenie zewnętrznej granicy trawnika",
    dockEdgeLabel: "Otoczenie stacji", dockEdgeSub: "Koszenie wokół stacji ładującej",
    cloud: "Połączenie z chmurą", cloudSub: "Odśwież dane i polecenia",
    customDirection: "Własny kierunek", rainDelay: "Opóźnienie po deszczu", volume: "Głośność",
    rainDetection: "Wykrywanie deszczu", customCutDirection: "Własny kierunek koszenia",
    showZones: "Pokaż strefy", showBoundary: "Pokaż granicę",
    showNoGoZones: "Pokaż strefy zakazane", showNoGoLabels: "Pokaż etykiety stref zakazanych",
    mapOnly: "Tylko mapa", themeBackground: "Użyj motywu Home Assistant",
    glassBackground: "Szklane tło", transparentBackground: "Przezroczyste tło",
    battery: "Bateria", charging: "Ładowanie", connection: "Połączenie",
    cutHeight: "Wysokość koszenia", mowedArea: "Skoszony obszar",
    mowingTime: "Czas koszenia", totalArea: "Całkowity obszar", error: "Błąd",
    bladeLife: "Zużycie elementów tnących", lineLife: "Zużycie żyłki tnącej",
    dockContact: "Zużycie styków stacji", lastUpdate: "Ostatnia aktualizacja",
    calibration: "Kalibracja", mapFit: "Dopasowanie mapy", robotFit: "Kalibracja robota", mowingPathFit: "Kalibracja ścieżki koszenia",
    robotDirection: "Kierunek robota", boundaryFit: "Dopasowanie granicy",
    yamlCopy: "Kopiuj YAML", up: "Góra", left: "Lewo", right: "Prawo", down: "Dół",
    narrower: "Węziej", wider: "Szerzej", shorter: "Niżej", taller: "Wyżej",
    rotation: "Obrót", reset: "Resetuj",
    switchMissing: "Nie znaleziono encji przełącznika",
    operationFailed: "Operacja nie powiodła się", settingFailed: "Nie udało się zmienić ustawienia",
    status_on: "włączony", status_off: "wyłączony", status_standby: "oczekiwanie",
    status_paused: "wstrzymany", status_charging: "ładowanie", status_mowing: "koszenie",
    status_returning_to_dock: "powrót do stacji", status_mapping: "mapowanie",
    status_positioning: "pozycjonowanie", status_sleeping: "uśpiony", status_unknown: "nieznany",
    zone: "Strefa",
    mowingHistoryEmpty: "Brak jeszcze zakończonych koszeń.",
    mowingHistoryTotalCount: "Liczba koszeń",
    mowingHistoryTotalArea: "Łączny skoszony obszar",
    mowingHistoryArea: "Skoszony obszar",
    mowingHistoryProgress: "Postęp koszenia",
    mowingHistoryDuration: "Czas trwania",
    mowingHistoryMode: "Tryb koszenia",
    mowingHistoryStartedBy: "Powód rozpoczęcia",
    mowingHistoryRawFields: "Pozostałe pola",
    mowingHistoryUnknownTime: "Nieznana godzina",
    mowingModeZones: "Strefy",
    mowingModeGlobal: "Cały obszar",
    mowingModeEdge: "Zewnętrzna krawędź",
    mowingModeDockEdge: "Otoczenie stacji",
    mowingSourceApp: "Aplikacja",
    mowingSourceSchedule: "Harmonogram",
    mowingSourceButton: "Przycisk robota",
    mowingSourceVoice: "Głos",
    mowingHistoryDetailLoading: "Ładowanie…",
    mowingHistoryDetailUnavailable: "Brak dostępnych danych wizualnych dla tej sesji.",
  },
  cs: { language:"Jazyk", automatic:"Automaticky", status:"Stav", control:"Ovládání", settings:"Nastavení", diagnostics:"Diagnostika", map:"Mapa", zones:"Zóny", forbidden:"Zakázaná zóna", position:"Poloha", heading:"Směr", startLabel:"Spustit", stopLabel:"Zastavit", homeLabel:"Stanice", homeSub:"Návrat do stanice", zoneStart:"Spustit sečení zóny", cloud:"Cloudové připojení", customDirection:"Vlastní směr", rainDelay:"Čekání po dešti", volume:"Hlasitost", rainDetection:"Detekce deště", showZones:"Zobrazit zóny", showBoundary:"Zobrazit hranici", battery:"Baterie", charging:"Nabíjení", connection:"Připojení", cutHeight:"Výška sečení", mowedArea:"Posečená plocha", mowingTime:"Doba sečení", totalArea:"Celková plocha", error:"Chyba", calibration:"Kalibrace", yamlCopy:"Kopírovat YAML" , zone:"Zóna", mowingHistoryEmpty:"Zatím žádné dokončené sečení.", mowingHistoryTotalCount:"Počet sečení", mowingHistoryTotalArea:"Celková posečená plocha", mowingHistoryArea:"Posečená plocha", mowingHistoryProgress:"Průběh sečení", mowingHistoryDuration:"Doba trvání", mowingHistoryMode:"Režim sečení", mowingHistoryStartedBy:"Důvod spuštění", mowingHistoryRawFields:"Další pole", mowingHistoryUnknownTime:"Neznámý čas", mowingModeZones:"Zóny", mowingModeGlobal:"Celá plocha", mowingModeEdge:"Vnější okraj", mowingModeDockEdge:"Okolí stanice", mowingSourceApp:"Aplikace", mowingSourceSchedule:"Plán", mowingSourceButton:"Tlačítko robota", mowingSourceVoice:"Hlas", mowingHistoryDetailLoading:"Načítání…", mowingHistoryDetailUnavailable:"Pro tuto relaci nejsou k dispozici žádná vizuální data." },
  sk: { language:"Jazyk", automatic:"Automaticky", status:"Stav", control:"Ovládanie", settings:"Nastavenia", diagnostics:"Diagnostika", map:"Mapa", zones:"Zóny", forbidden:"Zakázaná zóna", position:"Poloha", heading:"Smer", startLabel:"Spustiť", stopLabel:"Zastaviť", homeLabel:"Stanica", homeSub:"Návrat do stanice", zoneStart:"Spustiť kosenie zóny", cloud:"Cloudové pripojenie", customDirection:"Vlastný smer", rainDelay:"Čakanie po daždi", volume:"Hlasitosť", rainDetection:"Detekcia dažďa", showZones:"Zobraziť zóny", showBoundary:"Zobraziť hranicu", battery:"Batéria", charging:"Nabíjanie", connection:"Pripojenie", cutHeight:"Výška kosenia", mowedArea:"Pokosená plocha", mowingTime:"Čas kosenia", totalArea:"Celková plocha", error:"Chyba", calibration:"Kalibrácia", yamlCopy:"Kopírovať YAML" , zone:"Zóna", mowingHistoryEmpty:"Zatiaľ žiadne dokončené kosenie.", mowingHistoryTotalCount:"Počet kosení", mowingHistoryTotalArea:"Celková pokosená plocha", mowingHistoryArea:"Pokosená plocha", mowingHistoryProgress:"Priebeh kosenia", mowingHistoryDuration:"Trvanie", mowingHistoryMode:"Režim kosenia", mowingHistoryStartedBy:"Dôvod spustenia", mowingHistoryRawFields:"Ďalšie polia", mowingHistoryUnknownTime:"Neznámy čas", mowingModeZones:"Zóny", mowingModeGlobal:"Celá plocha", mowingModeEdge:"Vonkajší okraj", mowingModeDockEdge:"Okolie stanice", mowingSourceApp:"Aplikácia", mowingSourceSchedule:"Plán", mowingSourceButton:"Tlačidlo robota", mowingSourceVoice:"Hlas", mowingHistoryDetailLoading:"Načítava sa…", mowingHistoryDetailUnavailable:"Pre túto reláciu nie sú k dispozícii žiadne vizuálne údaje." },
  ro: { language:"Limbă", automatic:"Automat", status:"Stare", control:"Control", settings:"Setări", diagnostics:"Diagnostic", map:"Hartă", zones:"Zone", forbidden:"Zonă interzisă", position:"Poziție", heading:"Direcție", startLabel:"Pornire", stopLabel:"Oprire", homeLabel:"Stație", homeSub:"Înapoi la stație", zoneStart:"Pornește tunderea zonei", cloud:"Conexiune cloud", customDirection:"Direcție personalizată", rainDelay:"Așteptare după ploaie", volume:"Volum", rainDetection:"Detectare ploaie", showZones:"Afișează zonele", showBoundary:"Afișează limita", battery:"Baterie", charging:"Încărcare", connection:"Conexiune", cutHeight:"Înălțime de tăiere", mowedArea:"Suprafață tunsă", mowingTime:"Timp de tundere", totalArea:"Suprafață totală", error:"Eroare", calibration:"Calibrare", yamlCopy:"Copiază YAML" , zone:"Zonă", mowingHistoryEmpty:"Încă nu există tunderi finalizate.", mowingHistoryTotalCount:"Număr de tunderi", mowingHistoryTotalArea:"Suprafață totală tunsă", mowingHistoryArea:"Suprafață tunsă", mowingHistoryProgress:"Progresul tunderii", mowingHistoryDuration:"Durată", mowingHistoryMode:"Mod de tundere", mowingHistoryStartedBy:"Motivul pornirii", mowingHistoryRawFields:"Alte câmpuri", mowingHistoryUnknownTime:"Oră necunoscută", mowingModeZones:"Zone", mowingModeGlobal:"Întreaga suprafață", mowingModeEdge:"Margine exterioară", mowingModeDockEdge:"Zona din jurul stației", mowingSourceApp:"Aplicație", mowingSourceSchedule:"Programare", mowingSourceButton:"Buton robot", mowingSourceVoice:"Voce", mowingHistoryDetailLoading:"Se încarcă…", mowingHistoryDetailUnavailable:"Nu există date vizuale disponibile pentru această sesiune." },
  da: { language:"Sprog", automatic:"Automatisk", status:"Status", control:"Styring", settings:"Indstillinger", diagnostics:"Diagnostik", map:"Kort", zones:"Zoner", forbidden:"Forbudszone", position:"Position", heading:"Retning", startLabel:"Start", stopLabel:"Stop", homeLabel:"Ladestation", homeSub:"Tilbage til ladestation", zoneStart:"Start zoneklipning", cloud:"Cloudforbindelse", customDirection:"Tilpasset retning", rainDelay:"Ventetid efter regn", volume:"Lydstyrke", rainDetection:"Regnregistrering", showZones:"Vis zoner", showBoundary:"Vis grænse", battery:"Batteri", charging:"Opladning", connection:"Forbindelse", cutHeight:"Klippehøjde", mowedArea:"Klippet område", mowingTime:"Klippetid", totalArea:"Samlet område", error:"Fejl", calibration:"Kalibrering", yamlCopy:"Kopiér YAML" , zone:"Zone", mowingHistoryEmpty:"Endnu ingen fuldførte klipninger.", mowingHistoryTotalCount:"Antal klipninger", mowingHistoryTotalArea:"Samlet klippet område", mowingHistoryArea:"Klippet område", mowingHistoryProgress:"Klippefremskridt", mowingHistoryDuration:"Varighed", mowingHistoryMode:"Klippetilstand", mowingHistoryStartedBy:"Startårsag", mowingHistoryRawFields:"Andre felter", mowingHistoryUnknownTime:"Ukendt tidspunkt", mowingModeZones:"Zoner", mowingModeGlobal:"Hele området", mowingModeEdge:"Yderkant", mowingModeDockEdge:"Omkring ladestationen", mowingSourceApp:"App", mowingSourceSchedule:"Tidsplan", mowingSourceButton:"Robotknap", mowingSourceVoice:"Stemme", mowingHistoryDetailLoading:"Indlæser…", mowingHistoryDetailUnavailable:"Ingen visuelle data tilgængelige for denne session." },
  sv: { language:"Språk", automatic:"Automatiskt", status:"Status", control:"Styrning", settings:"Inställningar", diagnostics:"Diagnostik", map:"Karta", zones:"Zoner", forbidden:"Förbjuden zon", position:"Position", heading:"Riktning", startLabel:"Start", stopLabel:"Stopp", homeLabel:"Laddstation", homeSub:"Tillbaka till laddstation", zoneStart:"Starta zonklippning", cloud:"Molnanslutning", customDirection:"Anpassad riktning", rainDelay:"Väntetid efter regn", volume:"Volym", rainDetection:"Regndetektering", showZones:"Visa zoner", showBoundary:"Visa gräns", battery:"Batteri", charging:"Laddning", connection:"Anslutning", cutHeight:"Klipphöjd", mowedArea:"Klippt område", mowingTime:"Klipptid", totalArea:"Total yta", error:"Fel", calibration:"Kalibrering", yamlCopy:"Kopiera YAML" , zone:"Zon", mowingHistoryEmpty:"Inga avslutade klippningar än.", mowingHistoryTotalCount:"Antal klippningar", mowingHistoryTotalArea:"Total klippt yta", mowingHistoryArea:"Klippt yta", mowingHistoryProgress:"Klippförlopp", mowingHistoryDuration:"Varaktighet", mowingHistoryMode:"Klippläge", mowingHistoryStartedBy:"Startorsak", mowingHistoryRawFields:"Övriga fält", mowingHistoryUnknownTime:"Okänd tidpunkt", mowingModeZones:"Zoner", mowingModeGlobal:"Hela ytan", mowingModeEdge:"Ytterkant", mowingModeDockEdge:"Runt laddstationen", mowingSourceApp:"App", mowingSourceSchedule:"Schema", mowingSourceButton:"Robotknapp", mowingSourceVoice:"Röst", mowingHistoryDetailLoading:"Läser in…", mowingHistoryDetailUnavailable:"Inga visuella data tillgängliga för denna session." },
  no: { language:"Språk", automatic:"Automatisk", status:"Status", control:"Styring", settings:"Innstillinger", diagnostics:"Diagnostikk", map:"Kart", zones:"Soner", forbidden:"Forbudssone", position:"Posisjon", heading:"Retning", startLabel:"Start", stopLabel:"Stopp", homeLabel:"Ladestasjon", homeSub:"Tilbake til ladestasjon", zoneStart:"Start soneklipping", cloud:"Skytilkobling", customDirection:"Tilpasset retning", rainDelay:"Ventetid etter regn", volume:"Volum", rainDetection:"Regndeteksjon", showZones:"Vis soner", showBoundary:"Vis grense", battery:"Batteri", charging:"Lading", connection:"Tilkobling", cutHeight:"Klippehøyde", mowedArea:"Klippet område", mowingTime:"Klippetid", totalArea:"Totalt område", error:"Feil", calibration:"Kalibrering", yamlCopy:"Kopier YAML" , zone:"Sone", mowingHistoryEmpty:"Ingen fullførte klipperunder ennå.", mowingHistoryTotalCount:"Antall klipperunder", mowingHistoryTotalArea:"Totalt klippet område", mowingHistoryArea:"Klippet område", mowingHistoryProgress:"Klippefremdrift", mowingHistoryDuration:"Varighet", mowingHistoryMode:"Klippemodus", mowingHistoryStartedBy:"Startårsak", mowingHistoryRawFields:"Andre felt", mowingHistoryUnknownTime:"Ukjent tidspunkt", mowingModeZones:"Soner", mowingModeGlobal:"Hele området", mowingModeEdge:"Ytterkant", mowingModeDockEdge:"Rundt ladestasjonen", mowingSourceApp:"App", mowingSourceSchedule:"Tidsplan", mowingSourceButton:"Robotknapp", mowingSourceVoice:"Stemme", mowingHistoryDetailLoading:"Laster…", mowingHistoryDetailUnavailable:"Ingen visuelle data tilgjengelig for denne økten." },
  fi: { language:"Kieli", automatic:"Automaattinen", status:"Tila", control:"Ohjaus", settings:"Asetukset", diagnostics:"Diagnostiikka", map:"Kartta", zones:"Alueet", forbidden:"Kielletty alue", position:"Sijainti", heading:"Suunta", startLabel:"Käynnistä", stopLabel:"Pysäytä", homeLabel:"Latausasema", homeSub:"Palaa latausasemalle", zoneStart:"Aloita alueen leikkuu", cloud:"Pilviyhteys", customDirection:"Mukautettu suunta", rainDelay:"Odotus sateen jälkeen", volume:"Äänenvoimakkuus", rainDetection:"Sateen tunnistus", showZones:"Näytä alueet", showBoundary:"Näytä raja", battery:"Akku", charging:"Lataus", connection:"Yhteys", cutHeight:"Leikkuukorkeus", mowedArea:"Leikattu alue", mowingTime:"Leikkuuaika", totalArea:"Kokonaisalue", error:"Virhe", calibration:"Kalibrointi", yamlCopy:"Kopioi YAML" , zone:"Alue", mowingHistoryEmpty:"Ei vielä suoritettuja leikkuita.", mowingHistoryTotalCount:"Leikkuukertojen määrä", mowingHistoryTotalArea:"Leikattu kokonaisala", mowingHistoryArea:"Leikattu alue", mowingHistoryProgress:"Leikkuun eteneminen", mowingHistoryDuration:"Kesto", mowingHistoryMode:"Leikkuutila", mowingHistoryStartedBy:"Aloitussyy", mowingHistoryRawFields:"Muut kentät", mowingHistoryUnknownTime:"Tuntematon ajankohta", mowingModeZones:"Alueet", mowingModeGlobal:"Koko alue", mowingModeEdge:"Ulkoreuna", mowingModeDockEdge:"Latausaseman ympäristö", mowingSourceApp:"Sovellus", mowingSourceSchedule:"Aikataulu", mowingSourceButton:"Robotin painike", mowingSourceVoice:"Ääni", mowingHistoryDetailLoading:"Ladataan…", mowingHistoryDetailUnavailable:"Tälle istunnolle ei ole saatavilla visuaalista dataa." },
  "zh-CN": { language:"语言", automatic:"自动", waiting:"等待地图实体", status:"状态", control:"控制", settings:"设置", diagnostics:"诊断", map:"地图", expand:"点击查看大图", close:"关闭", zoomIn:"放大", zoomOut:"缩小", zones:"区域", forbidden:"禁区", position:"位置", heading:"方向", startLabel:"开始", startSub:"修剪整个区域", stopLabel:"停止", stopSub:"停止所有任务", homeLabel:"充电座", homeSub:"返回充电座", zoneStart:"开始区域修剪", cloud:"云连接", cloudSub:"刷新数据和命令", customDirection:"自定义方向", rainDelay:"雨后等待", volume:"音量", rainDetection:"雨水检测", customCutDirection:"自定义修剪方向", showZones:"显示区域", showBoundary:"显示边界", battery:"电池", charging:"充电", connection:"连接", cutHeight:"割草高度", mowedArea:"已修剪面积", mowingTime:"修剪时间", totalArea:"总面积", error:"错误", bladeLife:"刀片寿命", lineLife:"割草线寿命", dockContact:"充电触点寿命", lastUpdate:"最后更新", calibration:"校准", mapFit:"地图校准", robotFit:"机器人校准", mowingPathFit:"修剪路径校准", boundaryFit:"边界校准", yamlCopy:"复制 YAML", up:"上", left:"左", right:"右", down:"下", narrower:"变窄", wider:"变宽", shorter:"变短", taller:"变高", rotation:"旋转", reset:"重置", status_on:"开", status_off:"关", status_standby:"待机", status_paused:"暂停", status_charging:"充电中", status_mowing:"修剪中", status_returning_to_dock:"返回充电座", status_mapping:"建图中", status_positioning:"定位中", status_sleeping:"休眠", status_unknown:"未知" , zone:"区域", mowingHistoryEmpty:"暂无已完成的修剪记录。", mowingHistoryTotalCount:"总次数", mowingHistoryTotalArea:"累计修剪面积", mowingHistoryArea:"修剪面积", mowingHistoryProgress:"修剪进度", mowingHistoryDuration:"时长", mowingHistoryMode:"修剪模式", mowingHistoryStartedBy:"启动原因", mowingHistoryRawFields:"其他字段", mowingHistoryUnknownTime:"未知时间", mowingModeZones:"区域", mowingModeGlobal:"整个区域", mowingModeEdge:"外边界", mowingModeDockEdge:"充电座周边", mowingSourceApp:"应用", mowingSourceSchedule:"计划", mowingSourceButton:"机器人按钮", mowingSourceVoice:"语音", mowingHistoryDetailLoading:"加载中…", mowingHistoryDetailUnavailable:"此次记录没有可用的可视化数据。" },
  "zh-TW": { language:"語言", automatic:"自動", waiting:"等待地圖實體", status:"狀態", control:"控制", settings:"設定", diagnostics:"診斷", map:"地圖", expand:"點擊查看大圖", close:"關閉", zoomIn:"放大", zoomOut:"縮小", zones:"區域", forbidden:"禁區", position:"位置", heading:"方向", startLabel:"開始", startSub:"修剪整個區域", stopLabel:"停止", stopSub:"停止所有任務", homeLabel:"充電座", homeSub:"返回充電座", zoneStart:"開始區域修剪", cloud:"雲端連線", cloudSub:"重新整理資料和命令", customDirection:"自訂方向", rainDelay:"雨後等待", volume:"音量", rainDetection:"雨水偵測", customCutDirection:"自訂修剪方向", showZones:"顯示區域", showBoundary:"顯示邊界", battery:"電池", charging:"充電", connection:"連線", cutHeight:"割草高度", mowedArea:"已修剪面積", mowingTime:"修剪時間", totalArea:"總面積", error:"錯誤", bladeLife:"刀片壽命", lineLife:"割草線壽命", dockContact:"充電接點壽命", lastUpdate:"最後更新", calibration:"校準", mapFit:"地圖校準", robotFit:"機器人校準", mowingPathFit:"修剪路徑校準", boundaryFit:"邊界校準", yamlCopy:"複製 YAML", up:"上", left:"左", right:"右", down:"下", narrower:"變窄", wider:"變寬", shorter:"變短", taller:"變高", rotation:"旋轉", reset:"重設", status_on:"開", status_off:"關", status_standby:"待機", status_paused:"暫停", status_charging:"充電中", status_mowing:"修剪中", status_returning_to_dock:"返回充電座", status_mapping:"建圖中", status_positioning:"定位中", status_sleeping:"休眠", status_unknown:"未知" , zone:"區域", mowingHistoryEmpty:"尚無已完成的修剪紀錄。", mowingHistoryTotalCount:"總次數", mowingHistoryTotalArea:"累計修剪面積", mowingHistoryArea:"修剪面積", mowingHistoryProgress:"修剪進度", mowingHistoryDuration:"時長", mowingHistoryMode:"修剪模式", mowingHistoryStartedBy:"啟動原因", mowingHistoryRawFields:"其他欄位", mowingHistoryUnknownTime:"未知時間", mowingModeZones:"區域", mowingModeGlobal:"整個區域", mowingModeEdge:"外邊界", mowingModeDockEdge:"充電座周邊", mowingSourceApp:"應用程式", mowingSourceSchedule:"排程", mowingSourceButton:"機器人按鈕", mowingSourceVoice:"語音", mowingHistoryDetailLoading:"載入中…", mowingHistoryDetailUnavailable:"此次記錄沒有可用的視覺化資料。" },
  tr: { language:"Dil", automatic:"Otomatik", waiting:"Harita varlığı bekleniyor", status:"Durum", control:"Kontrol", settings:"Ayarlar", diagnostics:"Tanılama", map:"Harita", expand:"Büyük görünüm için tıklayın", close:"Kapat", zoomIn:"Yakınlaştır", zoomOut:"Uzaklaştır", zones:"Bölgeler", forbidden:"Yasak bölge", position:"Konum", heading:"Yön", startLabel:"Başlat", startSub:"Tüm alanı biç", stopLabel:"Durdur", stopSub:"Tüm görevleri durdur", homeLabel:"İstasyon", homeSub:"İstasyona dön", zoneStart:"Bölge biçmeyi başlat", cloud:"Bulut bağlantısı", customDirection:"Özel yön", rainDelay:"Yağmur sonrası bekleme", volume:"Ses", rainDetection:"Yağmur algılama", showZones:"Bölgeleri göster", showBoundary:"Sınırı göster", battery:"Pil", charging:"Şarj", connection:"Bağlantı", cutHeight:"Kesim yüksekliği", mowedArea:"Biçilen alan", mowingTime:"Biçme süresi", totalArea:"Toplam alan", error:"Hata", calibration:"Kalibrasyon", yamlCopy:"YAML kopyala", status_standby:"beklemede", status_paused:"duraklatıldı", status_charging:"şarj oluyor", status_mowing:"biçiyor", status_returning_to_dock:"istasyona dönüyor", status_unknown:"bilinmiyor" , zone:"Bölge", mowingHistoryEmpty:"Henüz tamamlanmış biçme yok.", mowingHistoryTotalCount:"Toplam biçme sayısı", mowingHistoryTotalArea:"Toplam biçilen alan", mowingHistoryArea:"Biçilen alan", mowingHistoryProgress:"Biçme ilerlemesi", mowingHistoryDuration:"Süre", mowingHistoryMode:"Biçme modu", mowingHistoryStartedBy:"Başlatma nedeni", mowingHistoryRawFields:"Diğer alanlar", mowingHistoryUnknownTime:"Bilinmeyen zaman", mowingModeZones:"Bölgeler", mowingModeGlobal:"Tüm alan", mowingModeEdge:"Dış kenar", mowingModeDockEdge:"İstasyon çevresi", mowingSourceApp:"Uygulama", mowingSourceSchedule:"Zamanlama", mowingSourceButton:"Robot düğmesi", mowingSourceVoice:"Ses", mowingHistoryDetailLoading:"Yükleniyor…", mowingHistoryDetailUnavailable:"Bu oturum için görsel veri mevcut değil." },
  th: { language:"ภาษา", automatic:"อัตโนมัติ", waiting:"กำลังรอเอนทิตีแผนที่", status:"สถานะ", control:"ควบคุม", settings:"การตั้งค่า", diagnostics:"การวินิจฉัย", map:"แผนที่", close:"ปิด", zoomIn:"ซูมเข้า", zoomOut:"ซูมออก", zones:"โซน", forbidden:"เขตห้ามเข้า", position:"ตำแหน่ง", heading:"ทิศทาง", startLabel:"เริ่ม", startSub:"ตัดหญ้าทั้งพื้นที่", stopLabel:"หยุด", stopSub:"หยุดงานทั้งหมด", homeLabel:"แท่นชาร์จ", homeSub:"กลับแท่นชาร์จ", zoneStart:"เริ่มตัดหญ้าในโซน", cloud:"การเชื่อมต่อคลาวด์", customDirection:"ทิศทางกำหนดเอง", rainDelay:"หน่วงเวลาหลังฝน", volume:"ระดับเสียง", rainDetection:"ตรวจจับฝน", showZones:"แสดงโซน", showBoundary:"แสดงขอบเขต", battery:"แบตเตอรี่", charging:"กำลังชาร์จ", connection:"การเชื่อมต่อ", cutHeight:"ความสูงการตัด", mowedArea:"พื้นที่ตัดแล้ว", mowingTime:"เวลาตัดหญ้า", totalArea:"พื้นที่ทั้งหมด", error:"ข้อผิดพลาด", calibration:"การปรับเทียบ", yamlCopy:"คัดลอก YAML", status_standby:"พร้อมใช้งาน", status_paused:"หยุดชั่วคราว", status_mowing:"กำลังตัดหญ้า", status_unknown:"ไม่ทราบ" , zone:"โซน", mowingHistoryEmpty:"ยังไม่มีการตัดหญ้าที่เสร็จสมบูรณ์", mowingHistoryTotalCount:"จำนวนครั้งทั้งหมด", mowingHistoryTotalArea:"พื้นที่ตัดรวม", mowingHistoryArea:"พื้นที่ตัดแล้ว", mowingHistoryProgress:"ความคืบหน้าการตัดหญ้า", mowingHistoryDuration:"ระยะเวลา", mowingHistoryMode:"โหมดการตัดหญ้า", mowingHistoryStartedBy:"สาเหตุการเริ่ม", mowingHistoryRawFields:"ฟิลด์อื่น ๆ", mowingHistoryUnknownTime:"เวลาที่ไม่ทราบ", mowingModeZones:"โซน", mowingModeGlobal:"พื้นที่ทั้งหมด", mowingModeEdge:"ขอบด้านนอก", mowingModeDockEdge:"รอบแท่นชาร์จ", mowingSourceApp:"แอป", mowingSourceSchedule:"ตารางเวลา", mowingSourceButton:"ปุ่มบนหุ่นยนต์", mowingSourceVoice:"เสียง", mowingHistoryDetailLoading:"กำลังโหลด…", mowingHistoryDetailUnavailable:"ไม่มีข้อมูลภาพสำหรับเซสชันนี้" },
  vi: { language:"Ngôn ngữ", automatic:"Tự động", waiting:"Đang chờ thực thể bản đồ", status:"Trạng thái", control:"Điều khiển", settings:"Cài đặt", diagnostics:"Chẩn đoán", map:"Bản đồ", close:"Đóng", zoomIn:"Phóng to", zoomOut:"Thu nhỏ", zones:"Khu vực", forbidden:"Vùng cấm", position:"Vị trí", heading:"Hướng", startLabel:"Bắt đầu", startSub:"Cắt toàn bộ khu vực", stopLabel:"Dừng", stopSub:"Dừng mọi tác vụ", homeLabel:"Trạm sạc", homeSub:"Trở về trạm sạc", zoneStart:"Bắt đầu cắt theo khu vực", cloud:"Kết nối đám mây", customDirection:"Hướng tùy chỉnh", rainDelay:"Chờ sau mưa", volume:"Âm lượng", rainDetection:"Phát hiện mưa", showZones:"Hiện khu vực", showBoundary:"Hiện ranh giới", battery:"Pin", charging:"Đang sạc", connection:"Kết nối", cutHeight:"Chiều cao cắt", mowedArea:"Diện tích đã cắt", mowingTime:"Thời gian cắt", totalArea:"Tổng diện tích", error:"Lỗi", calibration:"Hiệu chỉnh", yamlCopy:"Sao chép YAML", status_standby:"chờ", status_paused:"tạm dừng", status_mowing:"đang cắt", status_returning_to_dock:"đang về trạm", status_unknown:"không xác định" , zone:"Khu vực", mowingHistoryEmpty:"Chưa có lần cắt nào hoàn thành.", mowingHistoryTotalCount:"Tổng số lần cắt", mowingHistoryTotalArea:"Tổng diện tích đã cắt", mowingHistoryArea:"Diện tích đã cắt", mowingHistoryProgress:"Tiến độ cắt", mowingHistoryDuration:"Thời lượng", mowingHistoryMode:"Chế độ cắt", mowingHistoryStartedBy:"Lý do bắt đầu", mowingHistoryRawFields:"Trường khác", mowingHistoryUnknownTime:"Thời gian không xác định", mowingModeZones:"Khu vực", mowingModeGlobal:"Toàn bộ khu vực", mowingModeEdge:"Viền ngoài", mowingModeDockEdge:"Xung quanh trạm sạc", mowingSourceApp:"Ứng dụng", mowingSourceSchedule:"Lịch trình", mowingSourceButton:"Nút trên robot", mowingSourceVoice:"Giọng nói", mowingHistoryDetailLoading:"Đang tải…", mowingHistoryDetailUnavailable:"Không có dữ liệu hình ảnh cho phiên này." },
  ko: { language:"언어", automatic:"자동", waiting:"지도 엔티티를 기다리는 중", status:"상태", control:"제어", settings:"설정", diagnostics:"진단", map:"지도", close:"닫기", zoomIn:"확대", zoomOut:"축소", zones:"구역", forbidden:"금지 구역", position:"위치", heading:"방향", startLabel:"시작", startSub:"전체 구역 잔디 깎기", stopLabel:"정지", stopSub:"모든 작업 정지", homeLabel:"충전소", homeSub:"충전소로 복귀", zoneStart:"구역 잔디 깎기 시작", cloud:"클라우드 연결", customDirection:"사용자 지정 방향", rainDelay:"비 온 뒤 대기", volume:"음량", rainDetection:"비 감지", showZones:"구역 표시", showBoundary:"경계 표시", battery:"배터리", charging:"충전 중", connection:"연결", cutHeight:"절단 높이", mowedArea:"깎은 면적", mowingTime:"작업 시간", totalArea:"전체 면적", error:"오류", calibration:"보정", yamlCopy:"YAML 복사", status_standby:"대기", status_paused:"일시 정지", status_mowing:"잔디 깎는 중", status_returning_to_dock:"충전소로 복귀 중", status_unknown:"알 수 없음" , zone:"구역", mowingHistoryEmpty:"아직 완료된 잔디 깎기가 없습니다.", mowingHistoryTotalCount:"총 작업 횟수", mowingHistoryTotalArea:"총 깎은 면적", mowingHistoryArea:"깎은 면적", mowingHistoryProgress:"작업 진행률", mowingHistoryDuration:"소요 시간", mowingHistoryMode:"잔디 깎기 모드", mowingHistoryStartedBy:"시작 이유", mowingHistoryRawFields:"기타 필드", mowingHistoryUnknownTime:"알 수 없는 시간", mowingModeZones:"구역", mowingModeGlobal:"전체 구역", mowingModeEdge:"외곽 가장자리", mowingModeDockEdge:"충전소 주변", mowingSourceApp:"앱", mowingSourceSchedule:"예약", mowingSourceButton:"로봇 버튼", mowingSourceVoice:"음성", mowingHistoryDetailLoading:"로딩 중…", mowingHistoryDetailUnavailable:"이 세션에 사용할 수 있는 시각 데이터가 없습니다." },
  km: { language:"ភាសា", automatic:"ស្វ័យប្រវត្តិ", waiting:"កំពុងរង់ចាំធាតុផែនទី", status:"ស្ថានភាព", control:"ការគ្រប់គ្រង", settings:"ការកំណត់", diagnostics:"ការវិនិច្ឆ័យ", map:"ផែនទី", close:"បិទ", zoomIn:"ពង្រីក", zoomOut:"បង្រួម", zones:"តំបន់", forbidden:"តំបន់ហាមឃាត់", position:"ទីតាំង", heading:"ទិសដៅ", startLabel:"ចាប់ផ្តើម", startSub:"កាត់ស្មៅពេញតំបន់", stopLabel:"បញ្ឈប់", stopSub:"បញ្ឈប់កិច្ចការទាំងអស់", homeLabel:"ស្ថានីយសាក", homeSub:"ត្រឡប់ទៅស្ថានីយសាក", zoneStart:"ចាប់ផ្តើមកាត់ស្មៅតាមតំបន់", cloud:"ការតភ្ជាប់ក្លោដ", customDirection:"ទិសដៅផ្ទាល់ខ្លួន", rainDelay:"រង់ចាំក្រោយភ្លៀង", volume:"កម្រិតសំឡេង", rainDetection:"ការរកឃើញភ្លៀង", showZones:"បង្ហាញតំបន់", showBoundary:"បង្ហាញព្រំដែន", battery:"ថ្ម", charging:"កំពុងសាក", connection:"ការតភ្ជាប់", cutHeight:"កម្ពស់កាត់", mowedArea:"ផ្ទៃដែលបានកាត់", mowingTime:"ពេលវេលាកាត់", totalArea:"ផ្ទៃសរុប", error:"កំហុស", calibration:"ការក្រិត", yamlCopy:"ចម្លង YAML", status_standby:"រង់ចាំ", status_paused:"បានផ្អាក", status_mowing:"កំពុងកាត់ស្មៅ", status_unknown:"មិនស្គាល់" , zone:"តំបន់", mowingHistoryEmpty:"មិនទាន់មានការកាត់ស្មៅដែលបានបញ្ចប់នៅឡើយទេ។", mowingHistoryTotalCount:"ចំនួនដងសរុប", mowingHistoryTotalArea:"ផ្ទៃដែលបានកាត់សរុប", mowingHistoryArea:"ផ្ទៃដែលបានកាត់", mowingHistoryProgress:"វឌ្ឍនភាពកាត់ស្មៅ", mowingHistoryDuration:"រយៈពេល", mowingHistoryMode:"របៀបកាត់ស្មៅ", mowingHistoryStartedBy:"មូលហេតុចាប់ផ្តើម", mowingHistoryRawFields:"វាល​ផ្សេងទៀត", mowingHistoryUnknownTime:"ពេលវេលាមិនស្គាល់", mowingModeZones:"តំបន់", mowingModeGlobal:"ផ្ទៃទាំងមូល", mowingModeEdge:"គែមខាងក្រៅ", mowingModeDockEdge:"ជុំវិញស្ថានីយសាក", mowingSourceApp:"កម្មវិធី", mowingSourceSchedule:"កាលវិភាគ", mowingSourceButton:"ប៊ូតុងរបស់រ៉ូបូត", mowingSourceVoice:"សំឡេង", mowingHistoryDetailLoading:"កំពុងផ្ទុក…", mowingHistoryDetailUnavailable:"មិនមានទិន្នន័យរូបភាពសម្រាប់វគ្គនេះទេ។" },
};

for (const [language, complement] of Object.entries(TRANSLATION_COMPLEMENTS)) {
  Object.assign(translations[language], complement);
}

const feedbackTranslations = {
  en: { cloudChecking:"☁ Cloud: checking…", cloudDisconnected:"☁ Cloud: disconnected", cloudRobotOnline:"☁ Cloud: active · Robot: online", cloudRobotNoResponse:"☁ Cloud: active · Robot: not responding", commandSentWaiting:"{command}: command sent, waiting for confirmation.", commandConfirmed:"{command}: confirmed by the robot.", commandNotConfirmed:"{command}: accepted by the cloud, but not confirmed by the robot.", commandFailed:"Operation failed: {command}" },
  hu: { cloudChecking:"☁ Felhő: ellenőrzés…", cloudDisconnected:"☁ Felhő: nincs kapcsolat", cloudRobotOnline:"☁ Felhő: aktív · Robot: online", cloudRobotNoResponse:"☁ Felhő: aktív · Robot: nem válaszol", commandSentWaiting:"{command}: parancs elküldve, visszaigazolásra vár.", commandConfirmed:"{command}: a robot visszaigazolta.", commandNotConfirmed:"{command}: a felhő elfogadta, de a robot nem igazolta vissza.", commandFailed:"A művelet sikertelen: {command}" },
  de: { cloudChecking:"☁ Cloud: wird geprüft…", cloudDisconnected:"☁ Cloud: keine Verbindung", cloudRobotOnline:"☁ Cloud: aktiv · Roboter: online", cloudRobotNoResponse:"☁ Cloud: aktiv · Roboter antwortet nicht", commandSentWaiting:"{command}: Befehl gesendet, Bestätigung wird erwartet.", commandConfirmed:"{command}: vom Roboter bestätigt.", commandNotConfirmed:"{command}: von der Cloud akzeptiert, aber nicht vom Roboter bestätigt.", commandFailed:"Vorgang fehlgeschlagen: {command}" },
  fr: { cloudChecking:"☁ Cloud : vérification…", cloudDisconnected:"☁ Cloud : déconnecté", cloudRobotOnline:"☁ Cloud : actif · Robot : en ligne", cloudRobotNoResponse:"☁ Cloud : actif · Robot sans réponse", commandSentWaiting:"{command} : commande envoyée, en attente de confirmation.", commandConfirmed:"{command} : confirmée par le robot.", commandNotConfirmed:"{command} : acceptée par le cloud, mais non confirmée par le robot.", commandFailed:"Échec de l’opération : {command}" },
  es: { cloudChecking:"☁ Nube: comprobando…", cloudDisconnected:"☁ Nube: sin conexión", cloudRobotOnline:"☁ Nube: activa · Robot: en línea", cloudRobotNoResponse:"☁ Nube: activa · Robot sin respuesta", commandSentWaiting:"{command}: comando enviado, esperando confirmación.", commandConfirmed:"{command}: confirmado por el robot.", commandNotConfirmed:"{command}: aceptado por la nube, pero no confirmado por el robot.", commandFailed:"Error en la operación: {command}" },
  it: { cloudChecking:"☁ Cloud: verifica…", cloudDisconnected:"☁ Cloud: disconnesso", cloudRobotOnline:"☁ Cloud: attivo · Robot: online", cloudRobotNoResponse:"☁ Cloud: attivo · Robot non risponde", commandSentWaiting:"{command}: comando inviato, in attesa di conferma.", commandConfirmed:"{command}: confermato dal robot.", commandNotConfirmed:"{command}: accettato dal cloud, ma non confermato dal robot.", commandFailed:"Operazione non riuscita: {command}" },
  pt: { cloudChecking:"☁ Nuvem: a verificar…", cloudDisconnected:"☁ Nuvem: sem ligação", cloudRobotOnline:"☁ Nuvem: ativa · Robô: online", cloudRobotNoResponse:"☁ Nuvem: ativa · Robô sem resposta", commandSentWaiting:"{command}: comando enviado, a aguardar confirmação.", commandConfirmed:"{command}: confirmado pelo robô.", commandNotConfirmed:"{command}: aceite pela nuvem, mas não confirmado pelo robô.", commandFailed:"Falha na operação: {command}" },
  nl: { cloudChecking:"☁ Cloud: controleren…", cloudDisconnected:"☁ Cloud: niet verbonden", cloudRobotOnline:"☁ Cloud: actief · Robot: online", cloudRobotNoResponse:"☁ Cloud: actief · Robot reageert niet", commandSentWaiting:"{command}: opdracht verzonden, wacht op bevestiging.", commandConfirmed:"{command}: bevestigd door de robot.", commandNotConfirmed:"{command}: geaccepteerd door de cloud, maar niet bevestigd door de robot.", commandFailed:"Bewerking mislukt: {command}" },
  pl: { cloudChecking:"☁ Chmura: sprawdzanie…", cloudDisconnected:"☁ Chmura: brak połączenia", cloudRobotOnline:"☁ Chmura: aktywna · Robot: online", cloudRobotNoResponse:"☁ Chmura: aktywna · Robot nie odpowiada", commandSentWaiting:"{command}: polecenie wysłane, oczekiwanie na potwierdzenie.", commandConfirmed:"{command}: potwierdzone przez robota.", commandNotConfirmed:"{command}: zaakceptowane przez chmurę, ale niepotwierdzone przez robota.", commandFailed:"Operacja nie powiodła się: {command}" },
  cs: { cloudChecking:"☁ Cloud: kontrola…", cloudDisconnected:"☁ Cloud: nepřipojeno", cloudRobotOnline:"☁ Cloud: aktivní · Robot: online", cloudRobotNoResponse:"☁ Cloud: aktivní · Robot neodpovídá", commandSentWaiting:"{command}: příkaz odeslán, čeká se na potvrzení.", commandConfirmed:"{command}: potvrzeno robotem.", commandNotConfirmed:"{command}: přijato cloudem, ale nepotvrzeno robotem.", commandFailed:"Operace se nezdařila: {command}" },
  sk: { cloudChecking:"☁ Cloud: kontrola…", cloudDisconnected:"☁ Cloud: nepripojené", cloudRobotOnline:"☁ Cloud: aktívny · Robot: online", cloudRobotNoResponse:"☁ Cloud: aktívny · Robot neodpovedá", commandSentWaiting:"{command}: príkaz odoslaný, čaká sa na potvrdenie.", commandConfirmed:"{command}: potvrdené robotom.", commandNotConfirmed:"{command}: prijaté cloudom, ale nepotvrdené robotom.", commandFailed:"Operácia zlyhala: {command}" },
  ro: { cloudChecking:"☁ Cloud: se verifică…", cloudDisconnected:"☁ Cloud: deconectat", cloudRobotOnline:"☁ Cloud: activ · Robot: online", cloudRobotNoResponse:"☁ Cloud: activ · Robotul nu răspunde", commandSentWaiting:"{command}: comandă trimisă, se așteaptă confirmarea.", commandConfirmed:"{command}: confirmată de robot.", commandNotConfirmed:"{command}: acceptată de cloud, dar neconfirmată de robot.", commandFailed:"Operațiunea a eșuat: {command}" },
  da: { cloudChecking:"☁ Cloud: kontrollerer…", cloudDisconnected:"☁ Cloud: ikke forbundet", cloudRobotOnline:"☁ Cloud: aktiv · Robot: online", cloudRobotNoResponse:"☁ Cloud: aktiv · Robot svarer ikke", commandSentWaiting:"{command}: kommando sendt, afventer bekræftelse.", commandConfirmed:"{command}: bekræftet af robotten.", commandNotConfirmed:"{command}: accepteret af cloud, men ikke bekræftet af robotten.", commandFailed:"Handlingen mislykkedes: {command}" },
  sv: { cloudChecking:"☁ Moln: kontrollerar…", cloudDisconnected:"☁ Moln: frånkopplat", cloudRobotOnline:"☁ Moln: aktivt · Robot: online", cloudRobotNoResponse:"☁ Moln: aktivt · Robot svarar inte", commandSentWaiting:"{command}: kommando skickat, väntar på bekräftelse.", commandConfirmed:"{command}: bekräftat av roboten.", commandNotConfirmed:"{command}: accepterat av molnet, men inte bekräftat av roboten.", commandFailed:"Åtgärden misslyckades: {command}" },
  no: { cloudChecking:"☁ Sky: kontrollerer…", cloudDisconnected:"☁ Sky: ikke tilkoblet", cloudRobotOnline:"☁ Sky: aktiv · Robot: online", cloudRobotNoResponse:"☁ Sky: aktiv · Robot svarer ikke", commandSentWaiting:"{command}: kommando sendt, venter på bekreftelse.", commandConfirmed:"{command}: bekreftet av roboten.", commandNotConfirmed:"{command}: godtatt av skyen, men ikke bekreftet av roboten.", commandFailed:"Handlingen mislyktes: {command}" },
  fi: { cloudChecking:"☁ Pilvi: tarkistetaan…", cloudDisconnected:"☁ Pilvi: ei yhteyttä", cloudRobotOnline:"☁ Pilvi: aktiivinen · Robotti: online", cloudRobotNoResponse:"☁ Pilvi: aktiivinen · Robotti ei vastaa", commandSentWaiting:"{command}: komento lähetetty, odotetaan vahvistusta.", commandConfirmed:"{command}: robotin vahvistama.", commandNotConfirmed:"{command}: pilvi hyväksyi, mutta robotti ei vahvistanut.", commandFailed:"Toiminto epäonnistui: {command}" },
  "zh-CN": { cloudChecking:"☁ 云端：正在检查…", cloudDisconnected:"☁ 云端：未连接", cloudRobotOnline:"☁ 云端：已连接 · 机器人：在线", cloudRobotNoResponse:"☁ 云端：已连接 · 机器人无响应", commandSentWaiting:"{command}：命令已发送，等待确认。", commandConfirmed:"{command}：机器人已确认。", commandNotConfirmed:"{command}：云端已接受，但机器人未确认。", commandFailed:"操作失败：{command}" },
  "zh-TW": { cloudChecking:"☁ 雲端：正在檢查…", cloudDisconnected:"☁ 雲端：未連線", cloudRobotOnline:"☁ 雲端：已連線 · 機器人：在線", cloudRobotNoResponse:"☁ 雲端：已連線 · 機器人無回應", commandSentWaiting:"{command}：指令已傳送，等待確認。", commandConfirmed:"{command}：機器人已確認。", commandNotConfirmed:"{command}：雲端已接受，但機器人未確認。", commandFailed:"操作失敗：{command}" },
  tr: { cloudChecking:"☁ Bulut: kontrol ediliyor…", cloudDisconnected:"☁ Bulut: bağlantı yok", cloudRobotOnline:"☁ Bulut: etkin · Robot: çevrimiçi", cloudRobotNoResponse:"☁ Bulut: etkin · Robot yanıt vermiyor", commandSentWaiting:"{command}: komut gönderildi, onay bekleniyor.", commandConfirmed:"{command}: robot tarafından onaylandı.", commandNotConfirmed:"{command}: bulut tarafından kabul edildi, ancak robot onaylamadı.", commandFailed:"İşlem başarısız: {command}" },
  th: { cloudChecking:"☁ คลาวด์: กำลังตรวจสอบ…", cloudDisconnected:"☁ คลาวด์: ไม่ได้เชื่อมต่อ", cloudRobotOnline:"☁ คลาวด์: ทำงาน · หุ่นยนต์: ออนไลน์", cloudRobotNoResponse:"☁ คลาวด์: ทำงาน · หุ่นยนต์ไม่ตอบสนอง", commandSentWaiting:"{command}: ส่งคำสั่งแล้ว กำลังรอการยืนยัน", commandConfirmed:"{command}: หุ่นยนต์ยืนยันแล้ว", commandNotConfirmed:"{command}: คลาวด์ยอมรับแล้ว แต่หุ่นยนต์ไม่ได้ยืนยัน", commandFailed:"การทำงานล้มเหลว: {command}" },
  vi: { cloudChecking:"☁ Đám mây: đang kiểm tra…", cloudDisconnected:"☁ Đám mây: mất kết nối", cloudRobotOnline:"☁ Đám mây: hoạt động · Robot: trực tuyến", cloudRobotNoResponse:"☁ Đám mây: hoạt động · Robot không phản hồi", commandSentWaiting:"{command}: đã gửi lệnh, đang chờ xác nhận.", commandConfirmed:"{command}: robot đã xác nhận.", commandNotConfirmed:"{command}: đám mây đã chấp nhận nhưng robot chưa xác nhận.", commandFailed:"Thao tác thất bại: {command}" },
  ko: { cloudChecking:"☁ 클라우드: 확인 중…", cloudDisconnected:"☁ 클라우드: 연결 끊김", cloudRobotOnline:"☁ 클라우드: 활성 · 로봇: 온라인", cloudRobotNoResponse:"☁ 클라우드: 활성 · 로봇 응답 없음", commandSentWaiting:"{command}: 명령을 전송했습니다. 확인 대기 중입니다.", commandConfirmed:"{command}: 로봇이 확인했습니다.", commandNotConfirmed:"{command}: 클라우드는 수락했지만 로봇이 확인하지 않았습니다.", commandFailed:"작업 실패: {command}" },
  km: { cloudChecking:"☁ ក្លោដ៖ កំពុងពិនិត្យ…", cloudDisconnected:"☁ ក្លោដ៖ មិនបានភ្ជាប់", cloudRobotOnline:"☁ ក្លោដ៖ សកម្ម · រ៉ូបូត៖ អនឡាញ", cloudRobotNoResponse:"☁ ក្លោដ៖ សកម្ម · រ៉ូបូតមិនឆ្លើយតប", commandSentWaiting:"{command}៖ បានផ្ញើពាក្យបញ្ជា កំពុងរង់ចាំការបញ្ជាក់។", commandConfirmed:"{command}៖ រ៉ូបូតបានបញ្ជាក់។", commandNotConfirmed:"{command}៖ ក្លោដបានទទួល ប៉ុន្តែរ៉ូបូតមិនបានបញ្ជាក់។", commandFailed:"ប្រតិបត្តិការបរាជ័យ៖ {command}" },
};

const commandStageTranslations = {
  en: { commandCloudAccepted:"Cloud accepted: {command}", commandCloudRejected:"Cloud rejected: {command}" },
  hu: { commandCloudAccepted:"A felhő elfogadta: {command}", commandCloudRejected:"A felhő elutasította: {command}" },
  de: { commandCloudAccepted:"Von der Cloud akzeptiert: {command}", commandCloudRejected:"Von der Cloud abgelehnt: {command}" },
  fr: { commandCloudAccepted:"Acceptée par le cloud : {command}", commandCloudRejected:"Rejetée par le cloud : {command}" },
  es: { commandCloudAccepted:"Aceptado por la nube: {command}", commandCloudRejected:"Rechazado por la nube: {command}" },
  it: { commandCloudAccepted:"Accettato dal cloud: {command}", commandCloudRejected:"Rifiutato dal cloud: {command}" },
  pt: { commandCloudAccepted:"Aceite pela nuvem: {command}", commandCloudRejected:"Rejeitado pela nuvem: {command}" },
  nl: { commandCloudAccepted:"Geaccepteerd door de cloud: {command}", commandCloudRejected:"Geweigerd door de cloud: {command}" },
  pl: { commandCloudAccepted:"Zaakceptowane przez chmurę: {command}", commandCloudRejected:"Odrzucone przez chmurę: {command}" },
  cs: { commandCloudAccepted:"Přijato cloudem: {command}", commandCloudRejected:"Odmítnuto cloudem: {command}" },
  sk: { commandCloudAccepted:"Prijaté cloudom: {command}", commandCloudRejected:"Odmietnuté cloudom: {command}" },
  ro: { commandCloudAccepted:"Acceptată de cloud: {command}", commandCloudRejected:"Respinsă de cloud: {command}" },
  da: { commandCloudAccepted:"Accepteret af cloud: {command}", commandCloudRejected:"Afvist af cloud: {command}" },
  sv: { commandCloudAccepted:"Accepterat av molnet: {command}", commandCloudRejected:"Avvisat av molnet: {command}" },
  no: { commandCloudAccepted:"Godtatt av skyen: {command}", commandCloudRejected:"Avvist av skyen: {command}" },
  fi: { commandCloudAccepted:"Pilvi hyväksyi: {command}", commandCloudRejected:"Pilvi hylkäsi: {command}" },
  "zh-CN": { commandCloudAccepted:"云端已接受：{command}", commandCloudRejected:"云端已拒绝：{command}" },
  "zh-TW": { commandCloudAccepted:"雲端已接受：{command}", commandCloudRejected:"雲端已拒絕：{command}" },
  tr: { commandCloudAccepted:"Bulut kabul etti: {command}", commandCloudRejected:"Bulut reddetti: {command}" },
  th: { commandCloudAccepted:"คลาวด์ยอมรับแล้ว: {command}", commandCloudRejected:"คลาวด์ปฏิเสธ: {command}" },
  vi: { commandCloudAccepted:"Đám mây đã chấp nhận: {command}", commandCloudRejected:"Đám mây đã từ chối: {command}" },
  ko: { commandCloudAccepted:"클라우드가 수락했습니다: {command}", commandCloudRejected:"클라우드가 거부했습니다: {command}" },
  km: { commandCloudAccepted:"ក្លោដបានទទួល៖ {command}", commandCloudRejected:"ក្លោដបានបដិសេធ៖ {command}" },
};

const commandTranslations = {
  en:{ commandOuterEdge:"Outer edge mowing", commandDockEdge:"Dock surroundings mowing" },
  hu:{ commandOuterEdge:"Külső szegélynyírás", commandDockEdge:"Töltő körüli nyírás" },
  de:{ commandOuterEdge:"Außenkantenmähen", commandDockEdge:"Mähen um die Ladestation" },
  fr:{ commandOuterEdge:"Tonte de la bordure extérieure", commandDockEdge:"Tonte autour de la station" },
  es:{ commandOuterEdge:"Corte del borde exterior", commandDockEdge:"Corte alrededor de la base" },
  it:{ commandOuterEdge:"Taglio del bordo esterno", commandDockEdge:"Taglio intorno alla base" },
  pt:{ commandOuterEdge:"Corte da borda exterior", commandDockEdge:"Corte em redor da base" },
  nl:{ commandOuterEdge:"Buitenrand maaien", commandDockEdge:"Rond het laadstation maaien" },
  pl:{ commandOuterEdge:"Koszenie zewnętrznej krawędzi", commandDockEdge:"Koszenie wokół stacji" },
  cs:{ commandOuterEdge:"Sečení vnějšího okraje", commandDockEdge:"Sečení kolem stanice" },
  sk:{ commandOuterEdge:"Kosenie vonkajšieho okraja", commandDockEdge:"Kosenie okolo stanice" },
  ro:{ commandOuterEdge:"Tunderea marginii exterioare", commandDockEdge:"Tunderea în jurul stației" },
  da:{ commandOuterEdge:"Klipning af yderkant", commandDockEdge:"Klipning omkring ladestationen" },
  sv:{ commandOuterEdge:"Klippning av ytterkant", commandDockEdge:"Klippning runt laddstationen" },
  no:{ commandOuterEdge:"Klipping av ytterkant", commandDockEdge:"Klipping rundt ladestasjonen" },
  fi:{ commandOuterEdge:"Ulkoreunan leikkuu", commandDockEdge:"Leikkuu latausaseman ympärillä" },
  "zh-CN":{ commandOuterEdge:"外边界修剪", commandDockEdge:"充电座周边修剪" },
  "zh-TW":{ commandOuterEdge:"外邊界修剪", commandDockEdge:"充電座周邊修剪" },
  tr:{ commandOuterEdge:"Dış kenar biçme", commandDockEdge:"Şarj istasyonu çevresini biçme" },
  th:{ commandOuterEdge:"ตัดขอบด้านนอก", commandDockEdge:"ตัดรอบแท่นชาร์จ" },
  vi:{ commandOuterEdge:"Cắt viền ngoài", commandDockEdge:"Cắt quanh trạm sạc" },
  ko:{ commandOuterEdge:"외곽 가장자리 잔디 깎기", commandDockEdge:"충전소 주변 잔디 깎기" },
  km:{ commandOuterEdge:"កាត់គែមខាងក្រៅ", commandDockEdge:"កាត់ជុំវិញស្ថានីយសាក" },
};

const menuTranslations = {
  en:{ menu:"Menu" }, hu:{ menu:"Menü" }, de:{ menu:"Menü" },
  fr:{ menu:"Menu" }, es:{ menu:"Menú" }, it:{ menu:"Menu" },
  pt:{ menu:"Menu" }, nl:{ menu:"Menu" }, pl:{ menu:"Menu" },
  cs:{ menu:"Nabídka" }, sk:{ menu:"Ponuka" }, ro:{ menu:"Meniu" },
  da:{ menu:"Menu" }, sv:{ menu:"Meny" }, no:{ menu:"Meny" },
  fi:{ menu:"Valikko" }, "zh-CN":{ menu:"菜单" }, "zh-TW":{ menu:"選單" },
  tr:{ menu:"Menü" }, th:{ menu:"เมนู" }, vi:{ menu:"Trình đơn" },
  ko:{ menu:"메뉴" }, km:{ menu:"ម៉ឺនុយ" },
};

const settingsTranslations = {
  "en": {
    "autoZone": "Auto zone",
    "mowCount": "Mowing passes",
    "visualObstacle": "Visual obstacle detection",
    "visualObstacleLevel": "Obstacle sensitivity",
    "low": "Low",
    "medium": "Medium",
    "high": "High"
  },
  "hu": {
    "autoZone": "Automatikus zóna",
    "mowCount": "Nyírások száma",
    "visualObstacle": "Vizuális akadályérzékelés",
    "visualObstacleLevel": "Akadályérzékelés szintje",
    "low": "Alacsony",
    "medium": "Közepes",
    "high": "Magas"
  },
  "de": {
    "autoZone": "Automatische Zone",
    "mowCount": "Mähdurchgänge",
    "visualObstacle": "Visuelle Hinderniserkennung",
    "visualObstacleLevel": "Hindernisempfindlichkeit",
    "low": "Niedrig",
    "medium": "Mittel",
    "high": "Hoch"
  },
  "fr": {
    "autoZone": "Zone automatique",
    "mowCount": "Passages de tonte",
    "visualObstacle": "Détection visuelle des obstacles",
    "visualObstacleLevel": "Sensibilité aux obstacles",
    "low": "Faible",
    "medium": "Moyenne",
    "high": "Élevée"
  },
  "es": {
    "autoZone": "Zona automática",
    "mowCount": "Pasadas de corte",
    "visualObstacle": "Detección visual de obstáculos",
    "visualObstacleLevel": "Sensibilidad a obstáculos",
    "low": "Baja",
    "medium": "Media",
    "high": "Alta"
  },
  "it": {
    "autoZone": "Zona automatica",
    "mowCount": "Passaggi di taglio",
    "visualObstacle": "Rilevamento visivo ostacoli",
    "visualObstacleLevel": "Sensibilità agli ostacoli",
    "low": "Bassa",
    "medium": "Media",
    "high": "Alta"
  },
  "pt": {
    "autoZone": "Zona automática",
    "mowCount": "Passagens de corte",
    "visualObstacle": "Deteção visual de obstáculos",
    "visualObstacleLevel": "Sensibilidade a obstáculos",
    "low": "Baixa",
    "medium": "Média",
    "high": "Alta"
  },
  "nl": {
    "autoZone": "Automatische zone",
    "mowCount": "Maaibeurten",
    "visualObstacle": "Visuele obstakeldetectie",
    "visualObstacleLevel": "Obstakelgevoeligheid",
    "low": "Laag",
    "medium": "Gemiddeld",
    "high": "Hoog"
  },
  "pl": {
    "autoZone": "Strefa automatyczna",
    "mowCount": "Liczba przejazdów",
    "visualObstacle": "Wizualne wykrywanie przeszkód",
    "visualObstacleLevel": "Czułość na przeszkody",
    "low": "Niska",
    "medium": "Średnia",
    "high": "Wysoka"
  },
  "cs": {
    "autoZone": "Automatická zóna",
    "mowCount": "Počet přejezdů",
    "visualObstacle": "Vizuální detekce překážek",
    "visualObstacleLevel": "Citlivost na překážky",
    "low": "Nízká",
    "medium": "Střední",
    "high": "Vysoká"
  },
  "sk": {
    "autoZone": "Automatická zóna",
    "mowCount": "Počet prejazdov",
    "visualObstacle": "Vizuálna detekcia prekážok",
    "visualObstacleLevel": "Citlivosť na prekážky",
    "low": "Nízka",
    "medium": "Stredná",
    "high": "Vysoká"
  },
  "ro": {
    "autoZone": "Zonă automată",
    "mowCount": "Treceri de tundere",
    "visualObstacle": "Detectare vizuală a obstacolelor",
    "visualObstacleLevel": "Sensibilitate la obstacole",
    "low": "Scăzută",
    "medium": "Medie",
    "high": "Ridicată"
  },
  "da": {
    "autoZone": "Automatisk zone",
    "mowCount": "Klipninger",
    "visualObstacle": "Visuel forhindringsregistrering",
    "visualObstacleLevel": "Følsomhed for forhindringer",
    "low": "Lav",
    "medium": "Mellem",
    "high": "Høj"
  },
  "sv": {
    "autoZone": "Automatisk zon",
    "mowCount": "Klippass",
    "visualObstacle": "Visuell hinderdetektering",
    "visualObstacleLevel": "Hinderkänslighet",
    "low": "Låg",
    "medium": "Medel",
    "high": "Hög"
  },
  "no": {
    "autoZone": "Automatisk sone",
    "mowCount": "Klippepasseringer",
    "visualObstacle": "Visuell hinderdeteksjon",
    "visualObstacleLevel": "Hinderfølsomhet",
    "low": "Lav",
    "medium": "Middels",
    "high": "Høy"
  },
  "fi": {
    "autoZone": "Automaattinen alue",
    "mowCount": "Leikkuukerrat",
    "visualObstacle": "Visuaalinen esteentunnistus",
    "visualObstacleLevel": "Esteherkkyys",
    "low": "Matala",
    "medium": "Keskitaso",
    "high": "Korkea"
  },
  "zh-CN": {
    "autoZone": "自动区域",
    "mowCount": "割草遍数",
    "visualObstacle": "视觉障碍物检测",
    "visualObstacleLevel": "障碍物检测灵敏度",
    "low": "低",
    "medium": "中",
    "high": "高"
  },
  "zh-TW": {
    "autoZone": "自動區域",
    "mowCount": "割草遍數",
    "visualObstacle": "視覺障礙物偵測",
    "visualObstacleLevel": "障礙物偵測靈敏度",
    "low": "低",
    "medium": "中",
    "high": "高"
  },
  "tr": {
    "autoZone": "Otomatik bölge",
    "mowCount": "Biçme geçişleri",
    "visualObstacle": "Görsel engel algılama",
    "visualObstacleLevel": "Engel hassasiyeti",
    "low": "Düşük",
    "medium": "Orta",
    "high": "Yüksek"
  },
  "th": {
    "autoZone": "โซนอัตโนมัติ",
    "mowCount": "จำนวนรอบการตัด",
    "visualObstacle": "การตรวจจับสิ่งกีดขวางด้วยภาพ",
    "visualObstacleLevel": "ความไวต่อสิ่งกีดขวาง",
    "low": "ต่ำ",
    "medium": "ปานกลาง",
    "high": "สูง"
  },
  "vi": {
    "autoZone": "Vùng tự động",
    "mowCount": "Số lượt cắt",
    "visualObstacle": "Phát hiện chướng ngại vật bằng hình ảnh",
    "visualObstacleLevel": "Độ nhạy chướng ngại vật",
    "low": "Thấp",
    "medium": "Trung bình",
    "high": "Cao"
  },
  "ko": {
    "autoZone": "자동 구역",
    "mowCount": "잔디 깎기 횟수",
    "visualObstacle": "시각 장애물 감지",
    "visualObstacleLevel": "장애물 감도",
    "low": "낮음",
    "medium": "중간",
    "high": "높음"
  },
  "km": {
    "autoZone": "តំបន់ស្វ័យប្រវត្តិ",
    "mowCount": "ចំនួនជុំកាត់ស្មៅ",
    "visualObstacle": "ការរកឃើញឧបសគ្គដោយរូបភាព",
    "visualObstacleLevel": "កម្រិតភាពរសើបឧបសគ្គ",
    "low": "ទាប",
    "medium": "មធ្យម",
    "high": "ខ្ពស់"
  }
};

const beta5SettingsTranslations = {
  "en": { globalSettings:"Global settings", manualZones:"Manual zones", autoZones:"Automatic zones", edgeCutting:"Edge cutting" },
  "hu": { globalSettings:"Globális beállítások", manualZones:"Kézi zónák", autoZones:"Automatikus zónák", edgeCutting:"Szegélyvágás" },
  "de": { globalSettings:"Globale Einstellungen", manualZones:"Manuelle Zonen", autoZones:"Automatische Zonen", edgeCutting:"Kantenschnitt" },
  "fr": { globalSettings:"Paramètres globaux", manualZones:"Zones manuelles", autoZones:"Zones automatiques", edgeCutting:"Coupe des bordures" },
  "es": { globalSettings:"Ajustes globales", manualZones:"Zonas manuales", autoZones:"Zonas automáticas", edgeCutting:"Corte de bordes" },
  "it": { globalSettings:"Impostazioni globali", manualZones:"Zone manuali", autoZones:"Zone automatiche", edgeCutting:"Taglio bordi" },
  "pt": { globalSettings:"Definições globais", manualZones:"Zonas manuais", autoZones:"Zonas automáticas", edgeCutting:"Corte de bordas" },
  "nl": { globalSettings:"Algemene instellingen", manualZones:"Handmatige zones", autoZones:"Automatische zones", edgeCutting:"Rand maaien" },
  "pl": { globalSettings:"Ustawienia globalne", manualZones:"Strefy ręczne", autoZones:"Strefy automatyczne", edgeCutting:"Koszenie krawędzi" },
  "cs": { globalSettings:"Globální nastavení", manualZones:"Ruční zóny", autoZones:"Automatické zóny", edgeCutting:"Sečení okrajů" },
  "sk": { globalSettings:"Globálne nastavenia", manualZones:"Ručné zóny", autoZones:"Automatické zóny", edgeCutting:"Kosenie okrajov" },
  "ro": { globalSettings:"Setări globale", manualZones:"Zone manuale", autoZones:"Zone automate", edgeCutting:"Tunderea marginilor" },
  "da": { globalSettings:"Globale indstillinger", manualZones:"Manuelle zoner", autoZones:"Automatiske zoner", edgeCutting:"Kantklipning" },
  "sv": { globalSettings:"Globala inställningar", manualZones:"Manuella zoner", autoZones:"Automatiska zoner", edgeCutting:"Kantklippning" },
  "no": { globalSettings:"Globale innstillinger", manualZones:"Manuelle soner", autoZones:"Automatiske soner", edgeCutting:"Kantklipping" },
  "fi": { globalSettings:"Yleiset asetukset", manualZones:"Manuaaliset alueet", autoZones:"Automaattiset alueet", edgeCutting:"Reunaleikkuu" },
  "zh-CN": { globalSettings:"全局设置", manualZones:"手动区域", autoZones:"自动区域", edgeCutting:"边缘修剪" },
  "zh-TW": { globalSettings:"全域設定", manualZones:"手動區域", autoZones:"自動區域", edgeCutting:"邊緣修剪" },
  "tr": { globalSettings:"Genel ayarlar", manualZones:"Manuel bölgeler", autoZones:"Otomatik bölgeler", edgeCutting:"Kenar biçme" },
  "th": { globalSettings:"การตั้งค่าทั่วไป", manualZones:"โซนแบบกำหนดเอง", autoZones:"โซนอัตโนมัติ", edgeCutting:"การตัดขอบ" },
  "vi": { globalSettings:"Cài đặt chung", manualZones:"Vùng thủ công", autoZones:"Vùng tự động", edgeCutting:"Cắt mép" },
  "ko": { globalSettings:"전체 설정", manualZones:"수동 구역", autoZones:"자동 구역", edgeCutting:"가장자리 깎기" },
  "km": { globalSettings:"ការកំណត់ទូទៅ", manualZones:"តំបន់ដោយដៃ", autoZones:"តំបន់ស្វ័យប្រវត្តិ", edgeCutting:"ការកាត់គែម" }
};
for (const [language, values] of Object.entries(beta5SettingsTranslations)) {
  Object.assign(settingsTranslations[language] || (settingsTranslations[language] = {}), values);
}

const beta8Translations = {
  en:{resumeTask:"Resume task",resumeTaskSub:"Continue the paused mowing task",edgeReturn:"Edge-following return",autoDockMow:"Mow around dock after each task",maintenance:"Maintenance",resetBlade:"Reset blade counter",resetCamera:"Reset camera counter",resetDockContact:"Reset charging-contact counter",resetCounterWarning:"Reset only after servicing",mowingHistory:"Previous mowing tasks",errorHistory:"Detailed error history"},
  hu:{resumeTask:"Feladat folytatása",resumeTaskSub:"A szüneteltetett nyírás folytatása",edgeReturn:"Szegély mentén visszatérés",autoDockMow:"Automatikus töltőkörnyéki nyírás",maintenance:"Karbantartás",resetBlade:"Késszámláló nullázása",resetCamera:"Kameraszámláló nullázása",resetDockContact:"Töltőérintkező számlálójának nullázása",resetCounterWarning:"Csak karbantartás után nullázd",mowingHistory:"Korábbi nyírási feladatok",errorHistory:"Részletes hibakód-előzmények"},
  de:{resumeTask:"Aufgabe fortsetzen",resumeTaskSub:"Pausierte Mähaufgabe fortsetzen",edgeReturn:"Rückkehr entlang der Kante",autoDockMow:"Nach jeder Aufgabe um die Station mähen",maintenance:"Wartung",resetBlade:"Messerzähler zurücksetzen",resetCamera:"Kamerazähler zurücksetzen",resetDockContact:"Ladekontaktzähler zurücksetzen",resetCounterWarning:"Nur nach Wartung zurücksetzen",mowingHistory:"Frühere Mähaufgaben",errorHistory:"Detaillierter Fehlerverlauf"},
  fr:{resumeTask:"Reprendre la tâche",resumeTaskSub:"Continuer la tonte en pause",edgeReturn:"Retour le long de la bordure",autoDockMow:"Tondre autour de la station après chaque tâche",maintenance:"Entretien",resetBlade:"Réinitialiser le compteur de lame",resetCamera:"Réinitialiser le compteur caméra",resetDockContact:"Réinitialiser le compteur de contact",resetCounterWarning:"Réinitialiser après entretien seulement",mowingHistory:"Tontes précédentes",errorHistory:"Historique détaillé des erreurs"},
  es:{resumeTask:"Reanudar tarea",resumeTaskSub:"Continuar la tarea de corte pausada",edgeReturn:"Regreso siguiendo el borde",autoDockMow:"Cortar alrededor de la base tras cada tarea",maintenance:"Mantenimiento",resetBlade:"Restablecer contador de cuchilla",resetCamera:"Restablecer contador de cámara",resetDockContact:"Restablecer contador de contacto",resetCounterWarning:"Restablecer solo tras mantenimiento",mowingHistory:"Tareas de corte anteriores",errorHistory:"Historial detallado de errores"},
  it:{resumeTask:"Riprendi attività",resumeTaskSub:"Continua il taglio in pausa",edgeReturn:"Ritorno lungo il bordo",autoDockMow:"Taglia intorno alla base dopo ogni attività",maintenance:"Manutenzione",resetBlade:"Azzera contatore lama",resetCamera:"Azzera contatore fotocamera",resetDockContact:"Azzera contatore contatti",resetCounterWarning:"Azzerare solo dopo la manutenzione",mowingHistory:"Attività di taglio precedenti",errorHistory:"Cronologia dettagliata errori"},
  pt:{resumeTask:"Retomar tarefa",resumeTaskSub:"Continuar a tarefa de corte pausada",edgeReturn:"Regresso pela borda",autoDockMow:"Cortar à volta da base após cada tarefa",maintenance:"Manutenção",resetBlade:"Repor contador da lâmina",resetCamera:"Repor contador da câmara",resetDockContact:"Repor contador do contacto",resetCounterWarning:"Repor apenas após manutenção",mowingHistory:"Tarefas de corte anteriores",errorHistory:"Histórico detalhado de erros"},
  nl:{resumeTask:"Taak hervatten",resumeTaskSub:"Gepauzeerde maaitaak voortzetten",edgeReturn:"Terugkeer langs de rand",autoDockMow:"Na elke taak rond het laadstation maaien",maintenance:"Onderhoud",resetBlade:"Mesteller resetten",resetCamera:"Camerateller resetten",resetDockContact:"Contactteller resetten",resetCounterWarning:"Alleen na onderhoud resetten",mowingHistory:"Eerdere maaitaken",errorHistory:"Gedetailleerde foutgeschiedenis"},
  pl:{resumeTask:"Wznów zadanie",resumeTaskSub:"Kontynuuj wstrzymane koszenie",edgeReturn:"Powrót wzdłuż krawędzi",autoDockMow:"Koszenie wokół stacji po każdym zadaniu",maintenance:"Konserwacja",resetBlade:"Wyzeruj licznik ostrza",resetCamera:"Wyzeruj licznik kamery",resetDockContact:"Wyzeruj licznik styku",resetCounterWarning:"Zeruj tylko po konserwacji",mowingHistory:"Poprzednie zadania koszenia",errorHistory:"Szczegółowa historia błędów"},
  cs:{resumeTask:"Pokračovat v úloze",resumeTaskSub:"Pokračovat v pozastaveném sečení",edgeReturn:"Návrat podél okraje",autoDockMow:"Po každé úloze posekat kolem stanice",maintenance:"Údržba",resetBlade:"Vynulovat počítadlo nože",resetCamera:"Vynulovat počítadlo kamery",resetDockContact:"Vynulovat počítadlo kontaktu",resetCounterWarning:"Nulovat pouze po údržbě",mowingHistory:"Předchozí úlohy sečení",errorHistory:"Podrobná historie chyb"},
  sk:{resumeTask:"Pokračovať v úlohe",resumeTaskSub:"Pokračovať v pozastavenom kosení",edgeReturn:"Návrat pozdĺž okraja",autoDockMow:"Po každej úlohe kosiť okolo stanice",maintenance:"Údržba",resetBlade:"Vynulovať počítadlo noža",resetCamera:"Vynulovať počítadlo kamery",resetDockContact:"Vynulovať počítadlo kontaktu",resetCounterWarning:"Nulovať iba po údržbe",mowingHistory:"Predchádzajúce úlohy kosenia",errorHistory:"Podrobná história chýb"},
  ro:{resumeTask:"Reluare sarcină",resumeTaskSub:"Continuă tunderea întreruptă",edgeReturn:"Revenire de-a lungul marginii",autoDockMow:"Tundere în jurul stației după fiecare sarcină",maintenance:"Întreținere",resetBlade:"Resetare contor lamă",resetCamera:"Resetare contor cameră",resetDockContact:"Resetare contor contact",resetCounterWarning:"Resetați numai după întreținere",mowingHistory:"Sarcini de tundere anterioare",errorHistory:"Istoric detaliat al erorilor"},
  da:{resumeTask:"Fortsæt opgave",resumeTaskSub:"Fortsæt den pausede klipning",edgeReturn:"Retur langs kanten",autoDockMow:"Klip omkring stationen efter hver opgave",maintenance:"Vedligeholdelse",resetBlade:"Nulstil knivtæller",resetCamera:"Nulstil kameratæller",resetDockContact:"Nulstil kontakttæller",resetCounterWarning:"Nulstil kun efter service",mowingHistory:"Tidligere klippeopgaver",errorHistory:"Detaljeret fejlhistorik"},
  sv:{resumeTask:"Fortsätt uppgift",resumeTaskSub:"Fortsätt den pausade klippningen",edgeReturn:"Återgång längs kanten",autoDockMow:"Klipp runt stationen efter varje uppgift",maintenance:"Underhåll",resetBlade:"Nollställ knivräknare",resetCamera:"Nollställ kameraräknare",resetDockContact:"Nollställ kontakträknare",resetCounterWarning:"Nollställ endast efter service",mowingHistory:"Tidigare klippuppgifter",errorHistory:"Detaljerad felhistorik"},
  no:{resumeTask:"Fortsett oppgave",resumeTaskSub:"Fortsett den pausede klippingen",edgeReturn:"Retur langs kanten",autoDockMow:"Klipp rundt stasjonen etter hver oppgave",maintenance:"Vedlikehold",resetBlade:"Nullstill knivteller",resetCamera:"Nullstill kamerateller",resetDockContact:"Nullstill kontaktteller",resetCounterWarning:"Nullstill bare etter service",mowingHistory:"Tidligere klippeoppgaver",errorHistory:"Detaljert feilhistorikk"},
  fi:{resumeTask:"Jatka tehtävää",resumeTaskSub:"Jatka keskeytettyä leikkuuta",edgeReturn:"Paluu reunaa pitkin",autoDockMow:"Leikkaa aseman ympäriltä jokaisen tehtävän jälkeen",maintenance:"Huolto",resetBlade:"Nollaa terälaskuri",resetCamera:"Nollaa kameralaskuri",resetDockContact:"Nollaa kosketinlaskuri",resetCounterWarning:"Nollaa vain huollon jälkeen",mowingHistory:"Aiemmat leikkuutehtävät",errorHistory:"Yksityiskohtainen virhehistoria"},
  "zh-CN":{resumeTask:"继续任务",resumeTaskSub:"继续已暂停的割草任务",edgeReturn:"沿边返回",autoDockMow:"每次任务后修剪充电座周围",maintenance:"维护",resetBlade:"重置刀片计数器",resetCamera:"重置摄像头计数器",resetDockContact:"重置充电触点计数器",resetCounterWarning:"仅在维护后重置",mowingHistory:"以前的割草任务",errorHistory:"详细错误历史"},
  "zh-TW":{resumeTask:"繼續任務",resumeTaskSub:"繼續已暫停的割草任務",edgeReturn:"沿邊返回",autoDockMow:"每次任務後修剪充電座周圍",maintenance:"維護",resetBlade:"重設刀片計數器",resetCamera:"重設攝影機計數器",resetDockContact:"重設充電接點計數器",resetCounterWarning:"僅在維護後重設",mowingHistory:"以前的割草任務",errorHistory:"詳細錯誤歷史"},
  tr:{resumeTask:"Görevi sürdür",resumeTaskSub:"Duraklatılan biçme görevine devam et",edgeReturn:"Kenar boyunca dönüş",autoDockMow:"Her görevden sonra istasyon çevresini biç",maintenance:"Bakım",resetBlade:"Bıçak sayacını sıfırla",resetCamera:"Kamera sayacını sıfırla",resetDockContact:"Şarj kontağı sayacını sıfırla",resetCounterWarning:"Yalnızca bakımdan sonra sıfırla",mowingHistory:"Önceki biçme görevleri",errorHistory:"Ayrıntılı hata geçmişi"},
  th:{resumeTask:"ทำงานต่อ",resumeTaskSub:"ทำงานตัดหญ้าที่หยุดชั่วคราวต่อ",edgeReturn:"กลับตามแนวขอบ",autoDockMow:"ตัดรอบแท่นหลังทุกงาน",maintenance:"การบำรุงรักษา",resetBlade:"รีเซ็ตตัวนับใบมีด",resetCamera:"รีเซ็ตตัวนับกล้อง",resetDockContact:"รีเซ็ตตัวนับหน้าสัมผัส",resetCounterWarning:"รีเซ็ตหลังบำรุงรักษาเท่านั้น",mowingHistory:"งานตัดหญ้าก่อนหน้า",errorHistory:"ประวัติข้อผิดพลาดโดยละเอียด"},
  vi:{resumeTask:"Tiếp tục tác vụ",resumeTaskSub:"Tiếp tục tác vụ cắt đang tạm dừng",edgeReturn:"Trở về dọc theo mép",autoDockMow:"Cắt quanh trạm sau mỗi tác vụ",maintenance:"Bảo trì",resetBlade:"Đặt lại bộ đếm lưỡi",resetCamera:"Đặt lại bộ đếm camera",resetDockContact:"Đặt lại bộ đếm tiếp điểm",resetCounterWarning:"Chỉ đặt lại sau bảo trì",mowingHistory:"Các tác vụ cắt trước",errorHistory:"Lịch sử lỗi chi tiết"},
  ko:{resumeTask:"작업 계속",resumeTaskSub:"일시 중지된 잔디 깎기 계속",edgeReturn:"가장자리를 따라 복귀",autoDockMow:"각 작업 후 충전소 주변 깎기",maintenance:"유지보수",resetBlade:"날 카운터 초기화",resetCamera:"카메라 카운터 초기화",resetDockContact:"충전 접점 카운터 초기화",resetCounterWarning:"정비 후에만 초기화",mowingHistory:"이전 잔디 깎기 작업",errorHistory:"상세 오류 기록"},
  km:{resumeTask:"បន្តកិច្ចការ",resumeTaskSub:"បន្តការកាត់ស្មៅដែលបានផ្អាក",edgeReturn:"ត្រឡប់តាមគែម",autoDockMow:"កាត់ជុំវិញស្ថានីយក្រោយរាល់កិច្ចការ",maintenance:"ការថែទាំ",resetBlade:"កំណត់បញ្ជរផ្លែឡាមឡើងវិញ",resetCamera:"កំណត់បញ្ជរកាមេរ៉ាឡើងវិញ",resetDockContact:"កំណត់បញ្ជរទំនាក់ទំនងឡើងវិញ",resetCounterWarning:"កំណត់ឡើងវិញក្រោយថែទាំប៉ុណ្ណោះ",mowingHistory:"កិច្ចការកាត់ស្មៅមុន",errorHistory:"ប្រវត្តិកំហុសលម្អិត"}
};
for (const [language, values] of Object.entries(beta8Translations)) {
  Object.assign(settingsTranslations[language] || (settingsTranslations[language] = {}), values);
}

const noTaskToResumeTranslations = {
  en:"There is no task to resume. Start a new mowing task.", hu:"Nincs folytatható feladat. Indíts új nyírást.", de:"Es gibt keine fortsetzbare Aufgabe. Starten Sie eine neue Mähaufgabe.", fr:"Aucune tâche à reprendre. Démarrez une nouvelle tonte.", es:"No hay ninguna tarea que reanudar. Inicia una nueva tarea de corte.", it:"Non ci sono attività da riprendere. Avvia un nuovo taglio.", pt:"Não há tarefa para retomar. Inicie uma nova tarefa de corte.", nl:"Er is geen taak om te hervatten. Start een nieuwe maaibeurt.", pl:"Brak zadania do wznowienia. Uruchom nowe koszenie.", cs:"Není žádná úloha k obnovení. Spusťte nové sečení.", sk:"Nie je žiadna úloha na pokračovanie. Spustite nové kosenie.", ro:"Nu există nicio sarcină de reluat. Porniți o tundere nouă.", da:"Der er ingen opgave at fortsætte. Start en ny klipning.", sv:"Det finns ingen uppgift att fortsätta. Starta en ny klippning.", no:"Det finnes ingen oppgave å fortsette. Start en ny klipping.", fi:"Jatkettavaa tehtävää ei ole. Aloita uusi leikkuu.", "zh-CN":"没有可继续的任务。请开始新的割草任务。", "zh-TW":"沒有可繼續的任務。請開始新的割草任務。", tr:"Devam ettirilecek görev yok. Yeni bir biçme görevi başlatın.", th:"ไม่มีงานให้ทำต่อ โปรดเริ่มงานตัดหญ้าใหม่", vi:"Không có tác vụ để tiếp tục. Hãy bắt đầu một tác vụ cắt mới.", ko:"계속할 작업이 없습니다. 새 잔디 깎기 작업을 시작하세요.", km:"មិនមានកិច្ចការសម្រាប់បន្តទេ។ សូមចាប់ផ្តើមការកាត់ស្មៅថ្មី។"
};
for (const [language, value] of Object.entries(noTaskToResumeTranslations)) {
  Object.assign(settingsTranslations[language] || (settingsTranslations[language] = {}), {noTaskToResume:value});
}

const appStyleTaskTranslations = {
  en:{fullArea:"Full area",selectMowingTarget:"Select for the next mowing task"}, hu:{fullArea:"Teljes terület",selectMowingTarget:"Kijelölés a következő nyíráshoz"}, de:{fullArea:"Gesamte Fläche",selectMowingTarget:"Für die nächste Mähaufgabe auswählen"}, fr:{fullArea:"Zone entière",selectMowingTarget:"Sélectionner pour la prochaine tonte"}, es:{fullArea:"Área completa",selectMowingTarget:"Seleccionar para la próxima tarea"}, it:{fullArea:"Area completa",selectMowingTarget:"Seleziona per il prossimo taglio"}, pt:{fullArea:"Área completa",selectMowingTarget:"Selecionar para a próxima tarefa"}, nl:{fullArea:"Volledig gebied",selectMowingTarget:"Selecteren voor de volgende maaibeurt"}, pl:{fullArea:"Cały obszar",selectMowingTarget:"Wybierz do następnego koszenia"}, cs:{fullArea:"Celá plocha",selectMowingTarget:"Vybrat pro další sečení"}, sk:{fullArea:"Celá plocha",selectMowingTarget:"Vybrať pre ďalšie kosenie"}, ro:{fullArea:"Întreaga zonă",selectMowingTarget:"Selectați pentru următoarea tundere"}, da:{fullArea:"Hele området",selectMowingTarget:"Vælg til næste klipning"}, sv:{fullArea:"Hela området",selectMowingTarget:"Välj för nästa klippning"}, no:{fullArea:"Hele området",selectMowingTarget:"Velg for neste klipping"}, fi:{fullArea:"Koko alue",selectMowingTarget:"Valitse seuraavaa leikkuuta varten"}, "zh-CN":{fullArea:"全部区域",selectMowingTarget:"选择用于下一次割草"}, "zh-TW":{fullArea:"全部區域",selectMowingTarget:"選擇用於下一次割草"}, tr:{fullArea:"Tüm alan",selectMowingTarget:"Sonraki biçme görevi için seçin"}, th:{fullArea:"พื้นที่ทั้งหมด",selectMowingTarget:"เลือกสำหรับงานตัดหญ้าครั้งถัดไป"}, vi:{fullArea:"Toàn bộ khu vực",selectMowingTarget:"Chọn cho lần cắt tiếp theo"}, ko:{fullArea:"전체 구역",selectMowingTarget:"다음 잔디 깎기 작업으로 선택"}, km:{fullArea:"តំបន់ទាំងមូល",selectMowingTarget:"ជ្រើសសម្រាប់ការកាត់ស្មៅបន្ទាប់"}
};
for (const [language, values] of Object.entries(appStyleTaskTranslations)) {
  Object.assign(settingsTranslations[language] || (settingsTranslations[language] = {}), values);
}

const selectedTaskStartTranslations = {
  en:"Start selected task", hu:"Kijelölt feladat indítása", de:"Ausgewählte Aufgabe starten", fr:"Démarrer la tâche sélectionnée", es:"Iniciar tarea seleccionada", it:"Avvia attività selezionata", pt:"Iniciar tarefa selecionada", nl:"Geselecteerde taak starten", pl:"Uruchom wybrane zadanie", cs:"Spustit vybranou úlohu", sk:"Spustiť vybranú úlohu", ro:"Pornește sarcina selectată", da:"Start valgt opgave", sv:"Starta vald uppgift", no:"Start valgt oppgave", fi:"Aloita valittu tehtävä", "zh-CN":"开始所选任务", "zh-TW":"開始所選任務", tr:"Seçilen görevi başlat", th:"เริ่มงานที่เลือก", vi:"Bắt đầu tác vụ đã chọn", ko:"선택한 작업 시작", km:"ចាប់ផ្តើមកិច្ចការដែលបានជ្រើស"
};
for (const [language, value] of Object.entries(selectedTaskStartTranslations)) {
  Object.assign(settingsTranslations[language] || (settingsTranslations[language] = {}), {startSelectedTask:value});
}

const beta9Translations = {
  en:{pauseTask:"Pause task",pauseTaskSub:"Pause the current mowing task"},
  hu:{pauseTask:"Szüneteltetés",pauseTaskSub:"Az aktuális nyírás szüneteltetése"},
  de:{pauseTask:"Aufgabe pausieren",pauseTaskSub:"Aktuelle Mähaufgabe pausieren"},
  fr:{pauseTask:"Mettre en pause",pauseTaskSub:"Mettre la tonte actuelle en pause"},
  es:{pauseTask:"Pausar tarea",pauseTaskSub:"Pausar la tarea de corte actual"},
  it:{pauseTask:"Metti in pausa",pauseTaskSub:"Metti in pausa il taglio attuale"},
  pt:{pauseTask:"Pausar tarefa",pauseTaskSub:"Pausar a tarefa de corte atual"},
  nl:{pauseTask:"Taak pauzeren",pauseTaskSub:"Huidige maaitaak pauzeren"},
  pl:{pauseTask:"Wstrzymaj zadanie",pauseTaskSub:"Wstrzymaj bieżące koszenie"},
  cs:{pauseTask:"Pozastavit úlohu",pauseTaskSub:"Pozastavit aktuální sečení"},
  sk:{pauseTask:"Pozastaviť úlohu",pauseTaskSub:"Pozastaviť aktuálne kosenie"},
  ro:{pauseTask:"Întrerupe sarcina",pauseTaskSub:"Întrerupe tunderea curentă"},
  da:{pauseTask:"Sæt opgave på pause",pauseTaskSub:"Sæt den aktuelle klipning på pause"},
  sv:{pauseTask:"Pausa uppgift",pauseTaskSub:"Pausa den aktuella klippningen"},
  no:{pauseTask:"Sett oppgave på pause",pauseTaskSub:"Sett den aktive klippingen på pause"},
  fi:{pauseTask:"Keskeytä tehtävä",pauseTaskSub:"Keskeytä nykyinen leikkuutehtävä"},
  "zh-CN":{pauseTask:"暂停任务",pauseTaskSub:"暂停当前割草任务"},
  "zh-TW":{pauseTask:"暫停任務",pauseTaskSub:"暫停目前割草任務"},
  tr:{pauseTask:"Görevi duraklat",pauseTaskSub:"Geçerli biçme görevini duraklat"},
  th:{pauseTask:"หยุดงานชั่วคราว",pauseTaskSub:"หยุดงานตัดหญ้าปัจจุบันชั่วคราว"},
  vi:{pauseTask:"Tạm dừng tác vụ",pauseTaskSub:"Tạm dừng tác vụ cắt hiện tại"},
  ko:{pauseTask:"작업 일시 중지",pauseTaskSub:"현재 잔디 깎기 작업 일시 중지"},
  km:{pauseTask:"ផ្អាកកិច្ចការ",pauseTaskSub:"ផ្អាកកិច្ចការកាត់ស្មៅបច្ចុប្បន្ន"}
};
for (const [language, values] of Object.entries(beta9Translations)) {
  Object.assign(settingsTranslations[language] || (settingsTranslations[language] = {}), values);
}

const beta10Translations = {
  en:{bladeMaintenance:"Blade maintenance",cameraMaintenance:"Camera cleaning",dockContactMaintenance:"Charging-contact cleaning",remainingLife:"Remaining service life",maintenanceUnavailable:"No data",resetBlade:"Reset after blade replacement",resetCamera:"Reset after camera cleaning",resetDockContact:"Reset after contact cleaning",resetCounterWarning:"Confirm only after completing the indicated maintenance."},
  hu:{bladeMaintenance:"Kés karbantartása",cameraMaintenance:"Kamera tisztítása",dockContactMaintenance:"Töltőérintkezők tisztítása",remainingLife:"Hátralévő karbantartási idő",maintenanceUnavailable:"Nincs adat",resetBlade:"Nullázás késcsere után",resetCamera:"Nullázás kameratisztítás után",resetDockContact:"Nullázás érintkezőtisztítás után",resetCounterWarning:"Csak a jelzett karbantartás elvégzése után erősítsd meg."},
  de:{bladeMaintenance:"Messerwartung",cameraMaintenance:"Kamerareinigung",dockContactMaintenance:"Ladekontakte reinigen",remainingLife:"Verbleibende Wartungsdauer",maintenanceUnavailable:"Keine Daten",resetBlade:"Nach Messerwechsel zurücksetzen",resetCamera:"Nach Kamerareinigung zurücksetzen",resetDockContact:"Nach Kontaktreinigung zurücksetzen",resetCounterWarning:"Nur nach der angegebenen Wartung bestätigen."},
  fr:{bladeMaintenance:"Entretien de la lame",cameraMaintenance:"Nettoyage de la caméra",dockContactMaintenance:"Nettoyage des contacts de charge",remainingLife:"Durée d’entretien restante",maintenanceUnavailable:"Aucune donnée",resetBlade:"Réinitialiser après remplacement de la lame",resetCamera:"Réinitialiser après nettoyage de la caméra",resetDockContact:"Réinitialiser après nettoyage des contacts",resetCounterWarning:"Confirmez uniquement après l’entretien indiqué."},
  es:{bladeMaintenance:"Mantenimiento de cuchilla",cameraMaintenance:"Limpieza de cámara",dockContactMaintenance:"Limpieza de contactos de carga",remainingLife:"Vida de mantenimiento restante",maintenanceUnavailable:"Sin datos",resetBlade:"Restablecer tras cambiar la cuchilla",resetCamera:"Restablecer tras limpiar la cámara",resetDockContact:"Restablecer tras limpiar los contactos",resetCounterWarning:"Confirma solo después del mantenimiento indicado."},
  it:{bladeMaintenance:"Manutenzione lama",cameraMaintenance:"Pulizia fotocamera",dockContactMaintenance:"Pulizia contatti di ricarica",remainingLife:"Durata manutenzione residua",maintenanceUnavailable:"Nessun dato",resetBlade:"Azzera dopo la sostituzione della lama",resetCamera:"Azzera dopo la pulizia della fotocamera",resetDockContact:"Azzera dopo la pulizia dei contatti",resetCounterWarning:"Conferma solo dopo la manutenzione indicata."},
  pt:{bladeMaintenance:"Manutenção da lâmina",cameraMaintenance:"Limpeza da câmara",dockContactMaintenance:"Limpeza dos contactos de carga",remainingLife:"Vida útil restante",maintenanceUnavailable:"Sem dados",resetBlade:"Repor após trocar a lâmina",resetCamera:"Repor após limpar a câmara",resetDockContact:"Repor após limpar os contactos",resetCounterWarning:"Confirme apenas após a manutenção indicada."},
  nl:{bladeMaintenance:"Mesonderhoud",cameraMaintenance:"Camera reinigen",dockContactMaintenance:"Laadcontacten reinigen",remainingLife:"Resterende onderhoudsduur",maintenanceUnavailable:"Geen gegevens",resetBlade:"Resetten na mesvervanging",resetCamera:"Resetten na camerareiniging",resetDockContact:"Resetten na contactreiniging",resetCounterWarning:"Bevestig alleen na het aangegeven onderhoud."},
  pl:{bladeMaintenance:"Konserwacja ostrza",cameraMaintenance:"Czyszczenie kamery",dockContactMaintenance:"Czyszczenie styków ładowania",remainingLife:"Pozostały okres konserwacji",maintenanceUnavailable:"Brak danych",resetBlade:"Wyzeruj po wymianie ostrza",resetCamera:"Wyzeruj po czyszczeniu kamery",resetDockContact:"Wyzeruj po czyszczeniu styków",resetCounterWarning:"Potwierdź dopiero po wykonaniu wskazanej konserwacji."},
  cs:{bladeMaintenance:"Údržba nože",cameraMaintenance:"Čištění kamery",dockContactMaintenance:"Čištění nabíjecích kontaktů",remainingLife:"Zbývající servisní životnost",maintenanceUnavailable:"Žádná data",resetBlade:"Vynulovat po výměně nože",resetCamera:"Vynulovat po vyčištění kamery",resetDockContact:"Vynulovat po vyčištění kontaktů",resetCounterWarning:"Potvrďte pouze po provedení uvedené údržby."},
  sk:{bladeMaintenance:"Údržba noža",cameraMaintenance:"Čistenie kamery",dockContactMaintenance:"Čistenie nabíjacích kontaktov",remainingLife:"Zostávajúca servisná životnosť",maintenanceUnavailable:"Žiadne údaje",resetBlade:"Vynulovať po výmene noža",resetCamera:"Vynulovať po vyčistení kamery",resetDockContact:"Vynulovať po vyčistení kontaktov",resetCounterWarning:"Potvrďte iba po vykonaní uvedenej údržby."},
  ro:{bladeMaintenance:"Întreținerea lamei",cameraMaintenance:"Curățarea camerei",dockContactMaintenance:"Curățarea contactelor de încărcare",remainingLife:"Durată de service rămasă",maintenanceUnavailable:"Fără date",resetBlade:"Resetare după schimbarea lamei",resetCamera:"Resetare după curățarea camerei",resetDockContact:"Resetare după curățarea contactelor",resetCounterWarning:"Confirmați numai după întreținerea indicată."},
  da:{bladeMaintenance:"Vedligeholdelse af kniv",cameraMaintenance:"Rengøring af kamera",dockContactMaintenance:"Rengøring af ladekontakter",remainingLife:"Resterende servicelevetid",maintenanceUnavailable:"Ingen data",resetBlade:"Nulstil efter knivskift",resetCamera:"Nulstil efter kamerarengøring",resetDockContact:"Nulstil efter kontaktrengøring",resetCounterWarning:"Bekræft kun efter den angivne vedligeholdelse."},
  sv:{bladeMaintenance:"Knivunderhåll",cameraMaintenance:"Kamerarengöring",dockContactMaintenance:"Rengöring av laddkontakter",remainingLife:"Återstående servicelivslängd",maintenanceUnavailable:"Inga data",resetBlade:"Nollställ efter knivbyte",resetCamera:"Nollställ efter kamerarengöring",resetDockContact:"Nollställ efter kontaktrengöring",resetCounterWarning:"Bekräfta endast efter angivet underhåll."},
  no:{bladeMaintenance:"Knivvedlikehold",cameraMaintenance:"Kamerarengjøring",dockContactMaintenance:"Rengjøring av ladekontakter",remainingLife:"Gjenværende servicelevetid",maintenanceUnavailable:"Ingen data",resetBlade:"Nullstill etter knivbytte",resetCamera:"Nullstill etter kamerarengjøring",resetDockContact:"Nullstill etter kontaktrengjøring",resetCounterWarning:"Bekreft bare etter angitt vedlikehold."},
  fi:{bladeMaintenance:"Terän huolto",cameraMaintenance:"Kameran puhdistus",dockContactMaintenance:"Latauskoskettimien puhdistus",remainingLife:"Jäljellä oleva huoltoaika",maintenanceUnavailable:"Ei tietoja",resetBlade:"Nollaa terän vaihdon jälkeen",resetCamera:"Nollaa kameran puhdistuksen jälkeen",resetDockContact:"Nollaa koskettimien puhdistuksen jälkeen",resetCounterWarning:"Vahvista vasta ilmoitetun huollon jälkeen."},
  "zh-CN":{bladeMaintenance:"刀片维护",cameraMaintenance:"摄像头清洁",dockContactMaintenance:"充电触点清洁",remainingLife:"剩余维护寿命",maintenanceUnavailable:"无数据",resetBlade:"更换刀片后重置",resetCamera:"清洁摄像头后重置",resetDockContact:"清洁触点后重置",resetCounterWarning:"仅在完成所示维护后确认。"},
  "zh-TW":{bladeMaintenance:"刀片維護",cameraMaintenance:"攝影機清潔",dockContactMaintenance:"充電接點清潔",remainingLife:"剩餘維護壽命",maintenanceUnavailable:"無資料",resetBlade:"更換刀片後重設",resetCamera:"清潔攝影機後重設",resetDockContact:"清潔接點後重設",resetCounterWarning:"僅在完成所示維護後確認。"},
  tr:{bladeMaintenance:"Bıçak bakımı",cameraMaintenance:"Kamera temizliği",dockContactMaintenance:"Şarj kontaklarını temizleme",remainingLife:"Kalan bakım ömrü",maintenanceUnavailable:"Veri yok",resetBlade:"Bıçak değişiminden sonra sıfırla",resetCamera:"Kamera temizliğinden sonra sıfırla",resetDockContact:"Kontak temizliğinden sonra sıfırla",resetCounterWarning:"Yalnızca belirtilen bakımdan sonra onaylayın."},
  th:{bladeMaintenance:"การบำรุงรักษาใบมีด",cameraMaintenance:"การทำความสะอาดกล้อง",dockContactMaintenance:"การทำความสะอาดหน้าสัมผัสชาร์จ",remainingLife:"อายุการบำรุงรักษาคงเหลือ",maintenanceUnavailable:"ไม่มีข้อมูล",resetBlade:"รีเซ็ตหลังเปลี่ยนใบมีด",resetCamera:"รีเซ็ตหลังทำความสะอาดกล้อง",resetDockContact:"รีเซ็ตหลังทำความสะอาดหน้าสัมผัส",resetCounterWarning:"ยืนยันหลังจากบำรุงรักษาตามที่ระบุแล้วเท่านั้น"},
  vi:{bladeMaintenance:"Bảo trì lưỡi cắt",cameraMaintenance:"Vệ sinh camera",dockContactMaintenance:"Vệ sinh tiếp điểm sạc",remainingLife:"Tuổi thọ bảo trì còn lại",maintenanceUnavailable:"Không có dữ liệu",resetBlade:"Đặt lại sau khi thay lưỡi",resetCamera:"Đặt lại sau khi vệ sinh camera",resetDockContact:"Đặt lại sau khi vệ sinh tiếp điểm",resetCounterWarning:"Chỉ xác nhận sau khi hoàn tất bảo trì được chỉ định."},
  ko:{bladeMaintenance:"날 유지보수",cameraMaintenance:"카메라 청소",dockContactMaintenance:"충전 접점 청소",remainingLife:"남은 유지보수 수명",maintenanceUnavailable:"데이터 없음",resetBlade:"날 교체 후 초기화",resetCamera:"카메라 청소 후 초기화",resetDockContact:"접점 청소 후 초기화",resetCounterWarning:"표시된 유지보수를 마친 후에만 확인하십시오."},
  km:{bladeMaintenance:"ថែទាំផ្លែឡាម",cameraMaintenance:"សម្អាតកាមេរ៉ា",dockContactMaintenance:"សម្អាតទំនាក់ទំនងសាក",remainingLife:"អាយុកាលថែទាំនៅសល់",maintenanceUnavailable:"គ្មានទិន្នន័យ",resetBlade:"កំណត់ឡើងវិញក្រោយប្តូរផ្លែឡាម",resetCamera:"កំណត់ឡើងវិញក្រោយសម្អាតកាមេរ៉ា",resetDockContact:"កំណត់ឡើងវិញក្រោយសម្អាតទំនាក់ទំនង",resetCounterWarning:"បញ្ជាក់តែក្រោយបញ្ចប់ការថែទាំដែលបានបង្ហាញ។"}
};
for (const [language, values] of Object.entries(beta10Translations)) {
  Object.assign(settingsTranslations[language] || (settingsTranslations[language] = {}), values);
}

const mowingPathFitTranslations = {
  en:"Mowing path calibration", hu:"Nyírási útvonal kalibráció", de:"Mähpfad-Kalibrierung", fr:"Étalonnage du parcours de tonte", es:"Calibración de la ruta de corte", it:"Calibrazione del percorso di taglio", pt:"Calibração do percurso de corte", nl:"Kalibratie van het maaipad", pl:"Kalibracja ścieżki koszenia", cs:"Kalibrace trasy sečení", sk:"Kalibrácia trasy kosenia", ro:"Calibrarea traseului de tundere", da:"Kalibrering af klipperute", sv:"Kalibrering av klippväg", no:"Kalibrering av klipperute", fi:"Leikkuureitin kalibrointi", "zh-CN":"修剪路径校准", "zh-TW":"修剪路徑校準", tr:"Biçme yolu kalibrasyonu", th:"การปรับเทียบเส้นทางตัดหญ้า", vi:"Hiệu chỉnh đường cắt", ko:"잔디 깎기 경로 보정", km:"ការក្រិតផ្លូវកាត់ស្មៅ"
};
for (const [language, value] of Object.entries(mowingPathFitTranslations)) {
  Object.assign(settingsTranslations[language] || (settingsTranslations[language] = {}), {mowingPathFit:value});
}

const cameraLifeTranslations = {
  en:"Camera life", hu:"Kamera élettartama", de:"Kamera-Lebensdauer", fr:"Durée de vie de la caméra", es:"Vida útil de la cámara", it:"Durata della fotocamera", pt:"Vida útil da câmara", nl:"Levensduur camera", pl:"Żywotność kamery", cs:"Životnost kamery", sk:"Životnosť kamery", ro:"Durata de viață a camerei", da:"Kameraets levetid", sv:"Kamerans livslängd", no:"Kameraets levetid", fi:"Kameran käyttöikä", "zh-CN":"摄像头寿命", "zh-TW":"攝影機壽命", tr:"Kamera ömrü", th:"อายุการใช้งานกล้อง", vi:"Tuổi thọ camera", ko:"카메라 수명", km:"អាយុកាលកាមេរ៉ា"
};
for (const [language, value] of Object.entries(cameraLifeTranslations)) {
  Object.assign(settingsTranslations[language] || (settingsTranslations[language] = {}), {cameraLife:value});
}

const zoneSelectionTranslations = {
  en:{selectedCount:"selected",mowingOrder:"Mowing order",moveUp:"Move up",moveDown:"Move down"}, hu:{selectedCount:"kijelölve",mowingOrder:"Nyírási sorrend",moveUp:"Mozgatás fel",moveDown:"Mozgatás le"}, de:{selectedCount:"ausgewählt",mowingOrder:"Mähreihenfolge",moveUp:"Nach oben",moveDown:"Nach unten"}, fr:{selectedCount:"sélectionnée(s)",mowingOrder:"Ordre de tonte",moveUp:"Monter",moveDown:"Descendre"}, es:{selectedCount:"seleccionadas",mowingOrder:"Orden de corte",moveUp:"Subir",moveDown:"Bajar"}, it:{selectedCount:"selezionate",mowingOrder:"Ordine di taglio",moveUp:"Sposta su",moveDown:"Sposta giù"}, pt:{selectedCount:"selecionadas",mowingOrder:"Ordem de corte",moveUp:"Mover para cima",moveDown:"Mover para baixo"}, nl:{selectedCount:"geselecteerd",mowingOrder:"Maaivolgorde",moveUp:"Omhoog",moveDown:"Omlaag"}, pl:{selectedCount:"wybrano",mowingOrder:"Kolejność koszenia",moveUp:"Przenieś w górę",moveDown:"Przenieś w dół"}, cs:{selectedCount:"vybráno",mowingOrder:"Pořadí sečení",moveUp:"Posunout nahoru",moveDown:"Posunout dolů"}, sk:{selectedCount:"vybrané",mowingOrder:"Poradie kosenia",moveUp:"Posunúť hore",moveDown:"Posunúť dole"}, ro:{selectedCount:"selectate",mowingOrder:"Ordinea tunderii",moveUp:"Mută în sus",moveDown:"Mută în jos"}, da:{selectedCount:"valgt",mowingOrder:"Klipningsrækkefølge",moveUp:"Flyt op",moveDown:"Flyt ned"}, sv:{selectedCount:"valda",mowingOrder:"Klippordning",moveUp:"Flytta upp",moveDown:"Flytta ner"}, no:{selectedCount:"valgt",mowingOrder:"Klippefølge",moveUp:"Flytt opp",moveDown:"Flytt ned"}, fi:{selectedCount:"valittu",mowingOrder:"Leikkuujärjestys",moveUp:"Siirrä ylös",moveDown:"Siirrä alas"}, "zh-CN":{selectedCount:"已选择",mowingOrder:"割草顺序",moveUp:"上移",moveDown:"下移"}, "zh-TW":{selectedCount:"已選擇",mowingOrder:"割草順序",moveUp:"上移",moveDown:"下移"}, tr:{selectedCount:"seçildi",mowingOrder:"Biçme sırası",moveUp:"Yukarı taşı",moveDown:"Aşağı taşı"}, th:{selectedCount:"เลือกแล้ว",mowingOrder:"ลำดับการตัด",moveUp:"เลื่อนขึ้น",moveDown:"เลื่อนลง"}, vi:{selectedCount:"đã chọn",mowingOrder:"Thứ tự cắt",moveUp:"Di chuyển lên",moveDown:"Di chuyển xuống"}, ko:{selectedCount:"선택됨",mowingOrder:"작업 순서",moveUp:"위로 이동",moveDown:"아래로 이동"}, km:{selectedCount:"បានជ្រើស",mowingOrder:"លំដាប់កាត់",moveUp:"ផ្លាស់ទីឡើង",moveDown:"ផ្លាស់ទីចុះ"}
};
for (const [language, values] of Object.entries(zoneSelectionTranslations)) {
  Object.assign(settingsTranslations[language] || (settingsTranslations[language] = {}), values);
}

export function normalizeLanguage(value) {
  const raw = String(value || "en").replace("_", "-");
  const lower = raw.toLowerCase();
  if (lower.startsWith("zh")) return /tw|hk|hant/.test(lower) ? "zh-TW" : "zh-CN";
  const short = lower.split("-")[0];
  if (short === "nb" || short === "nn") return "no";
  return translations[short] ? short : "en";
}

export function resolveLanguage(selection, hass) {
  if (selection && selection !== "auto") return normalizeLanguage(selection);
  return normalizeLanguage(hass?.locale?.language || hass?.language || navigator.language);
}

export function translate(language, key) {
  return translations[language]?.[key] ?? settingsTranslations[language]?.[key] ?? feedbackTranslations[language]?.[key] ?? commandStageTranslations[language]?.[key] ?? commandTranslations[language]?.[key] ?? menuTranslations[language]?.[key] ?? en[key] ?? settingsTranslations.en[key] ?? feedbackTranslations.en[key] ?? commandStageTranslations.en[key] ?? commandTranslations.en[key] ?? menuTranslations.en[key] ?? key;
}
