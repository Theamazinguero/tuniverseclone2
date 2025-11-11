// ------- CONFIG -------
const BASE = "http://127.0.0.1:8000"; // backend
document.getElementById("baseShow").textContent = BASE;

// ------- Elements -------
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
const signedInAs = document.getElementById("signedInAs");

// ------- Helpers -------
function logOut(textArea, err) {
  textArea.textContent = `Error: ${err?.message || err}`;
  console.error(err);
}

function uiSync() {
  const hasToken = !!tokenEl.value.trim();
  btnMe.disabled = !hasToken;
  btnPlaylists.disabled = !hasToken;
  btnPassportTop.disabled = !hasToken;
  btnPassportRecent.disabled = !hasToken;
  btnLogout.disabled = !hasToken;

  // signed-in label
  signedInAs.textContent = hasToken ? "Signed in" : "Not signed in";
}

// Read params from URL hash after /auth/callback redirect: #access_token=...&refresh_token=...
(function initFromHash() {
  const h = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
  if (!h) return;
  const params = {};
  h.split("&").forEach(kv => {
    const [k, v] = kv.split("=");
    if (k) params[decodeURIComponent(k)] = decodeURIComponent(v || "");
  });
  if (params.access_token) {
    tokenEl.value = params.access_token;
    // show who signed in (if provided)
    if (params.display_name) signedInAs.textContent = `Signed in as ${params.display_name}`;
    // clean URL
    window.location.hash = "";
  }
})();

tokenEl.addEventListener("input", uiSync);
uiSync();

// ------- Actions -------
btnLogin.onclick = () => {
  window.location.href = `${BASE}/auth/login`;
};

btnLogout.onclick = () => {
  tokenEl.value = "";
  uiSync();
  meOut.textContent = "";
  playlistsEl.innerHTML = "";
  passOut.textContent = "";
  signedInAs.textContent = "Not signed in";
};

btnMe.onclick = async () => {
  meOut.textContent = "Loading profile...";
  try {
    const at = tokenEl.value.trim();
    const r = await fetch(`${BASE}/spotify/me?access_token=${encodeURIComponent(at)}`);
    if (!r.ok) throw new Error(`HTTP ${r.status} ${await r.text()}`);
    const data = await r.json();
    const lines = [
      `ID: ${data.id}`,
      `Email: ${data.email || "(unknown)"}`,
      `Name: ${data.display_name || "(unknown)"}`,
      `Country: ${data.country || "(unknown)"}`,
      `Product: ${data.product || "(unknown)"}`,
    ];
    meOut.textContent = lines.join("\n");
  } catch (e) {
    logOut(meOut, e);
  }
};

btnPlaylists.onclick = async () => {
  playlistsEl.innerHTML = "<li>Loading playlists...</li>";
  try {
    const at = tokenEl.value.trim();
    const limit = Number(limitEl.value) || 5;
    const r = await fetch(`${BASE}/spotify/playlists?access_token=${encodeURIComponent(at)}&limit=${limit}`);
    if (!r.ok) throw new Error(`HTTP ${r.status} ${await r.text()}`);
    const data = await r.json();
    const items = (data.items || []).map(
      p => `<li><strong>${p.name}</strong> <small>(${p.tracks?.total ?? "?"} tracks)</small></li>`
    ).join("");
    playlistsEl.innerHTML = items || "<li>No playlists</li>";
  } catch (e) {
    playlistsEl.innerHTML = `<li>Error: ${e.message || e}</li>`;
    console.error(e);
  }
};

// Render a passport JSON into the <pre>
function renderPassport(json, target) {
  const cc = json.country_counts || {};
  const rp = json.region_percentages || {};
  const lines = [];
  lines.push(`Total Artists: ${json.total_artists || 0}\n`);
  lines.push("Countries:");
  if (Object.keys(cc).length === 0) {
    lines.push("(none)");
  } else {
    Object.keys(cc).forEach(k => lines.push(`• ${k}: ${cc[k]}`));
  }
  lines.push("\nRegions:");
  if (Object.keys(rp).length === 0) {
    lines.push("(none)");
  } else {
    Object.keys(rp).forEach(k => lines.push(`• ${k}: ${Math.round((rp[k] || 0) * 100)}%`));
  }
  target.textContent = lines.join("\n");
}

// Build passport from Top Artists
btnPassportTop.onclick = async () => {
  passOut.textContent = "Building passport from Top Artists…";
  try {
    const at = tokenEl.value.trim();
    const url = `${BASE}/passport/from_token?access_token=${encodeURIComponent(at)}&limit=10`;
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status} ${await r.text()}`);
    const data = await r.json();

    // If backend returns empty (some users don’t have top artists yet), tell the user
    if (!data || (data.total_artists || 0) === 0) {
      passOut.textContent = "No top artists available yet. Try the 'Recently Played' fallback after playing a couple of tracks.";
      return;
    }
    renderPassport(data, passOut);
  } catch (e) {
    logOut(passOut, e);
  }
};

// Build passport from Recently Played (fallback)
btnPassportRecent.onclick = async () => {
  passOut.textContent = "Building passport from Recently Played…";
  try {
    const at = tokenEl.value.trim();
    const url = `${BASE}/passport/from_recent?access_token=${encodeURIComponent(at)}&limit=20`;
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status} ${await r.text()}`);
    const data = await r.json();

    if (!data || (data.total_artists || 0) === 0) {
      passOut.textContent = "No recent plays found. Open Spotify, play a couple of tracks, and try again.";
      return;
    }
    renderPassport(data, passOut);
  } catch (e) {
    logOut(passOut, e);
  }
};
