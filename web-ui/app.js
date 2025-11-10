// ------- CONFIG -------
const BASE = "http://127.0.0.1:8000";
document.getElementById("baseShow").textContent = BASE;

// ------- Elements -------
const authStatus = document.getElementById("authStatus");
const btnLogin = document.getElementById("btnLogin");
const btnLogout = document.getElementById("btnLogout");

const meOut = document.getElementById("meOut");

const limitEl = document.getElementById("limit");
const btnPlaylists = document.getElementById("btnPlaylists");
const playlistsEl = document.getElementById("playlists");

const btnPassport = document.getElementById("btnPassport");
const btnRecent = document.getElementById("btnRecent");
const passOut = document.getElementById("passOut");

// ------- Token storage -------
const TOKENS_KEY = "tuniverse_tokens";
function saveTokens(obj){ localStorage.setItem(TOKENS_KEY, JSON.stringify(obj||{})); }
function loadTokens(){ try { return JSON.parse(localStorage.getItem(TOKENS_KEY)||"{}"); } catch { return {}; } }
function clearTokens(){ localStorage.removeItem(TOKENS_KEY); }
function getAccessToken(){ return (loadTokens().access_token||"").trim(); }

// Parse callback hash and store tokens
function parseHashForTokens() {
  if (!location.hash || location.hash.length < 2) return null;
  const qs = new URLSearchParams(location.hash.substring(1));
  const access_token = qs.get("access_token") || "";
  const refresh_token = qs.get("refresh_token") || "";
  const app_token = qs.get("app_token") || "";
  const display_name = qs.get("display_name") || "";
  const spotify_id = qs.get("spotify_id") || "";
  if (access_token) {
    saveTokens({ access_token, refresh_token, app_token, display_name, spotify_id });
    history.replaceState(null, "", location.pathname);
    return { access_token, refresh_token, app_token, display_name, spotify_id };
  }
  return null;
}

// ------- UI actions -------
btnLogin.onclick = () => { window.location.href = `${BASE}/auth/login`; };
btnLogout.onclick = () => {
  clearTokens();
  authStatus.textContent = "Signed out.";
  meOut.textContent = "Sign in to load…";
  playlistsEl.innerHTML = "";
  passOut.textContent = "";
};

btnPlaylists.onclick = async () => {
  const at = getAccessToken();
  if (!at) return alert("Sign in first.");
  playlistsEl.innerHTML = "<li>Loading playlists...</li>";
  try {
    const limit = Number(limitEl.value) || 5;
    const r = await fetch(`${BASE}/spotify/playlists?access_token=${encodeURIComponent(at)}&limit=${limit}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const items = (data.items || []).map(p =>
      `<li><strong>${p.name}</strong> <small>(${p.tracks?.total ?? "?"} tracks)</small></li>`
    ).join("");
    playlistsEl.innerHTML = items || "<li>No playlists</li>";
  } catch (e) {
    playlistsEl.innerHTML = `<li>Error: ${e.message || e}</li>`;
  }
};

btnPassport.onclick = async () => {
  const at = getAccessToken();
  if (!at) return alert("Sign in first.");
  passOut.textContent = "Building passport (Top Artists)...";
  try {
    const r = await fetch(`${BASE}/passport/from_token?access_token=${encodeURIComponent(at)}&limit=12`);
    const data = await r.json();
    if (!r.ok) throw new Error(JSON.stringify(data));
    renderPassport(data);
  } catch (e) {
    passOut.textContent = `Error: ${e.message || e}`;
  }
};

btnRecent.onclick = async () => {
  const at = getAccessToken();
  if (!at) return alert("Sign in first.");
  passOut.textContent = "Building passport (Recently Played)...";
  try {
    const r = await fetch(`${BASE}/passport/from_recent?access_token=${encodeURIComponent(at)}&limit=20`);
    const data = await r.json();
    if (!r.ok) throw new Error(JSON.stringify(data));
    renderPassport(data);
  } catch (e) {
    passOut.textContent = `Error: ${e.message || e}`;
  }
};

function renderPassport(data) {
  const cc = data.country_counts || {};
  const rp = data.region_percentages || {};
  let out = `Total Artists: ${data.total_artists || 0}\n\nCountries:\n`;
  Object.keys(cc).forEach(k => out += `• ${k}: ${cc[k]}\n`);
  out += `\nRegions:\n`;
  Object.keys(rp).forEach(k => out += `• ${k}: ${Math.round((rp[k] || 0) * 100)}%\n`);
  passOut.textContent = out;
}

// ------- Auto init -------
(async function init() {
  parseHashForTokens(); // grab tokens if redirected
  const tokens = loadTokens();
  const at = getAccessToken();

  if (at) {
    authStatus.textContent = `Signed in as ${tokens.display_name || tokens.spotify_id || "Spotify User"}`;
    try {
      meOut.textContent = "Loading profile...";
      const r = await fetch(`${BASE}/spotify/me?access_token=${encodeURIComponent(at)}`);
      const me = await r.json();
      if (!r.ok) throw new Error(JSON.stringify(me));
      meOut.textContent = [
        `ID: ${me.id}`,
        `Email: ${me.email || "(not shared)"}`,
        `Name: ${me.display_name}`,
        `Country: ${me.country || "(unknown)"}`,
        `Product: ${me.product || "(unknown)"}`
      ].join("\n");
    } catch (e) {
      meOut.textContent = `Error: ${e.message || e}`;
    }
    // Auto-build a passport (Top Artists) on load
    btnPassport.click();
  } else {
    authStatus.textContent = "Not signed in.";
  }
})();



