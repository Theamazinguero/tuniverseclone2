// ------- CONFIG -------
const BASE = "http://127.0.0.1:8000";  // change to "http://<LAN-IP>:8000" if testing from phone
document.getElementById("baseShow").textContent = BASE;

// ------- Elements -------
const tokenEl = document.getElementById("token");
const btnLogin = document.getElementById("btnLogin");
const btnMe = document.getElementById("btnMe");
const meOut = document.getElementById("meOut");

const limitEl = document.getElementById("limit");
const btnPlaylists = document.getElementById("btnPlaylists");
const playlistsEl = document.getElementById("playlists");

const userIdEl = document.getElementById("userId");
const btnPassport = document.getElementById("btnPassport");
const passOut = document.getElementById("passOut");

// NEW: token-based passport button
const btnPassportFromToken = document.getElementById("btnPassportFromToken");

// ------- Enable/disable buttons based on token -------
const syncButtons = () => {
  const hasToken = !!tokenEl.value.trim();
  btnMe.disabled = !hasToken;
  btnPlaylists.disabled = !hasToken;
  if (btnPassportFromToken) btnPassportFromToken.disabled = !hasToken;
};
tokenEl.addEventListener("input", syncButtons);
syncButtons();

// ------- Actions -------
btnLogin.onclick = () => {
  // open server-side OAuth login (browser redirect)
  window.location.href = `${BASE}/auth/login`;
};

btnMe.onclick = async () => {
  meOut.textContent = "Loading profile...";
  try {
    const at = tokenEl.value.trim();
    const r = await fetch(`${BASE}/spotify/me?access_token=${encodeURIComponent(at)}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const lines = [
      `ID: ${data.id}`,
      `Email: ${data.email}`,
      `Name: ${data.display_name}`,
      `Country: ${data.country}`,
      `Product: ${data.product}`
    ];
    meOut.textContent = lines.join("\n");
  } catch (e) {
    meOut.textContent = `Error: ${e.message || e}`;
  }
};

btnPlaylists.onclick = async () => {
  playlistsEl.innerHTML = "<li>Loading playlists...</li>";
  try {
    const at = tokenEl.value.trim();
    const limit = Number(limitEl.value) || 5;
    const r = await fetch(`${BASE}/spotify/playlists?access_token=${encodeURIComponent(at)}&limit=${limit}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const items = (data.items || [])
      .map(p => `<li><strong>${p.name}</strong> <small>(${p.tracks?.total ?? "?"} tracks)</small></li>`)
      .join("");
    playlistsEl.innerHTML = items || "<li>No playlists</li>";
  } catch (e) {
    playlistsEl.innerHTML = `<li>Error: ${e.message || e}</li>`;
  }
};

// ------- Music Passport (demo endpoint) -------
btnPassport.onclick = async () => {
  passOut.textContent = "Generating (demo endpoint)...";
  try {
    const uid = userIdEl.value.trim() || "demo_user";
    const r = await fetch(`${BASE}/demo_passport/${encodeURIComponent(uid)}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    renderPassport(data);
  } catch (e) {
    passOut.textContent = `Error: ${e.message || e}`;
  }
};

// ------- Music Passport (from Spotify token) -------
if (btnPassportFromToken) {
  btnPassportFromToken.onclick = async () => {
    passOut.textContent = "Generating from Spotify (this can take ~10–20s due to lookups)...";
    try {
      const at = tokenEl.value.trim();
      if (!at) throw new Error("Paste your access_token first (use Login with Spotify).");
      const r = await fetch(`${BASE}/passport/from_token?access_token=${encodeURIComponent(at)}&limit=12`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      renderPassport(data);
    } catch (e) {
      passOut.textContent = `Error: ${e.message || e}`;
    }
  };
}

// ------- Helper: render passport summary -------
function renderPassport(data) {
  const cc = data.country_counts || {};
  const rp = data.region_percentages || {};
  let out = `User: ${data.user_id ?? "N/A"}\nTotal Artists: ${data.total_artists ?? 0}\n\nCountries:\n`;
  Object.keys(cc).forEach(k => (out += `• ${k}: ${cc[k]}\n`));
  out += `\nRegions:\n`;
  Object.keys(rp).forEach(k => (out += `• ${k}: ${Math.round(rp[k] * 100)}%\n`));
  passOut.textContent = out;
}
