// web-ui/app.js
// Minimal demo UI to log in via Spotify and generate a Music Passport quickly.

const BASE = "http://127.0.0.1:8000"; // Backend base URL
document.getElementById("baseShow") && (document.getElementById("baseShow").textContent = BASE);

// Elements
const btnLogin = document.getElementById("btnLogin");
const btnLogout = document.getElementById("btnLogout");
const btnMe = document.getElementById("btnMe");
const meOut = document.getElementById("meOut");
const tokenEl = document.getElementById("token");

const limitEl = document.getElementById("limit");
const btnPlaylists = document.getElementById("btnPlaylists");
const playlistsEl = document.getElementById("playlists");

const btnPassTop = document.getElementById("btnPassTop");
const btnPassRecent = document.getElementById("btnPassRecent");
const passOut = document.getElementById("passOut");

const signedStatus = document.getElementById("signedStatus");

// ----------------------- helpers -----------------------

function setSignedIn(name) {
  if (signedStatus) {
    signedStatus.textContent = name ? `Signed in as ${name}` : "Signed out";
  }
}

function getHashParams() {
  // Parse fragment: #access_token=...&refresh_token=...&app_token=...&display_name=...&spotify_id=...
  const hash = window.location.hash.startsWith("#") ? window.location.hash.substring(1) : "";
  const params = new URLSearchParams(hash);
  return {
    access_token: params.get("access_token") || "",
    refresh_token: params.get("refresh_token") || "",
    app_token: params.get("app_token") || "",
    display_name: params.get("display_name") || "",
    spotify_id: params.get("spotify_id") || "",
  };
}

function saveTokens(t) {
  if (!t) return;
  if (t.access_token) localStorage.setItem("tuniverse_access_token", t.access_token);
  if (t.refresh_token) localStorage.setItem("tuniverse_refresh_token", t.refresh_token);
  if (t.app_token) localStorage.setItem("tuniverse_app_token", t.app_token);
  if (t.display_name) localStorage.setItem("tuniverse_display_name", t.display_name);
  if (t.spotify_id) localStorage.setItem("tuniverse_spotify_id", t.spotify_id);
}

function loadTokens() {
  return {
    access_token: localStorage.getItem("tuniverse_access_token") || "",
    refresh_token: localStorage.getItem("tuniverse_refresh_token") || "",
    app_token: localStorage.getItem("tuniverse_app_token") || "",
    display_name: localStorage.getItem("tuniverse_display_name") || "",
    spotify_id: localStorage.getItem("tuniverse_spotify_id") || "",
  };
}

function clearTokens() {
  ["tuniverse_access_token","tuniverse_refresh_token","tuniverse_app_token","tuniverse_display_name","tuniverse_spotify_id"]
    .forEach(k => localStorage.removeItem(k));
}

function enableBtns(hasToken) {
  if (btnMe) btnMe.disabled = !hasToken;
  if (btnPlaylists) btnPlaylists.disabled = !hasToken;
  if (btnPassTop) btnPassTop.disabled = !hasToken;
  if (btnPassRecent) btnPassRecent.disabled = !hasToken;
}

// Render helpers
function renderProfile(p) {
  const lines = [
    `ID: ${p.id || "(unknown)"}`,
    `Email: ${p.email || "(unknown)"}`,
    `Name: ${p.display_name || "(unknown)"}`,
    `Country: ${p.country || "(unknown)"}`,
    `Product: ${p.product || "(unknown)"}`
  ];
  meOut.textContent = lines.join("\n");
}

