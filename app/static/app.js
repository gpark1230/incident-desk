// IncidentDesk frontend -- plain JS, no framework, no build step.
// Talks to the same FastAPI backend this page is served from (same-origin, no CORS needed).

let token = localStorage.getItem("token");
let currentUser = null;
let currentIncidentId = null;

// ---- API helper ----
// `form: true` sends body as application/x-www-form-urlencoded (needed for
// OAuth2PasswordRequestForm on /auth/login); everything else is JSON.
async function api(path, { method = "GET", body, form = false } = {}) {
  const headers = {};
  if (token) headers["Authorization"] = "Bearer " + token;
  if (body && !form) headers["Content-Type"] = "application/json";

  const res = await fetch(path, {
    method,
    headers,
    body: form ? body : body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const errBody = await res.json();
      if (errBody.detail) detail = errBody.detail;
    } catch (e) {
      /* response wasn't JSON -- keep statusText */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

const canWrite = () => currentUser && (currentUser.role === "analyst" || currentUser.role === "admin");

// ---- View switching ----
function showView(viewId) {
  ["login-view", "signup-view", "incidents-view", "detail-view"].forEach((id) => {
    document.getElementById(id).classList.toggle("hidden", id !== viewId);
  });
  document.getElementById("navbar").classList.toggle("hidden", viewId === "login-view" || viewId === "signup-view");
}

function setError(elId, message) {
  const el = document.getElementById(elId);
  if (!message) {
    el.classList.add("hidden");
    el.textContent = "";
  } else {
    el.textContent = message;
    el.classList.remove("hidden");
  }
}

// ---- Auth ----
async function login(email, password) {
  const body = new URLSearchParams({ username: email, password });
  const tokenResponse = await api("/auth/login", { method: "POST", body, form: true });
  token = tokenResponse.access_token;
  localStorage.setItem("token", token);
  currentUser = await api("/auth/me");
  renderNav();
  await loadIncidents();
  showView("incidents-view");
}

function logout() {
  token = null;
  currentUser = null;
  localStorage.removeItem("token");
  showView("login-view");
}

function renderNav() {
  document.getElementById("nav-email").textContent = currentUser.email;
  document.getElementById("nav-role").textContent = currentUser.role;
  document.getElementById("new-incident-btn").classList.toggle("hidden", !canWrite());
}

// ---- Incident list ----
async function loadIncidents() {
  const status = document.getElementById("filter-status").value;
  const severity = document.getElementById("filter-severity").value;
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (severity) params.set("severity", severity);

  const incidents = await api("/incidents?" + params.toString());
  const list = document.getElementById("incidents-list");
  list.innerHTML = "";

  if (incidents.length === 0) {
    list.innerHTML = '<div class="empty-state">No incidents match these filters.</div>';
    return;
  }

  for (const incident of incidents) {
    const card = document.createElement("div");
    card.className = "incident-card";
    card.innerHTML = `
      <div>
        <div class="title">${escapeHtml(incident.title)}</div>
        <div class="meta">#${incident.id} &middot; opened ${formatDate(incident.created_at)}</div>
      </div>
      <div class="badges">
        <span class="badge badge-severity-${incident.severity}">${incident.severity}</span>
        <span class="badge badge-status-${incident.status}">${incident.status}</span>
      </div>
    `;
    card.addEventListener("click", () => openIncident(incident.id));
    list.appendChild(card);
  }
}

// ---- Incident detail ----
async function openIncident(id) {
  currentIncidentId = id;
  const [incident, comments, auditLog] = await Promise.all([
    api(`/incidents/${id}`),
    api(`/incidents/${id}/comments`),
    api(`/incidents/${id}/audit-log`),
  ]);

  document.getElementById("detail-title").textContent = incident.title;
  document.getElementById("detail-description").textContent = incident.description || "No description provided.";
  document.getElementById("detail-meta").textContent =
    `#${incident.id} · created ${formatDate(incident.created_at)} · updated ${formatDate(incident.updated_at)}`;
  document.getElementById("detail-severity-badge").className = `badge badge-severity-${incident.severity}`;
  document.getElementById("detail-severity-badge").textContent = incident.severity;
  document.getElementById("detail-status-badge").className = `badge badge-status-${incident.status}`;
  document.getElementById("detail-status-badge").textContent = incident.status;

  const statusControl = document.getElementById("status-control");
  const commentForm = document.getElementById("comment-form");
  if (canWrite()) {
    statusControl.classList.remove("hidden");
    document.getElementById("status-select").value = incident.status;
    commentForm.classList.remove("hidden");
  } else {
    statusControl.classList.add("hidden");
    commentForm.classList.add("hidden");
  }

  renderComments(comments);
  renderAuditLog(auditLog);
  showView("detail-view");
}

function renderComments(comments) {
  const list = document.getElementById("comments-list");
  if (comments.length === 0) {
    list.innerHTML = '<div class="empty-state">No comments yet.</div>';
    return;
  }
  list.innerHTML = comments
    .map(
      (c) => `
      <div class="comment">
        <div class="comment-meta">User #${c.author_id} &middot; ${formatDate(c.created_at)}</div>
        <div class="comment-body">${escapeHtml(c.body)}</div>
      </div>`
    )
    .join("");
}

function renderAuditLog(entries) {
  const list = document.getElementById("audit-list");
  if (entries.length === 0) {
    list.innerHTML = '<div class="empty-state">No audit history yet.</div>';
    return;
  }
  list.innerHTML = entries
    .map(
      (e) => `
      <div class="audit-entry">
        <span class="audit-time">${formatDate(e.created_at)}</span>
        <span class="audit-action">${e.action}</span>
        <span>${escapeHtml(e.details || "")}</span>
      </div>`
    )
    .join("");
}

// ---- Helpers ----
function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---- Event wiring ----
document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setError("login-error", null);
  try {
    await login(document.getElementById("login-email").value, document.getElementById("login-password").value);
  } catch (err) {
    setError("login-error", err.message);
  }
});

document.getElementById("signup-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setError("signup-error", null);
  const email = document.getElementById("signup-email").value;
  const password = document.getElementById("signup-password").value;
  try {
    await api("/auth/signup", { method: "POST", body: { email, password } });
    await login(email, password);
  } catch (err) {
    setError("signup-error", err.message);
  }
});

