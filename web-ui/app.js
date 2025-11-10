// web-ui/app.js

// --------- CONFIG ---------
const BASE = "http://127.0.0.1:8000";
document.getElementById("baseShow").textContent = BASE;

// --------- Elements ---------
const whoami = document.getElementById("whoami");
const tokenEl = document.getElementById("token");

const btnLogin = document.getElementById("btnLogin");
const btnLogout = document.getElementById("btnLogout");

const btnMe = document.getElementById("btnMe");
const meOut = document.getElementById("meOut");

const limitEl = document.getElementById("limit");
const btnPlaylists = document.getElementById("btnPlaylists");
const playlistsEl = document.getElementById("playlists");

const btnPassportTop = document.getElementById("btnPassportTop");
const btnPassportRecent = document.getElementById("btnPassportRecent");
const passOut = document.getElementById("passOut");

// --------- Token management ---------
function setToken(tok) {
  if (!tok) return;
  tokenEl.value = tok;
  localStorage.setItem("tuniverse_access_token", tok);
  syncButtons();
}

function getToken() {
  return tokenEl.value.trim() || localStorage.getItem("tuniverse_access_token") || "";
}

function clearToken() {
  tokenEl.value = "";
  localStorage.removeItem("tuniverse_access_token");
  syncButtons();
}

// Parse tokens passed back from /auth/callback as URL hash
(function parseHash() {
  if (!location.hash) return;
  const h = new URLSearchParams(location.hash.slice(1));
  const accessToken = h.get("access_token");
  const displayName = h.get("display_name");
  const spotifyId = h.get("spotify_id");

  if (accessToken) {
    setToken(accessToken);
    whoami.hidden = false;
    whoami.textContent = `Signed in${displayName ? " as " + displayName : ""}`;
  }

  // Clean the URL (remove hash)
  history.replaceState(null, "", location.pathname);
})();

// Restore saved token on load
(function restoreToken() {
  const t = localStorage.getItem("tuniverse_access_token");
  if (t) {
    tokenEl.value = t;
    whoami.hidden = false;
    whoami.textContent = "Signed in";
  }
  syncButtons();
})();

tokenEl.addEventListener("input", syncButtons);

function syncButtons() {
  const hasToken = !!getToken();
  btnMe.disabled = !hasToken;
  btnPlaylists.disabled = !hasToken;
  btnPassportTop.disabled = !hasToken;
  btnPassportRecent.disabled = !hasToken;
}

// --------- Actions ---------
btnLogin.onclick = () => {
  window.location.href = `${BASE}/auth/login`;
};

btnLogout.onclick = () => {
  clearToken();
  whoami.hidden = true;
  meOut.textContent = "";
  playlistsEl.innerHTML = "";
  passOut.textContent = "";
};

btnMe.onclick = async () => {
  meOut.textContent = "Loading profile...";
  try {
    const at = getToken();
    const r = await fetch(`${BASE}/spotify/me?access_token=${encodeURIComponent(at)}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const lines = [
      `ID: ${data.id ?? "(unknown)"}`,
      `Email: ${data.email ?? "(unknown)"}`,
      `Name: ${data.display_name ?? "(unknown)"}`,
      `Country: ${data.country ?? "(unknown)"}`,
      `Product: ${data.product ?? "(unknown)"}`
    ];
    meOut.textContent = lines.join("\n");
  } catch (e) {
    meOut.textContent = `Error: ${e.message || e}`;
  }
};

btnPlaylists.onclick = async () => {
  playlistsEl.innerHTML = "<li>Loading playlists...</li>";
  try {
    const at = getToken();
    const limit = Number(limitEl.value) || 5;
    const r = await fetch(`${BASE}/spotify/playlists?access_token=${encodeURIComponent(at)}&limit=${limit}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const items = (data.items || []).map(p => {
      const name = p?.name ?? "(unnamed)";
      const total = p?.tracks?.total ?? "?";
      return `<li><strong>${name}</strong> <small>(${total} tracks)</small></li>`;
    }).join("");
    playlistsEl.innerHTML = items || "<li>No playlists</li>";
  } catch (e) {
    playlistsEl.innerHTML = `<li class="err">Error: ${e.message || e}</li>`;
  }
};

btnPassportTop.onclick = async () => {
  passOut.textContent = "Generating from Top Artists...";
  try {
    const at = getToken();
    const r = await fetch(`${BASE}/passport/from_token?access_token=${encodeURIComponent(at)}&limit=12`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    renderPassport(data);
  } catch (e) {
    passOut.textContent = `Error: ${e.message || e}`;
  }
};

btnPassportRecent.onclick = async () => {
  passOut.textContent = "Generating from Recently Played...";
  try {
    const at = getToken();
    const r = await fetch(`${BASE}/passport/from_recent?access_token=${encodeURIComponent(at)}&limit=50`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    renderPassport(data);
  } catch (e) {
    passOut.textContent = `Error: ${e.message || e}`;
  }
};

function renderPassport(data) {
  const cc = data.country_counts || {};
  const rp = data.region_percentages || {};
  let out = `Total Artists: ${data.total_artists}\n\nCountries:\n`;
  Object.keys(cc).forEach(k => out += `• ${k}: ${cc[k]}\n`);
  out += `\nRegions:\n`;
  Object.keys(rp).forEach(k => out += `• ${k}: ${Math.round((rp[k] || 0) * 100)}%\n`);
  passOut.textContent = out;
}