function renderPassport(data) {
  // data: { total_artists, country_counts, region_percentages, ... }
  if (!data || typeof data !== "object") {
    passOut.textContent = "Error: bad response";
    return;
  }
  const cc = data.country_counts || {};
  const rp = data.region_percentages || {};
  let out = `Total Artists: ${data.total_artists || 0}\n\nCountries:\n`;
  const ccKeys = Object.keys(cc);
  if (ccKeys.length === 0) out += "(none)\n";
  else ccKeys.forEach(k => out += `• ${k}: ${cc[k]}\n`);
  out += `\nRegions:\n`;
  const rpKeys = Object.keys(rp);
  if (rpKeys.length === 0) out += "(none)\n";
  else rpKeys.forEach(k => out += `• ${k}: ${Math.round(rp[k]*100)}%\n`);
  passOut.textContent = out;
}

// ----------------------- init from hash or cache -----------------------

(function bootstrap() {
  // 1) tokens from hash after /auth/callback
  const h = getHashParams();
  if (h.access_token) {
    saveTokens(h);
    // clear fragment for cleanliness
    history.replaceState(null, "", window.location.pathname);
  }

  // 2) populate UI from cache
  const t = loadTokens();
  if (tokenEl) tokenEl.value = t.access_token || "";
  enableBtns(!!t.access_token);
  setSignedIn(t.display_name || "");

  // If we already have a token, auto-load profile
  if (t.access_token && btnMe) {
    btnMe.click();
  }
})();

// ----------------------- actions -----------------------

if (btnLogin) {
  btnLogin.onclick = () => {
    // Server-side OAuth login; backend will redirect back with tokens in the hash
    window.location.href = `${BASE}/auth/login`;
  };
}
if (btnLogout) {
  btnLogout.onclick = () => {
    clearTokens();
    if (tokenEl) tokenEl.value = "";
    enableBtns(false);
    setSignedIn("");
    meOut.textContent = "";
    playlistsEl.innerHTML = "";
    passOut.textContent = "";
  };
}

if (btnMe) {
  btnMe.onclick = async () => {
    meOut.textContent = "Loading profile...";
    try {
      const at = (tokenEl?.value || "").trim();
      if (!at) throw new Error("No access token");
      const r = await fetch(`${BASE}/spotify/me?access_token=${encodeURIComponent(at)}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      renderProfile(data);
    } catch (e) {
      meOut.textContent = `Error: ${e.message || e}`;
    }
  };
}

if (btnPlaylists) {
  btnPlaylists.onclick = async () => {
    playlistsEl.innerHTML = "<li>Loading playlists...</li>";
    try {
      const at = (tokenEl?.value || "").trim();
      if (!at) throw new Error("No access token");
      const limit = Number(limitEl?.value || 5) || 5;
      const r = await fetch(`${BASE}/spotify/playlists?access_token=${encodeURIComponent(at)}&limit=${limit}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      const items = (data.items || []).map(p =>
        `<li><strong>${p.name}</strong> <small>(${(p.tracks && p.tracks.total) ?? "?"} tracks)</small></li>`
      ).join("");
      playlistsEl.innerHTML = items || "<li>No playlists</li>";
    } catch (e) {
      playlistsEl.innerHTML = `<li>Error: ${e.message || e}</li>`;
    }
  };
}

if (btnPassTop) {
  btnPassTop.onclick = async () => {
    passOut.textContent = "Generating...";
    try {
      const at = (tokenEl?.value || "").trim();
      if (!at) throw new Error("No access token");
      const r = await fetch(`${BASE}/passport/from_token?access_token=${encodeURIComponent(at)}&limit=8`);
      const data = await r.json();
      renderPassport(data);
    } catch (e) {
      passOut.textContent = `Error: ${e.message || e}`;
    }
  };
}

if (btnPassRecent) {
  btnPassRecent.onclick = async () => {
    passOut.textContent = "Generating...";
    try {
      const at = (tokenEl?.value || "").trim();
      if (!at) throw new Error("No access token");
      const r = await fetch(`${BASE}/passport/from_token_recent?access_token=${encodeURIComponent(at)}&limit=20`);
      const data = await r.json();
      renderPassport(data);
    } catch (e) {
      passOut.textContent = `Error: ${e.message || e}`;
    }
  };
}
