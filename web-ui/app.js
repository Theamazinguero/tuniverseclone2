// ------- CONFIG -------
const BASE = "http://127.0.0.1:8000";
document.getElementById("baseShow").textContent = BASE;

// ------- Elements -------
const tokenEl = document.getElementById("token");
const btnLogin = document.getElementById("btnLogin");
const btnLogout = document.getElementById("btnLogout");
const signedInAs = document.getElementById("signedInAs");

const btnMe = document.getElementById("btnMe");
const meOut = document.getElementById("meOut");

const limitEl = document.getElementById("limit");
const btnPlaylists = document.getElementById("btnPlaylists");
const playlistsEl = document.getElementById("playlists");

const btnPassportTop = document.getElementById("btnPassportTop");
const btnPassportRecent = document.getElementById("btnPassportRecent");
const passOut = document.getElementById("passOut");
const debugBox = document.getElementById("debugBox");

// ------- Helpers -------
function setStatus(msg, cls="") {
  debugBox.textContent = msg || "";
  debugBox.className = cls || "";
}

function enableIfToken() {
  const hasToken = !!tokenEl.value.trim();
  [btnMe, btnPlaylists, btnPassportTop, btnPassportRecent, btnLogout].forEach(b => b.disabled = !hasToken);
  signedInAs.textContent = hasToken ? (signedInAs.textContent || "Signed in") : "Not signed in";
}

function handleError(where, r) {
  return r.text().then(t => {
    const msg = `${where} -> HTTP ${r.status} ${t}`;
    setStatus(msg, "err");
    throw new Error(msg);
  });
}

function renderPassport(json) {
  const cc = json.country_counts || {};
  const rp = json.region_percentages || {};
  const lines = [];
  lines.push(`Total Artists: ${json.total_artists || 0}\n`);
  lines.push("Countries:");
  if (Object.keys(cc).length === 0) lines.push("(none)");
  else Object.keys(cc).forEach(k => lines.push(`• ${k}: ${cc[k]}`));
  lines.push("\nRegions:");
  if (Object.keys(rp).length === 0) lines.push("(none)");
  else Object.keys(rp).forEach(k => lines.push(`• ${k}: ${Math.round((rp[k] || 0) * 100)}%`));
  passOut.textContent = lines.join("\n");
}

// Reads tokens passed by /auth/callback as URL fragment
(function initFromHash() {
  const h = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
  if (!h) { enableIfToken(); return; }
  const params = {};
  h.split("&").forEach(kv => {
    const [k, v] = kv.split("=");
    if (k) params[decodeURIComponent(k)] = decodeURIComponent(v || "");
  });
  if (params.access_token) {
    tokenEl.value = params.access_token;
    signedInAs.textContent = params.display_name ? `Signed in as ${params.display_name}` : "Signed in";
    window.location.hash = ""; // clean URL
    setStatus("Token loaded from OAuth callback.", "ok");
  }
  enableIfToken();
})();

tokenEl.addEventListener("input", enableIfToken);

// ------- Actions -------
btnLogin.onclick = () => {
  setStatus("");
  window.location.href = `${BASE}/auth/login`;
};

btnLogout.onclick = () => {
  tokenEl.value = "";
  signedInAs.textContent = "Not signed in";
  meOut.textContent = "";
  playlistsEl.innerHTML = "";
  passOut.textContent = "";
  setStatus("Logged out.");
  enableIfToken();
};

btnMe.onclick = async () => {
  meOut.textContent = "Loading profile...";
  setStatus("");
  const at = tokenEl.value.trim();
  const r = await fetch(`${BASE}/spotify/me?access_token=${encodeURIComponent(at)}`);
  if (!r.ok) return handleError("GET /spotify/me", r);
  const data = await r.json();
  const lines = [
    `ID: ${data.id}`,
    `Email: ${data.email || "(unknown)"}`,
    `Name: ${data.display_name || "(unknown)"}`,
    `Country: ${data.country || "(unknown)"}`,
    `Product: ${data.product || "(unknown)"}`
  ];
  meOut.textContent = lines.join("\n");
};

btnPlaylists.onclick = async () => {
  playlistsEl.innerHTML = "<li>Loading playlists...</li>";
  setStatus("");
  const at = tokenEl.value.trim();
  const limit = Number(limitEl.value) || 5;
  const r = await fetch(`${BASE}/spotify/playlists?access_token=${encodeURIComponent(at)}&limit=${limit}`);
  if (!r.ok) {
    playlistsEl.innerHTML = "";
    return handleError("GET /spotify/playlists", r);
  }
  const data = await r.json();
  const items = (data.items || []).map(
    p => `<li><strong>${p.name}</strong> <small>(${p.tracks?.total ?? "?"} tracks)</small></li>`
  ).join("");
  playlistsEl.innerHTML = items || "<li>No playlists</li>";
};

btnPassportTop.onclick = async () => {
  passOut.textContent = "Building passport from Top Artists…";
  setStatus("");
  const at = tokenEl.value.trim();
  const r = await fetch(`${BASE}/passport/from_token?access_token=${encodeURIComponent(at)}&limit=10`);
  if (!r.ok) return handleError("GET /passport/from_token", r);
  const data = await r.json();
  if (!data || (data.total_artists || 0) === 0) {
    setStatus("Top artists returned 0. Try the Recently Played fallback after playing a couple tracks.", "warn");
  }
  renderPassport(data);
};

btnPassportRecent.onclick = async () => {
  passOut.textContent = "Building passport from Recently Played…";
  setStatus("");
  const at = tokenEl.value.trim();
  const r = await fetch(`${BASE}/passport/from_recent?access_token=${encodeURIComponent(at)}&limit=20`);
  if (!r.ok) return handleError("GET /passport/from_recent", r);
  const data = await r.json();
  if (!data || (data.total_artists || 0) === 0) {
    setStatus("No recent plays found. Play a couple tracks, then try again.", "warn");
  }
  renderPassport(data);
};
