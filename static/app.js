/* Maidenhead Grid Tools — static frontend.
 *
 * All conversions run locally through window.Maidenhead (grid.js).
 * Address lookup calls the public Nominatim API directly from the browser,
 * throttled to one request per second and cached in localStorage for 24 hours.
 */
const $ = (id) => document.getElementById(id);

const GEOCODE_ENDPOINT = "https://nominatim.openstreetmap.org/search";
const GEOCODE_CACHE_PREFIX = "maidenhead.geocode.v1:";
const GEOCODE_TTL_MS = 24 * 60 * 60 * 1000;
const GEOCODE_MIN_INTERVAL_MS = 1000;
const GEOCODE_TIMEOUT_MS = 10000;

let lastGeocodeAt = 0;
const inFlight = new Map();

function scheduleThrottle() {
  const wait = GEOCODE_MIN_INTERVAL_MS - (Date.now() - lastGeocodeAt);
  if (wait <= 0) return Promise.resolve();
  return new Promise((resolve) => setTimeout(resolve, wait));
}

const map = L.map("map", { worldCopyJump: true }).setView([20, 0], 2);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

let marker = null;

function setMarker(lat, lon, zoom = 8) {
  if (marker) {
    marker.setLatLng([lat, lon]);
  } else {
    marker = L.marker([lat, lon]).addTo(map);
  }
  map.setView([lat, lon], zoom);
}

function showResult({ grid, lat, lon, address }) {
  if (grid !== undefined) $("result-grid").textContent = grid;
  if (lat !== undefined) $("result-lat").textContent = Number(lat).toFixed(6);
  if (lon !== undefined) $("result-lon").textContent = Number(lon).toFixed(6);
  if (address !== undefined) $("result-address").textContent = address;
}

function fillInputs({ grid, lat, lon }) {
  if (grid !== undefined) $("grid").value = grid;
  if (lat !== undefined) $("lat").value = lat;
  if (lon !== undefined) $("lon").value = lon;
}

function readCache(key) {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const entry = JSON.parse(raw);
    if (!entry || typeof entry.ts !== "number" || !entry.value) return null;
    if (Date.now() - entry.ts > GEOCODE_TTL_MS) {
      window.localStorage.removeItem(key);
      return null;
    }
    return entry.value;
  } catch (error) {
    return null;
  }
}

function writeCache(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify({ ts: Date.now(), value }));
  } catch (error) {
    /* private mode / quota — caching is best effort */
  }
}

async function geocode(query) {
  const q = String(query).trim();
  if (!q) throw new Error("address is required");
  if (q.length > 200) throw new Error("address must be 200 characters or fewer");

  const key = GEOCODE_CACHE_PREFIX + q.toLowerCase();
  const cached = readCache(key);
  if (cached) return cached;
  if (inFlight.has(key)) return inFlight.get(key);

  const doFetch = async () => {
    await scheduleThrottle();
    lastGeocodeAt = Date.now();

    const params = new URLSearchParams({ format: "jsonv2", limit: "1", q });
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), GEOCODE_TIMEOUT_MS);

    try {
      const response = await fetch(`${GEOCODE_ENDPOINT}?${params.toString()}`, {
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`geocoder request failed (HTTP ${response.status})`);
      }
      const data = await response.json();
      if (!Array.isArray(data) || data.length === 0) {
        throw new Error("address not found");
      }
      const item = data[0];
      const lat = Number(item.lat);
      const lon = Number(item.lon);
      if (
        !Number.isFinite(lat) ||
        !Number.isFinite(lon) ||
        lat < -90 ||
        lat > 90 ||
        lon < -180 ||
        lon > 180
      ) {
        throw new Error("geocoder returned invalid coordinates");
      }
      const value = {
        lat,
        lon,
        display_name: String(item.display_name || ""),
      };
      writeCache(key, value);
      return value;
    } finally {
      clearTimeout(timeoutId);
      inFlight.delete(key);
    }
  };

  const promise = doFetch();
  inFlight.set(key, promise);
  return promise;
}

function convertLatLon(lat, lon) {
  const data = window.Maidenhead.latLonToGrid(lat, lon, 6);
  showResult({ grid: data, lat, lon, address: "—" });
  setMarker(Number(lat), Number(lon));
  fillInputs({ grid: data, lat, lon });
  return data;
}

function convertGrid(grid) {
  const normalized = window.Maidenhead.normalizeGrid(grid);
  const center = window.Maidenhead.gridToLatLon(normalized);
  showResult({ grid: normalized, lat: center.lat, lon: center.lon, address: "—" });
  setMarker(center.lat, center.lon);
  fillInputs({ grid: normalized, lat: center.lat, lon: center.lon });
  return normalized;
}

$("address-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("status").textContent = "Looking up address…";
  try {
    const place = await geocode($("address").value);
    convertLatLon(place.lat, place.lon);
    showResult({ address: place.display_name });
    setMarker(place.lat, place.lon, 12);
    $("status").textContent = "";
  } catch (error) {
    $("status").textContent = error.message;
  }
});

$("latlon-form").addEventListener("submit", (event) => {
  event.preventDefault();
  try {
    convertLatLon($("lat").value, $("lon").value);
    $("status").textContent = "";
  } catch (error) {
    $("status").textContent = error.message;
  }
});

$("grid-form").addEventListener("submit", (event) => {
  event.preventDefault();
  try {
    convertGrid($("grid").value);
    $("status").textContent = "";
  } catch (error) {
    $("status").textContent = error.message;
  }
});

map.on("click", (event) => {
  try {
    const lat = event.latlng.lat.toFixed(6);
    const lon = event.latlng.wrap().lng.toFixed(6);
    convertLatLon(lat, lon);
    $("status").textContent = "";
  } catch (error) {
    $("status").textContent = error.message;
  }
});

function clearLocalCache() {
  try {
    const keys = [];
    for (let i = 0; i < window.localStorage.length; i++) {
      const k = window.localStorage.key(i);
      if (k && k.startsWith(GEOCODE_CACHE_PREFIX)) keys.push(k);
    }
    keys.forEach((k) => window.localStorage.removeItem(k));
  } catch (error) {
    /* best effort */
  }
  $("status").textContent = "Local search cache cleared.";
}

const clearCacheButton = $("clear-cache");
if (clearCacheButton) {
  clearCacheButton.addEventListener("click", clearLocalCache);
}

window.__maidenheadReady = true;