document.getElementById("show-signup").addEventListener("click", () => showView("signup-view"));
document.getElementById("show-login").addEventListener("click", () => showView("login-view"));
document.getElementById("logout-btn").addEventListener("click", logout);
document.getElementById("back-to-list").addEventListener("click", (e) => {
  e.preventDefault();
  loadIncidents();
  showView("incidents-view");
});

document.getElementById("filter-status").addEventListener("change", loadIncidents);
document.getElementById("filter-severity").addEventListener("change", loadIncidents);

document.getElementById("new-incident-btn").addEventListener("click", () => {
  document.getElementById("create-form").reset();
  setError("create-error", null);
  document.getElementById("create-modal-backdrop").classList.remove("hidden");
});
document.getElementById("close-modal-btn").addEventListener("click", () => {
  document.getElementById("create-modal-backdrop").classList.add("hidden");
});

document.getElementById("create-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setError("create-error", null);
  const body = {
    title: document.getElementById("create-title").value,
    description: document.getElementById("create-description").value || null,
    severity: document.getElementById("create-severity").value,
  };
  try {
    await api("/incidents", { method: "POST", body });
    document.getElementById("create-modal-backdrop").classList.add("hidden");
    await loadIncidents();
  } catch (err) {
    setError("create-error", err.message);
  }
});

document.getElementById("status-save-btn").addEventListener("click", async () => {
  const status = document.getElementById("status-select").value;
  await api(`/incidents/${currentIncidentId}`, { method: "PATCH", body: { status } });
  await openIncident(currentIncidentId);
});

document.getElementById("comment-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = document.getElementById("comment-body").value;
  await api(`/incidents/${currentIncidentId}/comments`, { method: "POST", body: { body } });
  document.getElementById("comment-body").value = "";
  await openIncident(currentIncidentId);
});

// ---- Boot ----
(async function init() {
  if (!token) {
    showView("login-view");
    return;
  }
  try {
    currentUser = await api("/auth/me");
    renderNav();
    await loadIncidents();
    showView("incidents-view");
  } catch (err) {
    // stored token is invalid/expired
    logout();
  }
})();
