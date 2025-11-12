// -------- CONFIG --------
const BASE = "http://127.0.0.1:8000";
const baseShowEl = document.getElementById("baseShow");
if (baseShowEl) baseShowEl.textContent = BASE;

// -------- El refs --------
const signedAs   = document.getElementById("signedAs");
const tokenEl    = document.getElementById("token");
const btnLogin   = document.getElementById("btnLogin");
const btnLogout  = document.getElementById("btnLogout");

const btnMe      = document.getElementById("btnMe");
const meOut      = document.getElementById("meOut");

const limitEl    = document.getElementById("limit");
const btnPlay    = document.getElementById("btnPlaylists");
const listEl     = document.getElementById("playlists");

const btnPassTop = document.getElementById("btnPassportTop");
const btnPassRec = document.getElementById("btnPassportRecent");
const passOut    = document.getElementById("passOut");

// -------- Token helpers --------
function readHashParams() {
  const h = (window.location.hash || "").replace(/^#/, "");
  const out = {};
  if (!h) return out;
  h.split("&").forEach(kv => {
    const [k, v] = kv.split("=");
    if (k) out[decodeURIComponent(k)] = decodeURIComponent(v || "");
  });
  return out;
}

function loadTokens() {
  const hash = readHashParams();
  if (hash.access_token) {
    localStorage.setItem("spotify_access_token", hash.access_token);
    localStorage.setItem("spotify_refresh_token", hash.refresh_token || "");
    localStorage.setItem("app_token", hash.app_token || "");
    localStorage.setItem("display_name", hash.display_name || "");
    localStorage.setItem("spotify_id", hash.spotify_id || "");
    // Clean the URL
    history.replaceState({}, document.title, window.location.pathname);
  }

  const at = localStorage.getItem("spotify_access_token") || "";
  tokenEl.value = at;
  const name = localStorage.getItem("display_name") || "";
  signedAs.textContent = at ? `Signed in as ${name || "Spotify user"}` : "Not signed in";
  signedAs.className = "pill " + (at ? "ok" : "err");
}

function requireToken() {
  const at = tokenEl.value.trim();
  if (!at) throw new Error("No access token. Click 'Login with Spotify' first.");
  return at;
}

// -------- Actions --------
btnLogin.onclick = () => {
  window.location.href = `${BASE}/auth/login`;
};

btnLogout.onclick = () => {
  localStorage.removeItem("spotify_access_token");
  localStorage.removeItem("spotify_refresh_token");
  localStorage.removeItem("app_token");
  localStorage.removeItem("display_name");
  localStorage.removeItem("spotify_id");
  tokenEl.value = "";
  signedAs.textContent = "Not signed in";
  signedAs.className = "pill err";
  meOut.textContent = "";
  listEl.innerHTML = "";
  passOut.textContent = "";
};

btnMe.onclick = async () => {
  meOut.textContent = "Loading profile…";
  try {
    const at = requireToken();
    const r = await fetch(`${BASE}/spotify/me?access_token=${encodeURIComponent(at)}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const lines = [
      `ID: ${data.id}`,
      `Email: ${data.email || "(unknown)"}`,
      `Name: ${data.display_name || "(unknown)"}`,
      `Country: ${data.country || "(unknown)"}`,
      `Product: ${data.product || "(unknown)"}`
    ];
    meOut.textContent = lines.join("\n");
  } catch (e) {
    meOut.textContent = `Error: ${e.message || e}`;
  }
};

btnPlay.onclick = async () => {
  listEl.innerHTML = "<li>Loading…</li>";
  try {
    const at = requireToken();
    const limit = Number(limitEl.value) || 5;
    const r = await fetch(`${BASE}/spotify/playlists?access_token=${encodeURIComponent(at)}&limit=${limit}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const items = (data.items || []).map(p =>
      `<li><strong>${p.name}</strong> <small>(${p.tracks?.total ?? "?"} tracks)</small></li>`
    ).join("");
    listEl.innerHTML = items || "<li>No playlists</li>";
  } catch (e) {
    listEl.innerHTML = `<li class="err">Error: ${e.message || e}</li>`;
  }
};

async function buildPassport(path) {
  passOut.textContent = "Generating passport…";
  try {
    const at = requireToken();
    const r = await fetch(`${BASE}${path}?access_token=${encodeURIComponent(at)}`);
    if (!r.ok) {
      const txt = await r.text();
      throw new Error(`HTTP ${r.status}: ${txt}`);
    }
    const data = await r.json();

    const cc = data.country_counts || {};
    const rp = data.region_percentages || {};
    const total = data.total_artists ?? 0;

    if (!Object.keys(cc).length && total === 0) {
      passOut.textContent = "No country data available yet for your account.";
      return;
    }

    let out = `Total Artists: ${total}\n\nCountries:\n`;
    Object.keys(cc).sort().forEach(k => out += `• ${k}: ${cc[k]}\n`);
    out += `\nRegions:\n`;
    Object.keys(rp).forEach(k => out += `• ${k}: ${Math.round((rp[k] || 0) * 100)}%\n`);
    passOut.textContent = out;
  } catch (e) {
    passOut.textContent = `Error: ${e.message || e}`;
  }
}

// IMPORTANT: Must match backend routes exactly
btnPassTop.onclick  = () => buildPassport(`/passport/from_token`);
btnPassRec.onclick  = () => buildPassport(`/passport/from_recent`);

// Init
loadTokens();


