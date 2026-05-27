const state = {
  variablesDraft: [],
  lastExtractionId: null,
  lastDocumentId: null,
  lastResult: [],
  lastConfigId: null,
  lastDocumentName: null,
  configsById: {},
  editingConfigId: null,
  editingVariableIndex: null,
  previewVariableIndex: 0,
  responseFormatMode: "standard",
  currentUser: null,
  selectedBuId: null,
  businessUnits: [],
  refreshInFlight: null,
  documentHighlightTerm: null,
  usersAdminByUserId: {},
  confirmModalResolver: null,
};

// Map view names ↔ URL paths. "run" lives at "/" to keep the root clean.
const VIEW_PATHS = {
  run: "/",
  documents: "/docs",
  collections: "/batches",
  configs: "/settings",
  assessments: "/evals",
  history: "/history",
  audit: "/audit",
  users: "/users",
};
const PATH_TO_VIEW = Object.fromEntries(
  Object.entries(VIEW_PATHS).map(([v, p]) => [p, v])
);

const STORAGE_KEYS = {
  currentUser: "centinell.currentUser",
  selectedBuId: "centinell.selectedBuId",
  sidebarCollapsed: "centinell.sidebarCollapsed",
  theme: "centinell.theme",
};

function applyTheme(dark) {
  document.body.classList.toggle("dark", dark);
  const moon = el("themeIconMoon");
  const sun  = el("themeIconSun");
  const btn  = el("themeToggleBtn");
  if (!moon || !sun || !btn) return;
  moon.style.display = dark ? "none"  : "";
  sun.style.display  = dark ? ""      : "none";
  btn.title      = dark ? "Modo diurno"   : "Modo nocturno";
  btn.setAttribute("aria-label", btn.title);
}

function initTheme() {
  const saved = localStorage.getItem(STORAGE_KEYS.theme);
  const prefersDark = saved ? saved === "dark"
    : window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(prefersDark);
}

function toggleTheme() {
  const isDark = !document.body.classList.contains("dark");
  applyTheme(isDark);
  localStorage.setItem(STORAGE_KEYS.theme, isDark ? "dark" : "light");
}

const defaultPrompt = [
  "Eres Centinell, un sistema de extracción de información de documentos.",
  "Extrae exclusivamente los campos indicados.",
  "No anadas explicaciones ni texto adicional.",
  "",
  "CAMPOS A EXTRAER:",
  "{{VARIABLE_BLOCK}}",
  "",
  "REGLAS:",
  "- Si un campo no existe, responde null.",
  "- No inventes valores.",
  "- Incluye reasoning breve por campo; si no hay evidencia, usa null.",
  "",
  "FORMATO:",
  "[{\"title\": \"NombreVariable\", \"answer\": \"valor\", \"reasoning\": \"evidencia breve\"}]"
].join("\n");

const strictResponseFormat = '[{"title": "NombreVariable", "answer": "valor", "reasoning": "evidencia breve"}]';

const defaultResponseFormat = strictResponseFormat;

function el(id) {
  return document.getElementById(id);
}

function loadSessionFromStorage() {
  const rawUser = localStorage.getItem(STORAGE_KEYS.currentUser);
  state.currentUser = rawUser ? JSON.parse(rawUser) : null;
  state.selectedBuId = localStorage.getItem(STORAGE_KEYS.selectedBuId);
  state.sidebarCollapsed = localStorage.getItem(STORAGE_KEYS.sidebarCollapsed) === "1";
}

function persistSession() {
  if (state.currentUser) {
    localStorage.setItem(STORAGE_KEYS.currentUser, JSON.stringify(state.currentUser));
  } else {
    localStorage.removeItem(STORAGE_KEYS.currentUser);
  }

  if (state.selectedBuId) {
    localStorage.setItem(STORAGE_KEYS.selectedBuId, state.selectedBuId);
  } else {
    localStorage.removeItem(STORAGE_KEYS.selectedBuId);
  }

  if (state.sidebarCollapsed) {
    localStorage.setItem(STORAGE_KEYS.sidebarCollapsed, "1");
  } else {
    localStorage.removeItem(STORAGE_KEYS.sidebarCollapsed);
  }
}

function applySidebarState() {
  document.body.classList.toggle("sidebar-collapsed", Boolean(state.sidebarCollapsed));
  const toggleBtn = el("sidebarToggleBtn");
  if (toggleBtn) {
    toggleBtn.setAttribute("aria-label", state.sidebarCollapsed ? "Expandir menu" : "Contraer menu");
    toggleBtn.setAttribute("title", state.sidebarCollapsed ? "Expandir menu" : "Contraer menu");
  }
}

function toggleSidebar() {
  state.sidebarCollapsed = !state.sidebarCollapsed;
  persistSession();
  applySidebarState();
}

function hasSession() {
  return Boolean(state.currentUser);
}

function canManagePromptConfigs() {
  const role = state.currentUser?.role;
  return role === "admin_global" || role === "bu_admin";
}

function canViewAudit() {
  return state.currentUser?.role === "admin_global";
}

function canManageUsers() {
  return state.currentUser?.role === "admin_global";
}

function canManageApiKeys() {
  const role = state.currentUser?.role;
  return role === "admin_global" || role === "bu_admin";
}

/**
 * Devuelve true si el usuario puede lanzar/ver extracciones y evaluaciones.
 * bu_user y bu_viewer NO pueden: solo admin_global y bu_admin tienen acceso.
 */
function canRunExtractions() {
  const role = state.currentUser?.role;
  return role === "admin_global" || role === "bu_admin";
}

function isViewerRole() {
  return state.currentUser?.role === "bu_viewer";
}

function applyRoleBasedUi() {
  const configsNavBtn = document.querySelector('.nav-btn[data-view="configs"]');
  const configsView = el("view-configs");
  const auditNavBtn = document.querySelector('.nav-btn[data-view="audit"]');
  const auditView = el("view-audit");
  const usersNavBtn = document.querySelector('.nav-btn[data-view="users"]');
  const usersView = el("view-users");
  const canManage = canManagePromptConfigs();
  const canAudit = canViewAudit();
  const canUsers = canManageUsers();

  if (configsNavBtn) {
    configsNavBtn.style.display = canManage ? "" : "none";
  }
  if (configsView) {
    configsView.style.display = canManage ? "" : "none";
  }
  if (auditNavBtn) {
    auditNavBtn.style.display = canAudit ? "" : "none";
  }
  if (auditView) {
    auditView.style.display = canAudit ? "" : "none";
  }
  if (usersNavBtn) {
    usersNavBtn.style.display = canUsers ? "" : "none";
  }
  if (usersView) {
    usersView.style.display = canUsers ? "" : "none";
  }

  if (!canManage) {
    const activeConfigsBtn = document.querySelector('.nav-btn.active[data-view="configs"]');
    const activeConfigsView = document.querySelector("#view-configs.active");
    if (activeConfigsBtn || activeConfigsView) {
      activateView("run", "replace");
    }
  }

  if (!canAudit) {
    const activeAuditBtn = document.querySelector('.nav-btn.active[data-view="audit"]');
    const activeAuditView = document.querySelector("#view-audit.active");
    if (activeAuditBtn || activeAuditView) {
      activateView("run", "replace");
    }
  }

  if (!canUsers) {
    const activeUsersBtn = document.querySelector('.nav-btn.active[data-view="users"]');
    const activeUsersView = document.querySelector("#view-users.active");
    if (activeUsersBtn || activeUsersView) {
      activateView("run", "replace");
    }
  }

  const viewer = isViewerRole();
  [
    "runExtractionBtn",
    "saveValidationBtn",
    "parseFileBtn",
    "createConfigBtn",
    "updateConfigBtn",
    "addVariableBtn",
    "updateVariableBtn",
    "cancelVariableEditBtn",
    "colProcessBtn",
    "colClearBtn",
  ].forEach((id) => {
    const node = el(id);
    if (node) {
      node.disabled = viewer;
    }
  });

  const documentInput = el("documentText");
  if (documentInput) {
    documentInput.readOnly = viewer;
  }
  const uploadInput = el("documentFile");
  if (uploadInput) {
    uploadInput.disabled = viewer;
  }

  const colFileInput = el("colFileInput");
  if (colFileInput) {
    colFileInput.disabled = viewer;
  }
  const colUploadArea = el("colUploadArea");
  if (colUploadArea) {
    colUploadArea.classList.toggle("is-disabled", viewer);
    colUploadArea.setAttribute("aria-disabled", viewer ? "true" : "false");
  }
  const apikeysNavBtn = document.querySelector('.nav-btn[data-view="apikeys"]');
  const apikeysView = el("view-apikeys");
  const canApiKeys = canManageApiKeys();
  if (apikeysNavBtn) apikeysNavBtn.style.display = canApiKeys ? "" : "none";
  if (apikeysView) apikeysView.style.display = canApiKeys ? "" : "none";
  if (!canApiKeys) {
    const activeApiKeysBtn = document.querySelector('.nav-btn.active[data-view="apikeys"]');
    const activeApiKeysView = document.querySelector("#view-apikeys.active");
    if (activeApiKeysBtn || activeApiKeysView) activateView("run", "replace");
  }

  updateCopyToBuVisibility();

  // ─── bu_user: sin Nueva Extracción, Evaluaciones ni Historial ─────────────
  const canExtract = canRunExtractions();
  ["run", "assessments", "history"].forEach((viewName) => {
    const navBtn = document.querySelector(`.nav-btn[data-view="${viewName}"]`);
    const viewEl = el(`view-${viewName}`);
    if (navBtn) navBtn.style.display = canExtract ? "" : "none";
    if (viewEl) viewEl.style.display = canExtract ? "" : "none";
  });

  // Si la vista activa es una de las restringidas, redirigir a Documentos
  if (!canExtract) {
    const activeView = document.querySelector(".view.active");
    if (activeView) {
      const activeName = activeView.id.replace("view-", "");
      if (["run", "assessments", "history"].includes(activeName)) {
        activateView("documents", "replace");
      }
    }
  }

  // Columna Acciones de la tabla de documentos
  const actionsHeader = el("docsActionsHeader");
  if (actionsHeader) actionsHeader.style.display = canExtract ? "" : "none";
}

function renderUsersAdminTable() {
  const body = el("usersAdminTableBody");
  if (!body) return;
  body.innerHTML = "";

  const buUsers = Object.values(state.usersAdminByUserId).filter((u) => !u.is_global_admin);

  if (!buUsers.length) {
    body.innerHTML = '<tr><td colspan="4" class="empty-row">No hay usuarios asignados a esta BU.</td></tr>';
    return;
  }

  buUsers.forEach((access) => {
    const tr = document.createElement("tr");

    tr.innerHTML = `
      <td>${access.full_name || "-"}</td>
      <td>${access.email}</td>
      <td>
        <select data-user-role="${access.user_id}" class="users-role-select">
          <option value="bu_admin" ${access.role === "bu_admin" ? "selected" : ""}>bu_admin</option>
          <option value="bu_user" ${access.role === "bu_user" ? "selected" : ""}>bu_user</option>
          <option value="bu_viewer" ${access.role === "bu_viewer" ? "selected" : ""}>bu_viewer</option>
        </select>
      </td>
      <td>
        <div class="users-actions">
          <button type="button" class="secondary" data-assign-user="${access.user_id}">Actualizar rol</button>
          <button type="button" class="danger" data-remove-user="${access.user_id}">Borrar de BU</button>
        </div>
      </td>
    `;
    body.appendChild(tr);
  });

  body.querySelectorAll("button[data-assign-user]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const userId = btn.dataset.assignUser;
      const roleNode = body.querySelector(`select[data-user-role="${userId}"]`);
      const role = roleNode?.value || "bu_user";
      await assignUserAccess(userId, role);
    });
  });

  body.querySelectorAll("button[data-remove-user]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const userId = btn.dataset.removeUser;
      await removeUserAccess(userId);
    });
  });
}

async function loadUsersAdminData() {
  if (!canManageUsers()) {
    setMessage("usersAdminMessage", "No tienes permisos para administrar usuarios", "error");
    return;
  }

  if (!hasSession() || !state.selectedBuId) {
    setMessage("usersAdminMessage", "Haz login y seleccióna una BU", "error");
    return;
  }

  setMessage("usersAdminMessage", "Cargando usuarios...", "loading");
  try {
    const buUsers = await api(`/bus/${state.selectedBuId}/users`);

    state.usersAdminByUserId = {};
    (Array.isArray(buUsers) ? buUsers : []).forEach((access) => {
      state.usersAdminByUserId[access.user_id] = access;
    });

    renderUsersAdminTable();
    const count = Object.keys(state.usersAdminByUserId).length;
    setMessage("usersAdminMessage", `${count} usuario(s) en esta BU`, "success");
  } catch (error) {
    setMessage("usersAdminMessage", `Error cargando usuarios: ${error.message}`, "error");
    const body = el("usersAdminTableBody");
    if (body) {
      body.innerHTML = `<tr><td colspan="4" class="empty-row">Error: ${error.message}</td></tr>`;
    }
  }
}

async function assignUserAccess(userId, role) {
  if (!canManageUsers()) {
    setMessage("usersAdminMessage", "No tienes permisos para administrar usuarios", "error");
    return;
  }

  if (!state.selectedBuId) {
    setMessage("usersAdminMessage", "Seleccióna una BU", "error");
    return;
  }

  try {
    setMessage("usersAdminMessage", "Guardando acceso de usuario...", "loading");
    await api(`/bus/${state.selectedBuId}/users`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId, role }),
    });
    await loadUsersAdminData();
    setMessage("usersAdminMessage", "Acceso actualizado", "success");
  } catch (error) {
    setMessage("usersAdminMessage", `Error actualizando acceso: ${error.message}`, "error");
  }
}

async function removeUserAccess(userId) {
  if (!canManageUsers()) {
    setMessage("usersAdminMessage", "No tienes permisos para administrar usuarios", "error");
    return;
  }

  if (!state.selectedBuId) {
    setMessage("usersAdminMessage", "Seleccióna una BU", "error");
    return;
  }

  const confirmed = await openConfirmModal({
    title: "Borrar acceso de usuario",
    message: "Este usuario perdera acceso a la BU actual. ¿Quieres continuar?",
    acceptLabel: "Borrar de BU",
    cancelLabel: "Cancelar",
  });
  if (!confirmed) {
    setMessage("usersAdminMessage", "Operacion cancelada", "idle");
    return;
  }

  try {
    setMessage("usersAdminMessage", "Borrando acceso del usuario en esta BU...", "loading");
    await api(`/bus/${state.selectedBuId}/users/${userId}`, {
      method: "DELETE",
    });
    await loadUsersAdminData();
    setMessage("usersAdminMessage", "Usuario borrado de la BU", "success");
  } catch (error) {
    setMessage("usersAdminMessage", `Error removiendo acceso: ${error.message}`, "error");
  }
}

async function createUserInCurrentBu() {
  if (!canManageUsers()) {
    setMessage("usersAdminMessage", "No tienes permisos para administrar usuarios", "error");
    return;
  }

  if (!state.selectedBuId) {
    setMessage("usersAdminMessage", "Seleccióna una BU", "error");
    return;
  }

  const email = (el("usersCreateEmail")?.value || "").trim().toLowerCase();
  const fullName = (el("usersCreateFullName")?.value || "").trim();
  const password = el("usersCreatePassword")?.value || "";
  const role = (el("usersCreateRole")?.value || "bu_user").trim();

  if (!email || !email.includes("@")) {
    setMessage("usersAdminMessage", "Email invalido", "error");
    return;
  }
  if (!password || password.length < 10) {
    setMessage("usersAdminMessage", "Password debe tener al menos 10 caracteres", "error");
    return;
  }

  setMessage("usersAdminMessage", "Creando usuario y asignando a BU...", "loading");

  let userId = null;
  let userCreated = false;
  try {
    const created = await api("/admin/users", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        full_name: fullName || null,
        is_global_admin: false,
      }),
    });
    userId = created.id;
    userCreated = true;
  } catch (error) {
    if (!String(error.message).includes("Ya existe un usuario con ese email")) {
      setMessage("usersAdminMessage", `Error creando usuario: ${error.message}`, "error");
      return;
    }

    try {
      const users = await api("/admin/users");
      const existing = (Array.isArray(users) ? users : []).find((u) => String(u.email || "").toLowerCase() === email);
      if (!existing) {
        setMessage("usersAdminMessage", "El usuario ya existe, pero no se pudo resolver su ID", "error");
        return;
      }
      if (existing.is_global_admin) {
        setMessage("usersAdminMessage", "No se puede asignar un admin_global a una BU", "error");
        return;
      }
      userId = existing.id;
    } catch (resolveError) {
      setMessage("usersAdminMessage", `Error buscando usuario existente: ${resolveError.message}`, "error");
      return;
    }
  }

  try {
    await api(`/bus/${state.selectedBuId}/users`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId, role }),
    });

    el("usersCreateEmail").value = "";
    el("usersCreateFullName").value = "";
    el("usersCreatePassword").value = "";
    el("usersCreateRole").value = "bu_user";

    await loadUsersAdminData();
    setMessage(
      "usersAdminMessage",
      userCreated ? "Usuario creado y asignado a la BU" : "Usuario existente asignado/actualizado en la BU",
      "success"
    );
  } catch (error) {
    setMessage("usersAdminMessage", `Error asignando usuario a BU: ${error.message}`, "error");
  }
}

// ══════════════ API KEYS ══════════════

async function loadApiKeys() {
  if (!canManageApiKeys()) return;
  if (!state.selectedBuId) {
    renderApiKeysTable([]);
    return;
  }
  try {
    const keys = await api("/api-keys/");
    renderApiKeysTable(Array.isArray(keys) ? keys : []);
  } catch (err) {
    setMessage("apikeysMessage", `Error cargando API keys: ${err.message}`, "error");
  }
}

function renderApiKeysTable(keys) {
  const body = el("apikeysTableBody");
  if (!body) return;
  if (!keys.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty-row">No hay API keys activas.</td></tr>';
    return;
  }
  body.innerHTML = keys.map((k) => `
    <tr>
      <td>${escapeHtml(k.name)}</td>
      <td><code>${escapeHtml(k.key_prefix)}...</code></td>
      <td>${escapeHtml(k.role)}</td>
      <td>${new Date(k.created_at).toLocaleDateString("es-ES")}</td>
      <td>${k.last_used_at ? new Date(k.last_used_at).toLocaleString("es-ES") : "Nunca"}</td>
      <td>
        <button class="secondary apikey-revoke-btn" data-id="${k.id}" data-name="${escapeHtml(k.name)}" type="button">Revocar</button>
      </td>
    </tr>
  `).join("");

  body.querySelectorAll(".apikey-revoke-btn").forEach((btn) => {
    btn.addEventListener("click", () => revokeApiKey(btn.dataset.id, btn.dataset.name));
  });
}

async function createApiKey() {
  if (!canManageApiKeys()) return;
  if (!state.selectedBuId) {
    setMessage("apikeysMessage", "Seleccióna una BU primero", "error");
    return;
  }
  const name = (el("apikeyName")?.value || "").trim();
  const role = el("apikeyRole")?.value || "bu_user";
  if (!name) {
    setMessage("apikeysMessage", "Ingresa un nombre para la clave", "error");
    return;
  }

  setMessage("apikeysMessage", "Generando clave...", "loading");
  el("apikeyNewKeyBox").style.display = "none";

  try {
    const result = await api("/api-keys/", {
      method: "POST",
      body: JSON.stringify({ name, role }),
    });

    el("apikeyName").value = "";
    const keyBox = el("apikeyNewKeyBox");
    const keyValue = el("apikeyNewKeyValue");
    if (keyBox && keyValue) {
      keyValue.textContent = result.key;
      keyBox.style.display = "";
    }

    setMessage("apikeysMessage", "Clave generada. Copiala ahora.", "success");
    await loadApiKeys();
  } catch (err) {
    setMessage("apikeysMessage", `Error: ${err.message}`, "error");
  }
}

async function revokeApiKey(keyId, keyName) {
  const confirmed = await openConfirmModal({ title: "Revocar API Key", message: `¿Revocar la clave "${keyName}"? Esta accion no se puede deshacer.`, acceptLabel: "Revocar" });
  if (!confirmed) return;
  try {
    await api(`/api-keys/${keyId}`, { method: "DELETE" });
    setMessage("apikeysMessage", "Clave revocada", "success");
    await loadApiKeys();
  } catch (err) {
    setMessage("apikeysMessage", `Error: ${err.message}`, "error");
  }
}

function copyApiKeyToClipboard() {
  const val = el("apikeyNewKeyValue")?.textContent || "";
  if (!val) return;
  navigator.clipboard.writeText(val).then(() => {
    const btn = el("apikeyNewKeyCopyBtn");
    if (btn) { btn.textContent = "Copiado"; setTimeout(() => { btn.textContent = "Copiar"; }, 2000); }
  }).catch(() => {
    setMessage("apikeysMessage", "No se pudo copiar al portapapeles", "error");
  });
}

function renderAuditEvents(events) {
  const body = el("auditTableBody");
  if (!body) return;
  body.innerHTML = "";

  if (!Array.isArray(events) || !events.length) {
    body.innerHTML = '<tr><td colspan="7" class="empty-row">No hay eventos para esos filtros.</td></tr>';
    return;
  }

  events.forEach((evt) => {
    const tr = document.createElement("tr");
    const createdAt = evt.created_at ? new Date(evt.created_at).toLocaleString("es-ES") : "-";
    const details = evt.details ? JSON.stringify(evt.details) : "-";
    tr.innerHTML = `
      <td>${createdAt}</td>
      <td>${evt.event_type || "-"}</td>
      <td>${evt.actor_user_id || "-"}</td>
      <td>${evt.bu_id || "-"}</td>
      <td>${evt.resource_type || "-"}${evt.resource_id ? ` (${evt.resource_id})` : ""}</td>
      <td>${evt.message || "-"}</td>
      <td class="audit-details-cell">${details}</td>
    `;
    body.appendChild(tr);
  });
}

async function loadAuditEvents() {
  if (!canViewAudit()) {
    setMessage("auditMessage", "No tienes permisos para ver auditoria", "error");
    return;
  }

  const params = new URLSearchParams();
  const eventType = (el("auditEventType")?.value || "").trim();
  const actorUserId = (el("auditActorUserId")?.value || "").trim();
  const buId = (el("auditBuId")?.value || "").trim();
  const skip = (el("auditSkip")?.value || "0").trim();
  const limit = (el("auditLimit")?.value || "50").trim();

  if (eventType) params.set("event_type", eventType);
  if (actorUserId) params.set("actor_user_id", actorUserId);
  if (buId) params.set("bu_id", buId);
  params.set("skip", skip || "0");
  params.set("limit", limit || "50");

  setMessage("auditMessage", "Cargando auditoria...", "loading");
  try {
    const events = await api(`/admin/audit-events?${params.toString()}`);
    renderAuditEvents(events);
    setMessage("auditMessage", `${events.length} evento(s) cargado(s)`, "success");
  } catch (error) {
    setMessage("auditMessage", `Error cargando auditoria: ${error.message}`, "error");
    const body = el("auditTableBody");
    if (body) {
      body.innerHTML = `<tr><td colspan="7" class="empty-row">Error: ${error.message}</td></tr>`;
    }
  }
}

function setAuthMessage(text = "") {
  const node = el("authMessage");
  if (!node) return;
  node.textContent = text;
}

function setAuthAlert(visible, text = "") {
  const alert = el("authAlert");
  const alertText = el("authAlertText");
  if (!alert || !alertText) return;
  alert.classList.toggle("is-visible", visible);
  alertText.textContent = visible ? text : "";
}

function closeConfirmModal(result) {
  const modal = el("confirmModal");
  if (!modal) {
    return;
  }

  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");

  if (typeof state.confirmModalResolver === "function") {
    state.confirmModalResolver(Boolean(result));
    state.confirmModalResolver = null;
  }
}

function openConfirmModal({ title, message, acceptLabel = "Confirmar", cancelLabel = "Cancelar" }) {
  const modal = el("confirmModal");
  const titleNode = el("confirmModalTitle");
  const messageNode = el("confirmModalMessage");
  const acceptBtn = el("confirmModalAcceptBtn");
  const cancelBtn = el("confirmModalCancelBtn");

  if (!modal || !titleNode || !messageNode || !acceptBtn || !cancelBtn) {
    return Promise.resolve(window.confirm(message || "¿Seguro que quieres continuar?"));
  }

  titleNode.textContent = title || "Confirmar accion";
  messageNode.textContent = message || "¿Seguro que quieres continuar?";
  acceptBtn.textContent = acceptLabel;
  cancelBtn.textContent = cancelLabel;

  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");

  return new Promise((resolve) => {
    state.confirmModalResolver = resolve;
    cancelBtn.focus();
  });
}

function updateAuthUi({ preserveAuthMessage = false } = {}) {
  const authGate = el("authGate");
  const appShell = el("appShell");
  const authUserBox = el("authUserBox");
  const authUserLabel = el("authUserLabel");
  const buSelect = el("buSelect");

  if (hasSession()) {
    authGate.style.display = "none";
    appShell.style.display = "flex";
    authUserBox.style.display = "flex";
    const email = state.currentUser?.email || "usuario";
    authUserLabel.textContent = email;
  } else {
    authGate.style.display = "grid";
    appShell.style.display = "none";
    authUserBox.style.display = "none";
    if (!preserveAuthMessage) {
      setAuthMessage("");
      setAuthAlert(false);
    }
  }

  buSelect.disabled = !hasSession() || !state.businessUnits.length;
  applyRoleBasedUi();
}

function clearSessionForPendingAssignment(message) {
  state.currentUser = null;
  state.selectedBuId = null;
  state.businessUnits = [];
  persistSession();
  renderBuOptions();
  updateAuthUi({ preserveAuthMessage: true });
  setAuthMessage(message);
}

function renderBuOptions() {
  const buSelect = el("buSelect");
  buSelect.innerHTML = "";

  if (!state.businessUnits.length) {
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = hasSession() ? "Sin BUs disponibles" : "Haz login para cargar BUs";
    buSelect.appendChild(empty);
    buSelect.disabled = true;
    return;
  }

  state.businessUnits.forEach((bu) => {
    const option = document.createElement("option");
    option.value = bu.id;
    option.textContent = `${bu.name} (${bu.code})`;
    buSelect.appendChild(option);
  });

  const selected = state.businessUnits.find((bu) => bu.id === state.selectedBuId);
  if (selected) {
    buSelect.value = selected.id;
  } else {
    state.selectedBuId = state.businessUnits[0].id;
    buSelect.value = state.selectedBuId;
  }

  buSelect.disabled = false;
  persistSession();
}

async function loadBusinessUnits() {
  if (!hasSession()) {
    state.businessUnits = [];
    renderBuOptions();
    updateAuthUi();
    return { pendingAssignment: false };
  }

  try {
    const isGlobalAdmin = state.currentUser?.role === "admin_global";
    const units = await api(isGlobalAdmin ? "/bus/" : "/bus/my-access");
    state.businessUnits = Array.isArray(units) ? units : [];

    if (!state.businessUnits.length) {
      if (isGlobalAdmin) {
        await createDefaultAdminBu();
        const refreshed = await api("/bus/");
        state.businessUnits = Array.isArray(refreshed) ? refreshed : [];
      } else {
        renderBuOptions();
        updateAuthUi();
        return { pendingAssignment: true };
      }
    }

    renderBuOptions();
    updateAuthUi();
    return { pendingAssignment: false };
  } catch (error) {
    if (String(error.message).includes("401")) {
      logout();
    }
    state.businessUnits = [];
    renderBuOptions();
    if (hasSession()) {
      setMessage("runMessage", `No se pudieron cargar BUs: ${error.message}`, "error");
    } else {
      setAuthMessage(`No se pudieron cargar BUs: ${error.message}`);
    }
    return { pendingAssignment: false };
  }
}

async function createDefaultAdminBu() {
  try {
    const now = new Date();
    const suffix = `${now.getHours()}${now.getMinutes()}${now.getSeconds()}`;
    await api("/bus/", {
      method: "POST",
      body: JSON.stringify({
        name: "Admin",
        code: `ADMIN_${suffix}`,
      }),
    });
    setMessage("runMessage", "BU inicial creada: Admin", "success");
  } catch (error) {
    if (!String(error.message).includes("409")) {
      throw error;
    }
  }
}

async function login(event) {
  event.preventDefault();

  const email = el("loginEmail").value.trim();
  const password = el("loginPassword").value;
  if (!email || !password) {
    setAuthMessage("Introduce email y password");
    return;
  }

  try {
    setAuthMessage("Validando acceso...");
    const result = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    state.currentUser = result.user || null;
    persistSession();
    updateAuthUi();
    const buLoadState = await loadBusinessUnits();
    if (buLoadState?.pendingAssignment) {
      clearSessionForPendingAssignment("");
      return;
    }

    await loadConfigs();
    await loadColConfigs();

    setAuthAlert(false);
    setAuthMessage("");
    setMessage("runMessage", "", "idle");
    await loadHistory();
  } catch (error) {
    if (String(error.message).includes("Sin unidad de negocio asignada")) {
      setAuthAlert(true, error.message);
      return;
    }
    setAuthAlert(false);
    setAuthMessage(`Error: ${error.message}`);
  }
}

async function logout() {
  try {
    await fetch("/auth/logout", { method: "POST", credentials: "include" });
  } catch (_) {
    // server-side cookie clear best-effort
  }
  state.currentUser = null;
  state.selectedBuId = null;
  state.businessUnits = [];
  persistSession();
  renderBuOptions();
  updateAuthUi();
  setAuthAlert(false);
  el("loginPassword").value = "";
  setMessage("runMessage", "Sesion cerrada", "success");
}

function ensureSessionAndBu() {
  if (!hasSession()) {
    throw new Error("Haz login primero");
  }
  if (!state.selectedBuId) {
    throw new Error("Seleccióna una BU activa");
  }
}

function setMessage(id, text, variant = "idle") {
  const node = el(id);
  node.textContent = text;
  node.classList.remove("is-idle", "is-loading", "is-success", "is-error");
  node.classList.add(`is-${variant}`);
}

function setApiStatus(variant, text) {
  const node = el("apiStatus");
  if (!node) {
    return;
  }
  node.textContent = text;
  node.classList.remove("is-loading", "is-online", "is-offline");
  node.classList.add(`is-${variant}`);
}

function composeBasePrompt(baseInstructions, responseFormat) {
  const base = (baseInstructions || "").trim();
  const response = (responseFormat || "").trim();
  if (!response) {
    return base;
  }

  return `${base}\n\nFORMATO DE RESPUESTA:\n${response}`;
}

function getEffectiveResponseFormat() {
  if (state.responseFormatMode === "standard") {
    return strictResponseFormat;
  }

  const custom = el("cfgResponseFormat").value || "";
  return custom.trim() || strictResponseFormat;
}

function válidateResponseFormatJson(showMessage = false) {
  if (state.responseFormatMode !== "custom") {
    return true;
  }

  const raw = (el("cfgResponseFormat").value || "").trim();
  if (!raw) {
    if (showMessage) {
      setMessage("configMessage", "En modo Custom, Response format no puede estar vacio", "error");
    }
    return false;
  }

  try {
    JSON.parse(raw);
    return true;
  } catch (_) {
    if (showMessage) {
      setMessage("configMessage", "Response format Custom debe ser JSON valido", "error");
    }
    return false;
  }
}

function setResponseFormatMode(mode) {
  const select = el("cfgResponseFormatMode");
  const textarea = el("cfgResponseFormat");

  state.responseFormatMode = mode === "custom" ? "custom" : "standard";
  if (select) {
    select.value = state.responseFormatMode;
  }

  if (state.responseFormatMode === "standard") {
    textarea.value = strictResponseFormat;
    textarea.readOnly = true;
  } else {
    if (!textarea.value.trim()) {
      textarea.value = strictResponseFormat;
    }
    textarea.readOnly = false;
  }
}

function syncResponseFormatModeFromText(responseFormatText) {
  const text = (responseFormatText || "").trim();
  const isStrict = text === strictResponseFormat.trim();
  setResponseFormatMode(isStrict ? "standard" : "custom");
  el("cfgResponseFormat").value = text || strictResponseFormat;
}

function getVariablePlaceholderToken(prompt) {
  const matches = (prompt || "").match(/\{\{\s*[^{}]+\s*\}\}/g) || [];
  const unique = [...new Set(matches)];

  if (!unique.length) {
    return null;
  }

  if (unique.length > 1) {
    return "__MULTIPLE__";
  }

  return unique[0];
}

function splitPromptSections(fullPrompt) {
  const text = fullPrompt || "";
  const markerRegex = /\n\nFORMATO DE RESPUESTA:\n/i;
  const match = markerRegex.exec(text);

  if (!match) {
    return {
      baseInstructions: text,
      responseFormat: defaultResponseFormat,
    };
  }

  const markerIndex = match.index;
  const markerLength = match[0].length;

  return {
    baseInstructions: text.slice(0, markerIndex).trim(),
    responseFormat: text.slice(markerIndex + markerLength).trim(),
  };
}

function buildVariableBlock(variables) {
  if (!Array.isArray(variables) || !variables.length) {
    return "{{AUN_SIN_VARIABLES}}";
  }

  return variables
    .map((v) => {
      const requiredText = v.required === false ? "(opcional)" : "(obligatorio)";
      return `{{${v.name}}} -> ${v.description} ${requiredText}`;
    })
    .join("\n");
}

function normalizePreviewVariableIndex() {
  if (!Array.isArray(state.variablesDraft) || !state.variablesDraft.length) {
    state.previewVariableIndex = 0;
    return;
  }

  if (state.previewVariableIndex < 0) {
    state.previewVariableIndex = 0;
  }

  if (state.previewVariableIndex > state.variablesDraft.length - 1) {
    state.previewVariableIndex = state.variablesDraft.length - 1;
  }
}

function renderPreviewVariableSelector() {
  const container = el("previewVariableSelector");
  if (!container) {
    return;
  }

  container.innerHTML = "";

  if (!Array.isArray(state.variablesDraft) || !state.variablesDraft.length) {
    const chip = document.createElement("span");
    chip.className = "preview-chip active";
    chip.textContent = "0";
    container.appendChild(chip);
    return;
  }

  state.variablesDraft.forEach((_, idx) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = `preview-chip ${idx === state.previewVariableIndex ? "active" : ""}`;
    chip.textContent = String(idx + 1);
    chip.addEventListener("click", () => {
      state.previewVariableIndex = idx;
      renderPromptPreview();
      renderPreviewVariableSelector();
    });
    container.appendChild(chip);
  });
}

function renderPromptPreview() {
  const baseInstructions = el("cfgPromptBase").value || "";
  const responseFormat = getEffectiveResponseFormat();
  const composed = composeBasePrompt(baseInstructions, responseFormat);
  normalizePreviewVariableIndex();

  let previewVariables = [];
  if (Array.isArray(state.variablesDraft) && state.variablesDraft.length) {
    previewVariables = [state.variablesDraft[state.previewVariableIndex]];
  }

  const variableBlock = buildVariableBlock(previewVariables);
  const placeholderToken = getVariablePlaceholderToken(composed);
  let preview = composed;

  if (placeholderToken === "__MULTIPLE__") {
    preview = `${composed}\n\n[ERROR] Hay varios placeholders distintos {{...}}. Usa solo uno.`;
  } else if (placeholderToken) {
    preview = composed.replace(placeholderToken, variableBlock);
  } else {
    preview = `${composed}\n\n[ERROR] Falta un placeholder {{...}} para variables.`;
  }

  el("promptPreview").textContent = preview;
}

async function api(path, options = {}) {
  const { _skipAuthRetry, ...requestOptions } = options;
  const headers = options.headers ? { ...options.headers } : {};
  const isFormData = requestOptions.body instanceof FormData;

  if (state.selectedBuId && !headers["X-BU-ID"] && !path.startsWith("/auth/")) {
    headers["X-BU-ID"] = state.selectedBuId;
  }

  if (!isFormData && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(path, {
    credentials: "include",
    headers,
    ...requestOptions,
  });

  if (response.status === 401 && !path.startsWith("/auth/") && !_skipAuthRetry) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return api(path, {
        ...requestOptions,
        _skipAuthRetry: true,
      });
    }

    logout();
    throw new Error("Sesion expirada. Inicia sesion nuevamente");
  }

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch (_) {
      // keep fallback detail
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  return response.json();
}

async function refreshAccessToken() {
  if (state.refreshInFlight) {
    return state.refreshInFlight;
  }

  state.refreshInFlight = (async () => {
    try {
      const response = await fetch("/auth/refresh", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });

      if (!response.ok) {
        return false;
      }

      const result = await response.json();
      if (result.user) {
        state.currentUser = result.user;
        persistSession();
      }
      return Boolean(result.user);
    } catch (_) {
      return false;
    } finally {
      state.refreshInFlight = null;
    }
  })();

  return state.refreshInFlight;
}

// ═══════════════════════════ ASSESSMENTS ══════════════════════════════════

Object.assign(state, {
  assessments: [],
  assessConfigsDraft: [],   // [{config_id, config_name}] in order
  editingAssessmentId: null,
});

async function loadAssessments() {
  if (!hasSession() || !state.selectedBuId) return;
  try {
    const list = await api("/assessments/");
    state.assessments = Array.isArray(list) ? list : [];
    renderAssessmentList();
    populateAssessRunSelect();
  } catch (err) {
    setMessage("assessMessage", `Error cargando evaluaciones: ${err.message}`, "error");
  }
}

function renderAssessmentList() {
  const container = el("assessList");
  if (!container) return;

  if (!state.assessments.length) {
    container.innerHTML = '<p class="empty-row">No hay evaluaciones. Crea la primera.</p>';
    return;
  }

  container.innerHTML = "";
  state.assessments.forEach((a) => {
    const card = document.createElement("div");
    card.className = "assess-card";

    const configTags = (a.configs || [])
      .map((c) => `<span class="assess-config-tag">${c.config_name}</span>`)
      .join("");

    card.innerHTML = `
      <div class="assess-card-header">
        <span class="assess-card-name">${a.name}</span>
        <div class="assess-card-actions">
          <button type="button" class="secondary" data-assess-run="${a.id}">Ejecutar</button>
          ${canManagePromptConfigs() ? `<button type="button" class="secondary icon-btn" data-assess-edit="${a.id}" title="Editar">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17.25V21h3.75L18.81 8.94l-3.75-3.75L3 17.25zm17.71-10.04a1 1 0 0 0 0-1.41l-2.5-2.5a1 1 0 0 0-1.41 0L14.96 5.1l3.75 3.75 1.99-1.64z"/></svg>
          </button>
          <button type="button" class="danger icon-btn" data-assess-delete="${a.id}" title="Eliminar">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 6h2v9h-2V9zm4 0h2v9h-2V9zM7 9h2v9H7V9zm1 12h8a2 2 0 0 0 2-2V9H6v10a2 2 0 0 0 2 2z"/></svg>
          </button>` : ""}
        </div>
      </div>
      ${a.description ? `<p class="assess-card-desc">${a.description}</p>` : ""}
      <div class="assess-card-configs">${configTags || '<span style="font-size:.75rem;color:var(--text-3)">Sin configuraciones</span>'}</div>
    `;

    card.querySelector(`[data-assess-run="${a.id}"]`)?.addEventListener("click", () => {
      selectAssessmentForRun(a.id);
    });

    if (canManagePromptConfigs()) {
      card.querySelector(`[data-assess-edit="${a.id}"]`)?.addEventListener("click", () => editAssessment(a.id));
      card.querySelector(`[data-assess-delete="${a.id}"]`)?.addEventListener("click", () => deleteAssessment(a.id));
    }

    container.appendChild(card);
  });
}

function renderAssessConfigDraft() {
  const list = el("assessConfigList");
  if (!list) return;

  if (!state.assessConfigsDraft.length) {
    list.innerHTML = '<li class="assess-config-empty">Agrega al menos una configuración</li>';
    return;
  }

  list.innerHTML = "";
  state.assessConfigsDraft.forEach((cfg, idx) => {
    const li = document.createElement("li");
    li.className = "assess-config-item";
    li.innerHTML = `
      <span class="assess-config-pos">${idx + 1}</span>
      <span class="assess-config-item-name" title="${cfg.config_name}">${cfg.config_name}</span>
      <button class="assess-config-remove" data-remove-idx="${idx}" title="Quitar" type="button">×</button>
    `;
    li.querySelector(`[data-remove-idx]`).addEventListener("click", () => {
      state.assessConfigsDraft.splice(idx, 1);
      renderAssessConfigDraft();
    });
    list.appendChild(li);
  });
}

function populateAssessConfigSelect() {
  const sel = el("assessConfigSelect");
  if (!sel) return;
  sel.innerHTML = '<option value="">Seleccióna config...</option>';
  Object.values(state.configsById).forEach((cfg) => {
    const opt = document.createElement("option");
    opt.value = cfg.id;
    opt.dataset.name = cfg.name;
    opt.textContent = cfg.name;
    sel.appendChild(opt);
  });
}

function populateAssessRunSelect() {
  const sel = el("assessRunSelect");
  if (!sel) return;
  sel.innerHTML = '<option value="">Seleccióna una evaluación</option>';
  state.assessments.forEach((a) => {
    const opt = document.createElement("option");
    opt.value = a.id;
    opt.textContent = a.name;
    sel.appendChild(opt);
  });
}

function populateAssessDocSelect() {
  const sel = el("assessDocSelect");
  if (!sel) return;
  const processed = (state.docsItems || []).filter((d) => d.status === "processed" && d.ocr_text);
  sel.innerHTML = '<option value="">Seleccióna un documento procesado</option>';
  processed.forEach((d) => {
    const opt = document.createElement("option");
    opt.value = d.id;
    opt.textContent = d.filename;
    sel.appendChild(opt);
  });
  if (!processed.length) {
    sel.innerHTML = '<option value="">Sin documentos listos — ve a Documentos</option>';
  }
}

function selectAssessmentForRun(assessmentId) {
  const sel = el("assessRunSelect");
  if (sel) sel.value = assessmentId;
  el("assessRunBtn")?.scrollIntoView({ behavior: "smooth", block: "center" });
}

function editAssessment(assessmentId) {
  const a = state.assessments.find((x) => x.id === assessmentId);
  if (!a) return;

  state.editingAssessmentId = assessmentId;
  el("assessName").value = a.name;
  el("assessDescription").value = a.description || "";
  state.assessConfigsDraft = (a.configs || []).map((c) => ({
    config_id: c.config_id,
    config_name: c.config_name,
  }));
  renderAssessConfigDraft();

  el("assessFormTitle").textContent = "Editar evaluación";
  el("assessSaveBtn").textContent = "Actualizar";
  el("assessCancelBtn").style.display = "";
  el("assessName").focus();
  setMessage("assessFormMessage", "", "idle");
}

function cancelAssessEdit() {
  state.editingAssessmentId = null;
  state.assessConfigsDraft = [];
  el("assessName").value = "";
  el("assessDescription").value = "";
  renderAssessConfigDraft();
  el("assessFormTitle").textContent = "Nueva evaluación";
  el("assessSaveBtn").textContent = "Guardar";
  el("assessCancelBtn").style.display = "none";
  setMessage("assessFormMessage", "", "idle");
}

async function saveAssessment() {
  const name = (el("assessName")?.value || "").trim();
  if (!name) {
    setMessage("assessFormMessage", "El nombre es obligatorio", "error");
    return;
  }
  if (!state.assessConfigsDraft.length) {
    setMessage("assessFormMessage", "Agrega al menos una configuración", "error");
    return;
  }

  const body = {
    name,
    description: (el("assessDescription")?.value || "").trim() || null,
    config_ids: state.assessConfigsDraft.map((c) => c.config_id),
  };

  setMessage("assessFormMessage", "Guardando...", "loading");
  try {
    if (state.editingAssessmentId) {
      await api(`/assessments/${state.editingAssessmentId}`, { method: "PUT", body: JSON.stringify(body) });
    } else {
      await api("/assessments/", { method: "POST", body: JSON.stringify(body) });
    }
    cancelAssessEdit();
    await loadAssessments();
    setMessage("assessMessage", "Evaluación guardada", "success");
  } catch (err) {
    setMessage("assessFormMessage", `Error: ${err.message}`, "error");
  }
}

async function deleteAssessment(assessmentId) {
  const a = state.assessments.find((x) => x.id === assessmentId);
  const confirmed = await openConfirmModal({
    title: "Eliminar evaluación",
    message: `¿Eliminar la evaluación "${a?.name}"?`,
    acceptLabel: "Eliminar",
    cancelLabel: "Cancelar",
  });
  if (!confirmed) return;

  try {
    await api(`/assessments/${assessmentId}`, { method: "DELETE" });
    await loadAssessments();
    setMessage("assessMessage", "Evaluación eliminada", "success");
  } catch (err) {
    setMessage("assessMessage", `Error: ${err.message}`, "error");
  }
}

async function runAssessment() {
  const assessmentId = el("assessRunSelect")?.value;
  const docId = el("assessDocSelect")?.value;

  if (!assessmentId) {
    setMessage("assessRunMessage", "Seleccióna una evaluación", "error");
    return;
  }

  const doc = docId ? (state.docsItems || []).find((d) => d.id === docId) : null;
  const documentText = doc?.ocr_text || "";
  if (!documentText.trim()) {
    setMessage("assessRunMessage", "Seleccióna un documento con texto procesado", "error");
    return;
  }

  setMessage("assessRunMessage", "Iniciando evaluación...", "loading");
  el("assessRunBtn").disabled = true;

  const resultsEl = el("assessRunResults");
  if (resultsEl) resultsEl.style.display = "none";

  try {
    const pending = await api(`/assessments/${assessmentId}/run`, {
      method: "POST",
      body: JSON.stringify({
        document_text: documentText,
        document_name: doc?.filename || null,
        document_id: docId || null,
      }),
    });

    const runId = pending.id;
    const assessment = state.assessments.find((a) => a.id === assessmentId);
    setMessage("assessRunMessage", `Procesando${assessment ? ` "${assessment.name}"` : ""}...`, "loading");

    const MAX_POLLS = 120;
    let polls = 0;
    while (polls < MAX_POLLS) {
      await new Promise((r) => setTimeout(r, 1500));
      polls++;
      let run;
      try {
        run = await api(`/assessments/runs/${runId}`);
      } catch (_) {
        continue;
      }

      if (run.status === "success") {
        renderAssessmentRunResults(run);
        const latency = run.latency_ms ? ` en ${(run.latency_ms / 1000).toFixed(1)}s` : "";
        setMessage("assessRunMessage", `Evaluación completada${latency}`, "success");
        return;
      }

      if (run.status === "failed") {
        setMessage("assessRunMessage", `Error: ${run.error_message || "desconocido"}`, "error");
        return;
      }
    }

    setMessage("assessRunMessage", "La evaluación esta tardando demasiado. Intentalo de nuevo.", "error");
  } catch (err) {
    setMessage("assessRunMessage", `Error: ${err.message}`, "error");
  } finally {
    el("assessRunBtn").disabled = false;
  }
}

function renderAssessmentRunResults(run) {
  const resultsEl = el("assessRunResults");
  const titleEl = el("assessRunTitle");
  const metaEl = el("assessRunMeta");
  const sectionsEl = el("assessRunSections");
  if (!resultsEl || !sectionsEl) return;

  titleEl.textContent = run.assessment_name || "Resultado";
  const latency = run.latency_ms ? `${(run.latency_ms / 1000).toFixed(1)}s` : "";
  metaEl.textContent = [run.document_name, latency].filter(Boolean).join(" · ");

  sectionsEl.innerHTML = "";
  const sections = Array.isArray(run.combined_result) ? run.combined_result : [];
  sections.forEach((section) => {
    const div = document.createElement("div");
    div.className = "assess-section";

    const secLatency = section.latency_ms ? `${(section.latency_ms / 1000).toFixed(1)}s` : "";
    div.innerHTML = `
      <div class="assess-section-header">
        <span class="assess-section-name">${section.config_name}</span>
        <span class="assess-section-meta">${secLatency}</span>
      </div>
    `;

    if (section.error) {
      const errDiv = document.createElement("div");
      errDiv.className = "assess-section-error";
      errDiv.textContent = `Error: ${section.error}`;
      div.appendChild(errDiv);
    } else {
      const items = Array.isArray(section.result) ? section.result : [];
      if (items.length) {
        const table = document.createElement("table");
        table.innerHTML = `<thead><tr><th>Campo</th><th>Valor</th></tr></thead>`;
        const tbody = document.createElement("tbody");
        items.forEach((item) => {
          const tr = document.createElement("tr");
          tr.innerHTML = `<td>${item.title || "-"}</td><td>${item.answer ?? "-"}</td>`;
          tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        div.appendChild(table);
      } else {
        div.innerHTML += '<div class="assess-section-error" style="color:var(--text-3)">Sin resultados</div>';
      }
    }
    sectionsEl.appendChild(div);
  });

  resultsEl.style.display = "";
}

// ═══════════════════════════════════════════════════════════════════════════

// ═══════════════════════ DOC DETAIL / RUN DETAIL ══════════════════════════

// Revoke previous blob URLs to avoid memory leaks
const _previewBlobUrls = {};

// ── PDF.js state & rendering ──────────────────────────────────
// textItems: [{text, transform, width, viewport, hlCanvas, pageDiv}]
const _pdfState = { textItems: [], overlayCanvases: [] };

function _getPdfJs() {
  return window.pdfjsLib || window["pdfjs-dist/build/pdf"];
}

function _initPdfJs() {
  const lib = _getPdfJs();
  if (lib && !lib._centinellInit) {
    lib.GlobalWorkerOptions.workerSrc =
      "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
    lib._centinellInit = true;
  }
}

async function renderPdfWithPdfJs(container, arrayBuffer) {
  const lib = _getPdfJs();
  if (!lib) {
    container.innerHTML = '<p class="preview-loading" style="color:var(--danger)">PDF.js no disponible</p>';
    return;
  }
  _initPdfJs();
  _pdfState.textItems = [];
  _pdfState.overlayCanvases = [];
  container.innerHTML = '<p class="preview-loading">Renderizando PDF...</p>';

  try {
    const pdf = await lib.getDocument({ data: arrayBuffer }).promise;
    container.innerHTML = "";

    for (let p = 1; p <= pdf.numPages; p++) {
      const page = await pdf.getPage(p);
      const viewport = page.getViewport({ scale: 1.4 });
      const W = viewport.width, H = viewport.height;

      const pageDiv = document.createElement("div");
      pageDiv.className = "pdfPage";
      pageDiv.style.width = W + "px";
      pageDiv.style.height = H + "px";

      // Content canvas
      const canvas = document.createElement("canvas");
      canvas.className = "pdfCanvas";
      canvas.width = W; canvas.height = H;
      await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
      pageDiv.appendChild(canvas);

      // Highlight overlay (drawn on demand, sits on top of content canvas)
      const hlCanvas = document.createElement("canvas");
      hlCanvas.width = W; hlCanvas.height = H;
      hlCanvas.style.cssText = "position:absolute;top:0;left:0;pointer-events:none;";
      pageDiv.appendChild(hlCanvas);
      _pdfState.overlayCanvases.push(hlCanvas);

      // Text layer for text selection (best-effort; silently ignored if API missing)
      try {
        const textLayerDiv = document.createElement("div");
        textLayerDiv.className = "pdfTextLayer";
        textLayerDiv.style.width = W + "px";
        textLayerDiv.style.height = H + "px";
        const tcForLayer = await page.getTextContent();
        if (lib.renderTextLayer) {
          const rt = lib.renderTextLayer({
            textContentSource: tcForLayer,
            textContent: tcForLayer,
            container: textLayerDiv,
            viewport,
            textDivs: [],
          });
          const rp = rt && (rt.promise || rt);
          if (rp && rp.then) await rp;
        }
        pageDiv.appendChild(textLayerDiv);
      } catch (_) { /* skip text selection */ }

      // Build search index from textContent items (independent, always works)
      const textContent = await page.getTextContent();
      textContent.items.forEach((item) => {
        if (!item.str || !item.str.trim()) return;
        _pdfState.textItems.push({
          text: item.str,
          transform: item.transform,
          width: item.width,
          viewport,
          hlCanvas,
          pageDiv,
        });
      });

      container.appendChild(pageDiv);
    }
    console.log("[pdfjs] rendered, textItems:", _pdfState.textItems.length);
  } catch (err) {
    console.error("[pdfjs]", err);
    container.innerHTML = `<p class="preview-loading" style="color:var(--danger)">Error al renderizar PDF: ${err.message}</p>`;
  }
}

function clearPdfHighlights() {
  _pdfState.overlayCanvases.forEach((c) => c.getContext("2d").clearRect(0, 0, c.width, c.height));
}

function _drawHighlightItem(item, color) {
  const t = item.transform;
  const vp = item.viewport;
  const [vx, vy] = vp.convertToViewportPoint(t[4], t[5]);
  const scaleX = Math.sqrt(t[0] * t[0] + t[1] * t[1]);
  const fontH = scaleX * vp.scale * 1.15;
  const fontW = Math.max(item.width * vp.scale, 4);
  const ctx = item.hlCanvas.getContext("2d");
  ctx.fillStyle = color;
  ctx.fillRect(vx, vy - fontH, fontW, fontH);
}

function highlightPdfText(quote) {
  clearPdfHighlights();
  const items = _pdfState.textItems;
  console.log('[highlight] textItems:', items.length, '| quote:', (quote || '').slice(0, 70));
  if (!quote || !items.length) return;

  const norm = (s) => s.replace(/[\s]+/g, ' ').trim().toLowerCase();
  const nquote = norm(quote);
  const qwords = nquote.split(' ').filter(Boolean);
  if (!qwords.length) return;

  let bestStart = -1, bestEnd = -1, bestScore = -1;

  for (let s = 0; s < items.length; s++) {
    let combined = '';
    for (let e = s; e < Math.min(s + 100, items.length); e++) {
      combined += (e > s ? ' ' : '') + norm(items[e].text);
      if (combined.includes(nquote)) {
        bestStart = s; bestEnd = e; bestScore = 9999;
        break;
      }
      const matched = qwords.filter((w) => combined.includes(w)).length;
      const score = matched / qwords.length;
      if (score > bestScore && matched >= 2) {
        bestScore = score; bestStart = s; bestEnd = e;
      }
    }
    if (bestScore >= 9999) break;
  }

  console.log('[highlight] bestScore:', bestScore, '| range:', bestStart, '-', bestEnd);
  if (bestStart < 0 || bestScore < 0.3) return;

  for (let i = bestStart; i <= bestEnd; i++) {
    _drawHighlightItem(items[i], i === bestStart ? 'rgba(255,110,0,0.7)' : 'rgba(255,210,0,0.55)');
  }
  items[bestStart].pageDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

async function renderDocPreview(wrapperId, doc) {
  const wrap = el(wrapperId);
  if (!wrap) return;

  if (_previewBlobUrls[wrapperId]) {
    URL.revokeObjectURL(_previewBlobUrls[wrapperId]);
    delete _previewBlobUrls[wrapperId];
  }
  _pdfState.textItems = [];

  wrap.innerHTML = '<p class="preview-loading">Cargando preview…</p>';
  const mime = doc.mime_type || "";
  const fname = (doc.filename || "").toLowerCase();
  const isPdf = mime === "application/pdf" || fname.endsWith(".pdf");
  const isImage = mime.startsWith("image/")
    || [".png", ".jpg", ".jpeg", ".webp"].some((x) => fname.endsWith(x));

  if (isPdf || isImage) {
    try {
      const resp = await fetch(`/documents/${doc.id}/download`, {
        credentials: "include",
        headers: buildAuthHeaders(),
      });
      if (!resp.ok) {
        const body = await resp.text().catch(() => "");
        throw new Error(`HTTP ${resp.status}: ${body || resp.statusText}`);
      }
      const blob = await resp.blob();
      wrap.innerHTML = "";

      if (isPdf && window.pdfjsLib) {
        const ab = await blob.arrayBuffer();
        const pdfWrap = document.createElement("div");
        pdfWrap.className = "pdfViewerWrap";
        wrap.appendChild(pdfWrap);
        await renderPdfWithPdfJs(pdfWrap, ab);
      } else {
        const url = URL.createObjectURL(blob);
        _previewBlobUrls[wrapperId] = url;
        if (isPdf) {
          const frame = document.createElement("iframe");
          frame.src = url;
          frame.className = "doc-preview-frame";
          frame.title = doc.filename;
          wrap.appendChild(frame);
        } else {
          const img = document.createElement("img");
          img.src = url;
          img.className = "doc-preview-img";
          img.alt = doc.filename;
          wrap.appendChild(img);
        }
      }
      return;
    } catch (err) {
      console.error("[preview]", err);
      wrap.innerHTML = `<div class="detail-box" style="color:var(--danger,#e25b5b)">
        <strong>Preview no disponible</strong><br><small>${err.message}</small><br><br>
        <a href="/documents/${doc.id}/download" target="_blank" style="color:var(--accent)">Descargar archivo</a>
      </div>`;
      return;
    }
  }

  // Non-visual: OCR text
  wrap.innerHTML = "";
  const pre = document.createElement("pre");
  pre.className = "detail-box document-preview-live";
  pre.textContent = doc.ocr_text
    || (doc.status === "pending" || doc.status === "processing" ? "OCR en proceso…" : "Sin texto extraido");
  wrap.appendChild(pre);
}

async function openDocumentDetail(docId) {
  activateView("doc-detail", "push", { docId });
  await loadDocumentDetail(docId);
}

async function loadDocumentDetail(docId) {
  if (el("docDetailFilename")) el("docDetailFilename").textContent = "Cargando...";
  if (el("docDetailStatus")) el("docDetailStatus").innerHTML = "";
  if (el("docDetailPreviewWrap")) el("docDetailPreviewWrap").innerHTML = "";
  if (el("docDetailMeta")) el("docDetailMeta").textContent = "";
  if (el("docDetailRunsList")) el("docDetailRunsList").innerHTML = '<p class="empty-row">Cargando...</p>';

  try {
    const [doc, runs] = await Promise.all([
      api(`/documents/${docId}`),
      api(`/documents/${docId}/assessment-runs?limit=20`).catch(() => []),
    ]);

    state.docDetailDoc = doc;
    state.docDetailRuns = runs;

    if (el("docDetailFilename")) el("docDetailFilename").textContent = doc.filename;
    if (el("docDetailStatus")) el("docDetailStatus").innerHTML = docStatusBadge(doc.status);
    if (el("docDetailMeta")) el("docDetailMeta").textContent = `${formatFileSize(doc.size_bytes)} · ${doc.mime_type}`;
    renderDocPreview("docDetailPreviewWrap", doc);

    const sel = el("docDetailAssessSelect");
    if (sel) {
      sel.innerHTML = '<option value="">Seleccióna evaluación</option>';
      (state.assessments || []).filter((a) => a.is_active).forEach((a) => {
        const opt = document.createElement("option");
        opt.value = a.id;
        opt.textContent = a.name;
        sel.appendChild(opt);
      });
    }

    renderDocDetailRuns(runs, doc);
  } catch (err) {
    if (el("docDetailFilename")) el("docDetailFilename").textContent = "Error al cargar";
    if (el("docDetailRunsList")) el("docDetailRunsList").innerHTML = `<p class="empty-row">Error: ${err.message}</p>`;
  }
}

function renderDocDetailRuns(runs, doc) {
  const container = el("docDetailRunsList");
  if (!container) return;

  if (!runs.length) {
    container.innerHTML = '<p class="empty-row">Sin ejecuciones todavia. Usa el formulario para ejecutar la primera.</p>';
    return;
  }

  container.innerHTML = "";
  runs.forEach((run) => {
    const card = document.createElement("div");
    card.className = "doc-run-card";
    const latency = run.latency_ms ? `${(run.latency_ms / 1000).toFixed(1)}s` : "";
    const date = run.created_at ? formatRelativeTime(run.created_at) : "";
    const badge = run.status === "success"
      ? '<span class="doc-status-badge processed">ok</span>'
      : run.status === "failed"
      ? '<span class="doc-status-badge failed">error</span>'
      : '<span class="doc-status-badge processing">...</span>';

    const who = run.created_by_name || "";
    card.innerHTML = `
      <div class="doc-run-card-header">
        <span class="doc-run-card-name">${run.assessment_name || "Evaluación"}</span>
        <span class="doc-run-card-meta">${[date, latency, who].filter(Boolean).join(" · ")}</span>
        ${badge}
      </div>
    `;

    if (run.status === "success") {
      card.classList.add("clickable");
      card.addEventListener("click", () => openRunDetail(doc.id, run.id));
    }
    container.appendChild(card);
  });
}

async function runAssessmentFromDetail() {
  const doc = state.docDetailDoc;
  const assessId = el("docDetailAssessSelect")?.value;

  if (!assessId) { setMessage("docDetailRunMessage", "Seleccióna una evaluación", "error"); return; }
  if (!doc?.ocr_text?.trim()) { setMessage("docDetailRunMessage", "El documento no tiene texto procesado aun", "error"); return; }

  const btn = el("docDetailRunBtn");
  btn.disabled = true;
  setMessage("docDetailRunMessage", "Lanzando evaluación...", "loading");

  try {
    const pending = await api(`/assessments/${assessId}/run`, {
      method: "POST",
      body: JSON.stringify({ document_text: doc.ocr_text, document_name: doc.filename, document_id: doc.id }),
    });
    setMessage("docDetailRunMessage", "Procesando...", "loading");

    for (let i = 0; i < 80; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      let run;
      try { run = await api(`/assessments/runs/${pending.id}`); } catch (_) { continue; }
      if (run.status === "success") {
        setMessage("docDetailRunMessage", "Completado", "success");
        state.docDetailRuns = [run, ...state.docDetailRuns];
        renderDocDetailRuns(state.docDetailRuns, doc);
        openRunDetail(doc.id, run.id);
        return;
      }
      if (run.status === "failed") {
        setMessage("docDetailRunMessage", `Error: ${run.error_message || "desconocido"}`, "error");
        return;
      }
    }
    setMessage("docDetailRunMessage", "Timeout esperando resultado", "error");
  } catch (err) {
    setMessage("docDetailRunMessage", `Error: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
  }
}

async function openRunDetail(docId, runId) {
  activateView("run-detail", "push", { docId, runId });
  await loadRunDetail(docId, runId);
}

async function loadRunDetail(docId, runId) {
  if (el("runDetailAssessName")) el("runDetailAssessName").textContent = "Cargando...";
  if (el("runDetailMeta")) el("runDetailMeta").textContent = "";
  if (el("runDetailSections")) el("runDetailSections").innerHTML = "";
  if (el("runDetailPreviewWrap")) el("runDetailPreviewWrap").innerHTML = "";

  try {
    const run = await api(`/assessments/runs/${runId}`);
    state.runDetailRun = run;

    let doc = state.docDetailDoc;
    if ((!doc || doc.id !== docId) && docId) {
      try { doc = await api(`/documents/${docId}`); state.docDetailDoc = doc; } catch (_) {}
    }

    if (el("runDetailBackLabel")) el("runDetailBackLabel").textContent = doc?.filename || "Documento";
    if (el("runDetailAssessName")) el("runDetailAssessName").textContent = run.assessment_name || "Evaluación";

    const latency = run.latency_ms ? `${(run.latency_ms / 1000).toFixed(1)}s` : "";
    const date = run.created_at ? new Date(run.created_at).toLocaleString("es-ES") : "";
    const who = run.created_by_name ? `Por: ${run.created_by_name}` : "";
    if (el("runDetailMeta")) el("runDetailMeta").textContent = [run.document_name, date, latency, who].filter(Boolean).join(" · ");

    if (doc) renderDocPreview("runDetailPreviewWrap", doc);

    renderRunDetailSections(run);
  } catch (err) {
    if (el("runDetailAssessName")) el("runDetailAssessName").textContent = "Error";
    if (el("runDetailSections")) el("runDetailSections").innerHTML = `<p class="empty-row">Error: ${err.message}</p>`;
  }
}

function renderRunDetailSections(run) {
  const container = el("runDetailSections");
  if (!container) return;
  container.innerHTML = "";

  const sections = Array.isArray(run.combined_result) ? run.combined_result : [];
  if (!sections.length) {
    container.innerHTML = '<p class="empty-row">Sin resultados.</p>';
    return;
  }

  sections.forEach((section) => {
    const div = document.createElement("div");
    div.className = "assess-section";
    const latency = section.latency_ms ? `${(section.latency_ms / 1000).toFixed(1)}s` : "";
    div.innerHTML = `<div class="assess-section-header">
      <span class="assess-section-name">${escapeHtml(section.config_name)}</span>
      <span class="assess-section-meta">${latency}</span>
    </div>`;

    if (section.error) {
      const errDiv = document.createElement("div");
      errDiv.className = "assess-section-error";
      errDiv.textContent = `Error: ${section.error}`;
      div.appendChild(errDiv);
    } else {
      const items = Array.isArray(section.result) ? section.result : [];
      if (items.length) {
        const table = document.createElement("table");
        table.innerHTML = `<thead><tr><th>Campo</th><th>Valor</th><th></th></tr></thead>`;
        const tbody = document.createElement("tbody");

        items.forEach((item) => {
          const hasR = !!item.reasoning;
          const hasQ = !!item.source_quote;

          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td>${escapeHtml(item.title || "-")}</td>
            <td>${escapeHtml(String(item.answer ?? "-"))}</td>
            <td>
              <div class="field-actions">
                ${hasR ? `<button class="btn-reasoning" title="Ver razonamiento" type="button">?</button>` : ""}
                ${hasQ ? `<button class="btn-lupa" title="Localizar en documento" type="button">
                  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
                </button>` : ""}
              </div>
            </td>`;
          tbody.appendChild(tr);

          if (hasR) {
            const rTr = document.createElement("tr");
            rTr.className = "reasoning-row";
            rTr.innerHTML = `<td colspan="3"><div class="reasoning-box">${escapeHtml(item.reasoning)}</div></td>`;
            tbody.appendChild(rTr);

            tr.querySelector(".btn-reasoning").addEventListener("click", function () {
              const box = rTr.querySelector(".reasoning-box");
              box.classList.toggle("open");
              this.classList.toggle("active");
            });
          }

          if (hasQ) {
            tr.querySelector(".btn-lupa").addEventListener("click", function () {
              clearPdfHighlights();
              this.classList.add("active");
              setTimeout(() => this.classList.remove("active"), 1500);
              highlightPdfText(item.source_quote);
            });
          }
        });

        table.appendChild(tbody);
        div.appendChild(table);
      } else {
        div.innerHTML += '<div class="assess-section-error" style="color:var(--text-3)">Sin resultados</div>';
      }
    }
    container.appendChild(div);
  });
}

// ═══════════════════════════ DOCUMENTS ════════════════════════════════════

const DOCS_PAGE_SIZE = 50;

Object.assign(state, {
  docsItems: [],
  docsTotal: 0,
  docsOffset: 0,
  docsPollingTimer: null,
  docDetailDoc: null,
  docDetailRuns: [],
  runDetailRun: null,
});

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function formatRelativeTime(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Ahora";
  if (mins < 60) return `hace ${mins} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "Ayer" : `hace ${days} dias`;
}

function docFileIcon(mime) {
  if (mime && mime.includes("pdf")) {
    return `<svg class="docs-file-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 2H8a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zm-8.5 7.5c0 .83-.67 1.5-1.5 1.5H9v2H7.5V7H10c.83 0 1.5.67 1.5 1.5v1zm5 2c0 .83-.67 1.5-1.5 1.5h-2.5V7H15c.83 0 1.5.67 1.5 1.5v3zm4-3H19v1h1.5V11H19v2h-1.5V7h3v1.5zM9 9.5h1v-1H9v1zM4 6H2v14a2 2 0 0 0 2 2h14v-2H4V6zm10 5.5h1v-3h-1v3z"/></svg>`;
  }
  if (mime && (mime.includes("word") || mime.includes("docx"))) {
    return `<svg class="docs-file-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm-1 9h-2l-1 4-1-4H7l2 6h2l1-4 1 4h2l2-6h-2l-1 4-1-4z"/></svg>`;
  }
  return `<svg class="docs-file-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>`;
}

function docStatusBadge(status) {
  const badges = {
    pending: `<span class="doc-status pending"><svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zm.5 5v6l4 2.5-.75 1.23L11 14V7h1.5z"/></svg>Pendiente</span>`,
    processing: `<span class="doc-status processing"><span class="spinner-mini" aria-hidden="true"></span>Procesando</span>`,
    processed: `<span class="doc-status processed"><svg viewBox="0 0 24 24"><path d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>Listo</span>`,
    failed: `<span class="doc-status failed"><svg viewBox="0 0 24 24"><path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>Error</span>`,
  };
  return badges[status] || badges.pending;
}

function renderDocumentsList() {
  const body = el("docsTableBody");
  const countEl = el("docsCount");
  const loadMoreDiv = el("docsLoadMore");
  if (!body) return;

  const showActions = canRunExtractions();
  const colSpan = showActions ? 6 : 5;

  if (!state.docsItems.length) {
    body.innerHTML = `<tr><td colspan="${colSpan}" class="empty-row">No hay documentos en esta BU. Sube el primero.</td></tr>`;
    if (countEl) countEl.textContent = "";
    if (loadMoreDiv) loadMoreDiv.style.display = "none";
    return;
  }

  if (countEl) {
    countEl.textContent = `${state.docsTotal} documento${state.docsTotal !== 1 ? "s" : ""}`;
  }

  body.innerHTML = "";
  state.docsItems.forEach((doc) => {
    const tr = document.createElement("tr");
    tr.dataset.docId = doc.id;
    tr.dataset.docStatus = doc.status;

    const canOpen = doc.status === "processed" && doc.ocr_text;
    const openTitle = canOpen ? "Abrir en extractor" : (doc.status === "failed" ? "OCR fallido" : "Esperando OCR...");

    const fullDate = doc.created_at ? new Date(doc.created_at).toLocaleString("es-ES") : "";
    const relDate = doc.created_at ? formatRelativeTime(doc.created_at) : "-";

    tr.innerHTML = `
      <td>
        <div class="docs-filename-cell docs-filename-clickable" data-doc-detail="${doc.id}" title="Ver detalle del documento">
          ${docFileIcon(doc.mime_type)}
          <span class="docs-filename">${doc.filename}</span>
        </div>
      </td>
      <td class="docs-uploaded-by">${doc.created_by_name ? escapeHtml(doc.created_by_name) : "-"}</td>
      <td class="docs-size">${formatFileSize(doc.size_bytes)}</td>
      <td class="docs-date" title="${fullDate}">${relDate}</td>
      <td>${docStatusBadge(doc.status)}${doc.ocr_error ? `<span class="result-detail-text" title="${doc.ocr_error}" style="display:block;margin-top:2px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${doc.ocr_error}</span>` : ""}</td>
      ${showActions ? `
      <td>
        <div class="docs-row-actions">
          <button type="button" class="secondary" data-doc-open="${doc.id}" ${canOpen ? "" : "disabled"} title="${openTitle}">Abrir</button>
          <button type="button" class="danger icon-btn" data-doc-delete="${doc.id}" title="Eliminar documento">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 6h2v9h-2V9zm4 0h2v9h-2V9zM7 9h2v9H7V9zm1 12h8a2 2 0 0 0 2-2V9H6v10a2 2 0 0 0 2 2z"/></svg>
          </button>
        </div>
      </td>` : ""}
    `;
    body.appendChild(tr);
  });

  body.querySelectorAll("[data-doc-detail]").forEach((cell) => {
    cell.addEventListener("click", () => openDocumentDetail(cell.dataset.docDetail));
  });

  if (showActions) {
    body.querySelectorAll("button[data-doc-open]").forEach((btn) => {
      btn.addEventListener("click", () => openDocumentInExtractor(btn.dataset.docOpen));
    });

    body.querySelectorAll("button[data-doc-delete]").forEach((btn) => {
      btn.addEventListener("click", () => deleteDocument(btn.dataset.docDelete));
    });
  }

  if (loadMoreDiv) {
    loadMoreDiv.style.display = state.docsItems.length < state.docsTotal ? "" : "none";
  }
}

async function loadDocuments(append = false) {
  if (!hasSession() || !state.selectedBuId) return;

  if (!append) {
    state.docsOffset = 0;
    state.docsItems = [];
  }

  try {
    const data = await api(`/documents/?limit=${DOCS_PAGE_SIZE}&offset=${state.docsOffset}`);
    const items = data.items || [];
    if (append) {
      state.docsItems = [...state.docsItems, ...items];
    } else {
      state.docsItems = items;
    }
    state.docsTotal = data.total || 0;
    state.docsOffset = state.docsItems.length;
    renderDocumentsList();
    setMessage("docsMessage", "", "idle");
    manageDocsPolling();
  } catch (err) {
    setMessage("docsMessage", `Error cargando documentos: ${err.message}`, "error");
  }
}

function manageDocsPolling() {
  const hasPending = state.docsItems.some(
    (d) => d.status === "pending" || d.status === "processing"
  );
  const badge = el("docsPollingBadge");
  if (badge) badge.style.display = hasPending ? "" : "none";

  if (hasPending && !state.docsPollingTimer) {
    state.docsPollingTimer = setInterval(async () => {
      if (!hasSession() || !state.selectedBuId) {
        stopDocsPolling();
        return;
      }
      try {
        const data = await api(`/documents/?limit=${DOCS_PAGE_SIZE}&offset=0`);
        state.docsItems = data.items || [];
        state.docsTotal = data.total || 0;
        state.docsOffset = state.docsItems.length;
        renderDocumentsList();
        const stillPending = state.docsItems.some(
          (d) => d.status === "pending" || d.status === "processing"
        );
        if (!stillPending) stopDocsPolling();
      } catch (_) {
        // silent — don't disrupt the user
      }
    }, 3000);
  } else if (!hasPending) {
    stopDocsPolling();
  }
}

function stopDocsPolling() {
  if (state.docsPollingTimer) {
    clearInterval(state.docsPollingTimer);
    state.docsPollingTimer = null;
  }
  const badge = el("docsPollingBadge");
  if (badge) badge.style.display = "none";
}

async function uploadDocumentFiles(files) {
  if (!files || !files.length) return;
  if (isViewerRole()) {
    setMessage("docsMessage", "No tienes permisos para subir documentos", "error");
    return;
  }

  const progressDiv = el("docsUploadProgress");
  if (progressDiv) progressDiv.style.display = "";

  const items = [];
  Array.from(files).forEach((file) => {
    const itemEl = document.createElement("div");
    itemEl.className = "docs-upload-item";
    itemEl.innerHTML = `
      <span class="spinner-mini" aria-hidden="true"></span>
      <span class="docs-upload-item-name" title="${file.name}">${file.name}</span>
      <span class="docs-upload-item-status uploading">Subiendo...</span>
    `;
    progressDiv.appendChild(itemEl);
    items.push({ file, el: itemEl });
  });

  let anySuccess = false;
  for (const { file, el: itemEl } of items) {
    const statusEl = itemEl.querySelector(".docs-upload-item-status");
    const spinnerEl = itemEl.querySelector(".spinner-mini");
    try {
      const formData = new FormData();
      formData.append("file", file);
      await api("/documents/", { method: "POST", body: formData });
      if (statusEl) { statusEl.textContent = "Subido"; statusEl.className = "docs-upload-item-status done"; }
      if (spinnerEl) spinnerEl.remove();
      anySuccess = true;
    } catch (err) {
      if (statusEl) { statusEl.textContent = err.message; statusEl.className = "docs-upload-item-status error"; }
      if (spinnerEl) spinnerEl.remove();
    }
  }

  if (anySuccess) {
    await loadDocuments();
  }

  setTimeout(() => {
    if (progressDiv) {
      progressDiv.innerHTML = "";
      progressDiv.style.display = "none";
    }
  }, 4000);
}

async function openDocumentInExtractor(docId) {
  const doc = state.docsItems.find((d) => d.id === docId);
  if (!doc || doc.status !== "processed") return;

  const text = doc.ocr_text || "";
  const textarea = el("documentText");
  if (textarea) {
    textarea.value = text;
    textarea.dispatchEvent(new Event("input"));
  }

  state.lastDocumentName = doc.filename;
  state.lastDocumentId = docId;
  activateView("run");
  setMessage("runMessage", `Documento cargado: ${doc.filename}`, "success");
}

async function deleteDocument(docId) {
  const doc = state.docsItems.find((d) => d.id === docId);
  const name = doc ? doc.filename : "este documento";

  const confirmed = await openConfirmModal({
    title: "Eliminar documento",
    message: `¿Eliminar "${name}"? Se borrara el archivo y todos sus datos.`,
    acceptLabel: "Eliminar",
    cancelLabel: "Cancelar",
  });
  if (!confirmed) return;

  try {
    await api(`/documents/${docId}`, { method: "DELETE" });
    state.docsItems = state.docsItems.filter((d) => d.id !== docId);
    state.docsTotal = Math.max(0, state.docsTotal - 1);
    renderDocumentsList();
    setMessage("docsMessage", "Documento eliminado", "success");
  } catch (err) {
    setMessage("docsMessage", `Error eliminando: ${err.message}`, "error");
  }
}

// ═══════════════════════════════════════════════════════════════════════════

// Sub-views that keep the parent nav button highlighted
const VIEW_PARENT = { "doc-detail": "documents", "run-detail": "documents" };

// Parse current URL into {view, docId?, runId?}
function parseCurrentPath() {
  const p = location.pathname;
  let m;
  m = p.match(/^\/docs\/([^/]+)\/runs\/([^/]+)$/);
  if (m) return { view: "run-detail", docId: m[1], runId: m[2] };
  m = p.match(/^\/docs\/([^/]+)$/);
  if (m) return { view: "doc-detail", docId: m[1] };
  return { view: PATH_TO_VIEW[p] ?? "run" };
}

// historyMode: "push" | "replace" | "none"
function activateView(view, historyMode = "push", params = {}) {
  // Guard: si el usuario no puede ejecutar extracciones y navega a una vista
  // restringida (por URL directa o pushState), redirigir a Documentos.
  if (hasSession() && !canRunExtractions() && ["run", "assessments", "history"].includes(view)) {
    view = "documents";
    historyMode = "replace";
    params = {};
  }

  const navView = VIEW_PARENT[view] ?? view;
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === navView);
  });

  document.querySelectorAll(".view").forEach((section) => {
    section.classList.toggle("active", section.id === `view-${view}`);
  });

  if (historyMode !== "none") {
    let path;
    if (view === "doc-detail" && params.docId) path = `/docs/${params.docId}`;
    else if (view === "run-detail" && params.docId && params.runId) path = `/docs/${params.docId}/runs/${params.runId}`;
    else path = VIEW_PATHS[view] ?? `/${view}`;
    if (historyMode === "push") history.pushState({ view, ...params }, "", path);
    else history.replaceState({ view, ...params }, "", path);
  }
}

function renderVariablesDraft() {
  const body = el("variablesTableBody");
  if (!body) {
    return;
  }
  body.innerHTML = "";

  if (!state.variablesDraft.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = '<td colspan="5">No hay variables en el borrador. Carga un prompt o agrega una variable.</td>';
    body.appendChild(tr);
    normalizePreviewVariableIndex();
    renderPreviewVariableSelector();
    renderPromptPreview();
    return;
  }

  state.variablesDraft.forEach((v, index) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${v.name}</td>
      <td>${v.description}</td>
      <td>${v.type}</td>
      <td>${v.required ? "true" : "false"}</td>
      <td>
        <button type="button" class="secondary icon-btn" data-edit-index="${index}" aria-label="Editar variable" title="Editar variable">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17.25V21h3.75L18.81 8.94l-3.75-3.75L3 17.25zm17.71-10.04a1 1 0 0 0 0-1.41l-2.5-2.5a1 1 0 0 0-1.41 0L14.96 5.1l3.75 3.75 1.99-1.64z"/></svg>
        </button>
        <button type="button" class="danger icon-btn" data-remove-index="${index}" aria-label="Eliminar variable" title="Eliminar variable">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 6h2v9h-2V9zm4 0h2v9h-2V9zM7 9h2v9H7V9zm1 12h8a2 2 0 0 0 2-2V9H6v10a2 2 0 0 0 2 2z"/></svg>
        </button>
      </td>
    `;
    body.appendChild(tr);
  });

  body.querySelectorAll("button[data-edit-index]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const index = Number(btn.dataset.editIndex);
      const variable = state.variablesDraft[index];
      state.editingVariableIndex = index;
      el("varName").value = variable.name;
      el("varDescription").value = variable.description;
      el("varType").value = variable.type || "string";
      el("varRequired").checked = variable.required !== false;
      setMessage("configMessage", "Editando variable selecciónada");
    });
  });

  body.querySelectorAll("button[data-remove-index]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const index = Number(btn.dataset.removeIndex);
      state.variablesDraft.splice(index, 1);
      if (state.editingVariableIndex === index) {
        state.editingVariableIndex = null;
        clearVariableInputs();
      }
      renderVariablesDraft();
    });
  });

  normalizePreviewVariableIndex();
  renderPreviewVariableSelector();
  renderPromptPreview();
}

function clearVariableInputs() {
  el("varName").value = "";
  el("varDescription").value = "";
  el("varType").value = "string";
  el("varRequired").checked = true;
}

function normalizeConfigId(rawId) {
  if (rawId === null || rawId === undefined) {
    return "";
  }
  return String(rawId);
}

function getConfigIdFromObject(cfg) {
  if (!cfg || typeof cfg !== "object") {
    return "";
  }
  return normalizeConfigId(cfg.id || cfg.config_id || cfg.prompt_config_id);
}

function getSelectedInspectConfigId() {
  const inspectSelect = el("configInspectSelect");
  if (!inspectSelect) {
    return "";
  }

  const selectedOption = inspectSelect.selectedOptions && inspectSelect.selectedOptions[0];
  if (selectedOption?.dataset?.configId) {
    return normalizeConfigId(selectedOption.dataset.configId);
  }

  return normalizeConfigId(inspectSelect.value);
}

function selectInspectOptionByConfigId(configId) {
  const inspectSelect = el("configInspectSelect");
  const normalized = normalizeConfigId(configId);
  if (!inspectSelect || !normalized) {
    return false;
  }

  const options = Array.from(inspectSelect.options);
  const index = options.findIndex((opt) => normalizeConfigId(opt.dataset.configId) === normalized);
  if (index === -1) {
    return false;
  }

  inspectSelect.selectedIndex = index;
  return true;
}

async function loadConfigs() {
  if (!hasSession() || !state.selectedBuId) {
    state.configsById = {};
    clearConfigEditor({ silent: true });
    const select = el("configSelect");
    const inspectSelect = el("configInspectSelect");
    const colSelect = el("colConfigSelect");
    select.innerHTML = '<option value="">Haz login y seleccióna una BU</option>';
    inspectSelect.innerHTML = '<option value="">Haz login y seleccióna una BU</option>';
    if (colSelect) colSelect.innerHTML = '<option value="">Haz login y seleccióna una BU</option>';
    return;
  }

  let configs;
  try {
    configs = await api("/prompt-configs/");
  } catch (error) {
    state.configsById = {};
    clearConfigEditor({ silent: true });
    setMessage("configMessage", `No se pudieron cargar configuraciones: ${error.message}`, "error");
    return;
  }

  if (!Array.isArray(configs)) {
    state.configsById = {};
    clearConfigEditor({ silent: true });
    setMessage("configMessage", "Respuesta inválida al cargar configuraciones", "error");
    return;
  }

  state.configsById = Object.fromEntries(
    configs
      .map((cfg) => {
        const cfgId = getConfigIdFromObject(cfg);
        return cfgId ? [cfgId, cfg] : null;
      })
      .filter(Boolean)
  );
  const select = el("configSelect");
  const inspectSelect = el("configInspectSelect");
  const colSelect = el("colConfigSelect");
  select.innerHTML = "";
  inspectSelect.innerHTML = "";
  if (colSelect) colSelect.innerHTML = "";

  if (!configs.length) {
    clearConfigEditor({ silent: true });
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No hay configuraciones";
    select.appendChild(option);
    inspectSelect.appendChild(option.cloneNode(true));
    if (colSelect) colSelect.appendChild(option.cloneNode(true));
    return;
  }

  if (state.editingConfigId && !state.configsById[state.editingConfigId]) {
    clearConfigEditor({ silent: true });
  }

  configs.forEach((cfg, index) => {
    const cfgId = getConfigIdFromObject(cfg);
    if (!cfgId) {
      return;
    }

    const option = document.createElement("option");
    option.value = cfgId;
    option.textContent = `${cfg.name} (${cfg.id})`;
    select.appendChild(option);

    const inspectOption = document.createElement("option");
    inspectOption.value = String(index);
    inspectOption.dataset.configId = cfgId;
    inspectOption.textContent = `${cfg.name} (${cfg.id})`;
    inspectSelect.appendChild(inspectOption);

    if (colSelect) {
      const colOption = document.createElement("option");
      colOption.value = cfgId;
      colOption.textContent = `${cfg.name} (${cfg.id})`;
      colSelect.appendChild(colOption);
    }
  });

  const preferredId =
    state.editingConfigId && state.configsById[normalizeConfigId(state.editingConfigId)]
      ? normalizeConfigId(state.editingConfigId)
      : getConfigIdFromObject(configs[0]);
  select.value = preferredId;
  selectInspectOptionByConfigId(preferredId);
  if (colSelect) {
    colSelect.value = preferredId;
  }

  // Si hay una configuración selecciónada en el desplegable, reflejarla en el editor
  // para que el preview siempre muestre variables reales y no un estado vacío.
  if (getSelectedInspectConfigId()) {
    loadSelectedConfigToEditor(getSelectedInspectConfigId());
  }
}

function loadSelectedConfigToEditor(configIdOverride) {
  const configId = normalizeConfigId(configIdOverride || getSelectedInspectConfigId());
  const config = state.configsById[configId]
    || Object.values(state.configsById).find((cfg) => String(cfg.id) === configId);

  if (!config) {
    clearConfigEditor({ silent: true });
    setMessage("configMessage", "Seleccióna una configuración válida", "error");
    return;
  }

  const promptSections = splitPromptSections(config.base_prompt || defaultPrompt);

  state.editingConfigId = config.id;
  state.editingVariableIndex = null;
  el("cfgName").value = config.name || "";
  el("cfgDescription").value = config.description || "";
  el("cfgPromptBase").value = promptSections.baseInstructions;
  syncResponseFormatModeFromText(promptSections.responseFormat);
  el("cfgModel").value = config.model || "gpt-4o";
  state.variablesDraft = Array.isArray(config.variables)
    ? config.variables.map((v) => ({
        name: v.name,
        description: v.description || "",
        required: v.required !== false,
        type: v.type || "string",
        válidation_regex: v.validation_regex || null,
        max_length: v.max_length || null,
      }))
    : [];
  renderVariablesDraft();
  clearVariableInputs();
  renderPromptPreview();
  setMessage("configMessage", `Configuración cargada para edicion: ${config.id}`, "success");
}

function clearConfigEditor(options = {}) {
  const silent = Boolean(options.silent);
  state.editingConfigId = null;
  state.editingVariableIndex = null;
  state.previewVariableIndex = 0;
  state.variablesDraft = [];
  const promptSections = splitPromptSections(defaultPrompt);
  el("cfgName").value = "";
  el("cfgDescription").value = "";
  el("cfgPromptBase").value = promptSections.baseInstructions;
  syncResponseFormatModeFromText(promptSections.responseFormat);
  el("cfgModel").value = "gpt-4o";
  clearVariableInputs();
  renderVariablesDraft();
  renderPromptPreview();
  if (!silent) {
    setMessage("configMessage", "Editor limpio. Listo para nueva configuración", "idle");
  }
}

function buildVariableDescriptionMap(configId) {
  const config = state.configsById[configId];
  if (!config || !Array.isArray(config.variables)) {
    return {};
  }

  return Object.fromEntries(
    config.variables.map((v) => [v.name, v.description || ""])
  );
}

// ── Exportación de resultados ────────────────────────────────────────────────

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function getExportFilename(ext) {
  const base = state.lastDocumentName
    ? state.lastDocumentName.replace(/\.[^.]+$/, "")
    : "extracción";
  return `${base}.${ext}`;
}

function buildAuthHeaders(extraHeaders = {}) {
  const headers = { ...extraHeaders };
  if (state.selectedBuId && !headers["X-BU-ID"]) {
    headers["X-BU-ID"] = state.selectedBuId;
  }
  return headers;
}

async function getErrorDetailFromResponse(response) {
  const fallback = `${response.status} ${response.statusText}`;
  let rawText = "";
  try {
    rawText = await response.text();
  } catch (_) {
    return fallback;
  }

  if (!rawText) {
    return fallback;
  }

  try {
    const parsed = JSON.parse(rawText);
    return parsed.detail || rawText;
  } catch (_) {
    return rawText;
  }
}

function exportJson() {
  if (!state.lastResult || !state.lastResult.length) return;
  const blob = new Blob([JSON.stringify(state.lastResult, null, 2)], { type: "application/json" });
  downloadBlob(blob, getExportFilename("json"));
}

function exportCsv() {
  if (!state.lastResult || !state.lastResult.length) return;
  const lines = ["Campo,Valor"];
  for (const row of state.lastResult) {
    const campo = String(row.title ?? "").replace(/"/g, '""');
    const valor = row.answer === null || row.answer === undefined ? "" : String(row.answer).replace(/"/g, '""');
    lines.push(`"${campo}","${valor}"`);
  }
  const blob = new Blob(["\uFEFF" + lines.join("\r\n")], { type: "text/csv;charset=utf-8;" });
  downloadBlob(blob, getExportFilename("csv"));
}

function renderDocumentPreview() {
  const target = el("resultDocumentPreview");
  const source = el("documentText");
  if (!target || !source) {
    return;
  }

  const text = source.value || "";
  if (!text.trim()) {
    target.textContent = "Carga o pega un documento para comparar los resultados en vivo.";
    return;
  }

  const term = (state.documentHighlightTerm || "").trim();
  if (!term) {
    target.textContent = text;
    return;
  }

  const matchInfo = findDocumentMatch(text, term);
  if (!matchInfo) {
    target.textContent = text;
    return;
  }

  const firstIndex = matchInfo.index;
  const matchedTerm = matchInfo.term;

  const before = text.slice(0, firstIndex)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const match = text.slice(firstIndex, firstIndex + matchedTerm.length)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const after = text.slice(firstIndex + matchedTerm.length)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  target.innerHTML = `${before}<mark class="doc-highlight-match">${match}</mark>${after}`;
}

function findDocumentMatch(sourceText, rawTerm) {
  const text = sourceText || "";
  const term = (rawTerm || "").trim();
  if (!text || !term) {
    return null;
  }

  const sourceLower = text.toLowerCase();
  const candidates = buildSearchCandidates(term);

  for (const candidate of candidates) {
    const candidateLower = candidate.toLowerCase();
    const idx = sourceLower.indexOf(candidateLower);
    if (idx >= 0) {
      return { index: idx, term: candidate };
    }
  }

  return null;
}

function buildSearchCandidates(term) {
  const candidates = new Set();
  const cleanedTerm = term.replace(/\u00A0/g, " ").trim();
  if (!cleanedTerm) {
    return [];
  }

  candidates.add(cleanedTerm);
  candidates.add(cleanedTerm.replace(/\s+/g, ""));

  const numericVariants = buildNumericSearchVariants(cleanedTerm);
  numericVariants.forEach((v) => candidates.add(v));

  return [...candidates].filter(Boolean).sort((a, b) => b.length - a.length);
}

function buildNumericSearchVariants(raw) {
  const compact = raw.replace(/\s+/g, "");
  if (!/[0-9]/.test(compact)) {
    return [];
  }

  const normalized = normalizeNumericForSearch(compact);
  if (!normalized) {
    return [];
  }

  const { value, decimals } = normalized;
  const fixed = value.toFixed(decimals);
  const parts = fixed.split(".");
  const intPart = parts[0];
  const fracPart = parts[1] || "";
  const withDot = fracPart ? `${intPart}.${fracPart}` : intPart;
  const withComma = fracPart ? `${intPart},${fracPart}` : intPart;

  const groupedDot = groupThousands(intPart, ",");
  const groupedComma = groupThousands(intPart, ".");
  const groupedEn = fracPart ? `${groupedDot}.${fracPart}` : groupedDot;
  const groupedEs = fracPart ? `${groupedComma},${fracPart}` : groupedComma;

  return [
    compact,
    withDot,
    withComma,
    groupedEn,
    groupedEs,
  ];
}

function normalizeNumericForSearch(raw) {
  let v = raw;
  const hasDot = v.includes(".");
  const hasComma = v.includes(",");

  if (hasDot && hasComma) {
    const lastDot = v.lastIndexOf(".");
    const lastComma = v.lastIndexOf(",");
    if (lastComma > lastDot) {
      v = v.replace(/\./g, "").replace(/,/g, ".");
    } else {
      v = v.replace(/,/g, "");
    }
  } else if (hasComma && !hasDot) {
    v = v.replace(/,/g, ".");
  }

  if (!/^[+-]?\d+(?:\.\d+)?$/.test(v)) {
    return null;
  }

  const value = Number(v);
  if (!Number.isFinite(value)) {
    return null;
  }

  const decimals = (v.split(".")[1] || "").length;
  return { value, decimals };
}

function groupThousands(intPart, separator) {
  const sign = intPart.startsWith("-") ? "-" : "";
  const digits = intPart.replace(/^[-+]/, "");
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, separator);
  return `${sign}${grouped}`;
}

function focusDocumentMatch(rawTerm) {
  const term = (rawTerm || "").trim();
  if (!term) {
    return;
  }

  state.documentHighlightTerm = term;
  renderDocumentPreview();

  const match = document.querySelector("#resultDocumentPreview .doc-highlight-match");
  if (match) {
    match.scrollIntoView({ block: "center", behavior: "smooth" });
  }
}

async function exportXlsx() {
  if (!state.lastExtractionId) return;
  try {
    const res = await fetch(`/extractions/${state.lastExtractionId}/export/xlsx`, {
      credentials: "include",
      headers: buildAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error(await getErrorDetailFromResponse(res));
    }
    const blob = await res.blob();
    downloadBlob(blob, getExportFilename("xlsx"));
  } catch (err) {
    setMessage("runMessage", `Error al exportar Excel: ${err.message}`, "error");
  }
}

// ─────────────────────────────────────────────────────────────────────────────

function renderResult(result, descriptionMap = {}) {
  const body = el("resultTableBody");
  body.innerHTML = "";

  const exportActions = el("exportResultActions");

  if (!Array.isArray(result) || !result.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = '<td colspan="2" class="empty-row">No se devolvieron campos. Revisa prompt, variables o el contenido del documento.</td>';
    exportActions.style.display = "none";
    body.appendChild(tr);
    return;
  }

  result.forEach((row) => {
    const tr = document.createElement("tr");
    const answer = row.answer === null ? "" : String(row.answer);
    const description = descriptionMap[row.title] || "Sin descripcion disponible";
    const reasoning = row.reasoning ?? row.reason ?? row.rationale ?? "Sin razonamiento disponible";

    const titleTd = document.createElement("td");
    titleTd.textContent = row.title;

    const valueTd = document.createElement("td");
    const input = document.createElement("input");
    input.dataset.answerTitle = row.title;
    input.value = answer;
    valueTd.appendChild(input);

    const detailsWrap = document.createElement("div");
    detailsWrap.className = "result-row-details";

    const findBtn = document.createElement("button");
    findBtn.type = "button";
    findBtn.className = "result-find-btn";
    findBtn.setAttribute("aria-label", `Ir a ${row.title} en el documento`);
    findBtn.setAttribute("title", "Localizar en documento");
    findBtn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 4a6 6 0 1 0 3.87 10.59l4.27 4.27 1.41-1.41-4.27-4.27A6 6 0 0 0 10 4zm0 2a4 4 0 1 1 0 8 4 4 0 0 1 0-8z"/></svg>';
    findBtn.addEventListener("click", () => {
      const term = input.value.trim() || answer;
      focusDocumentMatch(term);
    });

    const variableBtn = document.createElement("button");
    variableBtn.type = "button";
    variableBtn.className = "result-desc-toggle";
    variableBtn.textContent = "Ver Variable";

    const variableText = document.createElement("span");
    variableText.className = "result-detail-text";
    variableText.hidden = true;
    variableText.textContent = description;

    variableBtn.addEventListener("click", () => {
      const isHidden = variableText.hidden;
      variableText.hidden = !isHidden;
      variableBtn.textContent = isHidden ? "Ocultar variable" : "Ver Variable";
    });

    const reasoningBtn = document.createElement("button");
    reasoningBtn.type = "button";
    reasoningBtn.className = "result-desc-toggle";
    reasoningBtn.textContent = "Ver razonamiento";

    const reasoningText = document.createElement("span");
    reasoningText.className = "result-detail-text";
    reasoningText.hidden = true;
    reasoningText.textContent = reasoning;

    reasoningBtn.addEventListener("click", () => {
      const isHidden = reasoningText.hidden;
      reasoningText.hidden = !isHidden;
      reasoningBtn.textContent = isHidden ? "Ocultar razonamiento" : "Ver razonamiento";
    });

    detailsWrap.appendChild(findBtn);
    detailsWrap.appendChild(variableBtn);
    detailsWrap.appendChild(reasoningBtn);
    detailsWrap.appendChild(variableText);
    detailsWrap.appendChild(reasoningText);
    valueTd.appendChild(detailsWrap);

    tr.appendChild(titleTd);
    tr.appendChild(valueTd);
    body.appendChild(tr);
  });

  exportActions.style.display = "flex";
}

async function runExtraction() {
  try {
    ensureSessionAndBu();
  } catch (error) {
    setMessage("runMessage", error.message, "error");
    return;
  }

  const configId = el("configSelect").value;
  const documentText = el("documentText").value.trim();

  if (!configId) {
    setMessage("runMessage", "Seleccióna una configuración", "error");
    return;
  }

  if (!documentText) {
    setMessage("runMessage", "Introduce el texto del documento", "error");
    return;
  }

  setMessage("runMessage", "Enviando extracción...", "loading");
  el("runExtractionBtn").disabled = true;

  try {
    const docName = state.lastDocumentName || `Documento_${new Date().toISOString().slice(0, 10)}`;

    const pending = await api("/extract/", {
      method: "POST",
      body: JSON.stringify({
        config_id: configId,
        document_text: documentText,
        document_name: docName,
        document_id: state.lastDocumentId,
      }),
    });

    const extractionId = pending.extraction_id;
    state.lastExtractionId = extractionId;
    state.lastConfigId = configId;

    if (!extractionId) {
      setMessage("runMessage", "No se pudo crear la extracción", "error");
      return;
    }

    // Poll until the background task finishes
    setMessage("runMessage", "Procesando con IA...", "loading");
    const MAX_POLLS = 120; // 2 min tope
    let polls = 0;
    while (polls < MAX_POLLS) {
      await new Promise((r) => setTimeout(r, 1500));
      polls++;
      let extraction;
      try {
        extraction = await api(`/extractions/${extractionId}`);
      } catch (_) {
        continue;
      }

      if (extraction.status === "success" || extraction.status === "validated") {
        const items = extraction.validated_result || [];
        state.lastResult = items;
        const descriptionMap = buildVariableDescriptionMap(configId);
        renderResult(items, descriptionMap);
        const latency = extraction.latency_ms ? ` (${(extraction.latency_ms / 1000).toFixed(1)}s)` : "";
        setMessage("runMessage", `Extracción completada${latency}`, "success");
        await loadHistory();
        return;
      }

      if (extraction.status === "failed") {
        setMessage("runMessage", `Error en la extracción: ${extraction.error_message || "desconocido"}`, "error");
        return;
      }
    }

    setMessage("runMessage", "La extracción esta tardando demasiado. Comprueba el historial.", "error");
  } catch (error) {
    setMessage("runMessage", `Error: ${error.message}`, "error");
  } finally {
    el("runExtractionBtn").disabled = false;
  }
}

async function saveValidation() {
  try {
    ensureSessionAndBu();
  } catch (error) {
    setMessage("runMessage", error.message, "error");
    return;
  }

  if (!state.lastExtractionId) {
    setMessage("runMessage", "Primero ejecuta una extracción para poder válidar", "error");
    return;
  }

  const reviewed = [];
  const inputs = document.querySelectorAll("input[data-answer-title]");
  const previousByTitle = Object.fromEntries(
    (state.lastResult || []).map((row) => [row.title, row])
  );

  inputs.forEach((input) => {
    const raw = input.value.trim();
    const previous = previousByTitle[input.dataset.answerTitle] || {};
    reviewed.push({
      title: input.dataset.answerTitle,
      answer: raw === "" ? null : raw,
      reasoning:
        previous.reasoning
        ?? previous.reason
        ?? previous.rationale
        ?? null,
    });
  });

  try {
    const updated = await api(`/extractions/${state.lastExtractionId}/validate`, {
      method: "PATCH",
      body: JSON.stringify({ result: reviewed }),
    });

    state.lastResult = updated.validated_result || reviewed;
    const descriptionMap = buildVariableDescriptionMap(state.lastConfigId);
    renderResult(state.lastResult, descriptionMap);
    setMessage("runMessage", "Sobreescribir cambios", "success");
    await loadHistory();
  } catch (error) {
    setMessage("runMessage", `Error al guardar válidación: ${error.message}`, "error");
  }
}

async function parseUploadedFile() {
  const fileInput = el("documentFile");
  const file = fileInput.files && fileInput.files[0];

  if (!file) {
    setMessage("runMessage", "Seleccióna un archivo", "error");
    return;
  }

  setMessage("runMessage", "Extrayendo texto del archivo...", "loading");

  try {
    const formData = new FormData();
    formData.append("file", file);

    const parsed = await api("/documents/parse", {
      method: "POST",
      body: formData,
    });

    const saveForm = new FormData();
    saveForm.append("file", file);
    const savedDoc = await api("/documents/", {
      method: "POST",
      body: saveForm,
    });

    el("documentText").value = parsed.text;
    renderDocumentPreview();
    state.lastDocumentName = parsed.filename;
    state.lastDocumentId = savedDoc.id || null;
    console.log("Document name set to:", state.lastDocumentName);
    const ocrNote = parsed.ocr_warning ? ` Aviso: ${parsed.ocr_warning}` : "";
    setMessage(
      "runMessage",
      `Archivo cargado: ${parsed.filename} (${parsed.char_count} caracteres). Documento ID: ${state.lastDocumentId}.${ocrNote}`,
      "success"
    );
  } catch (error) {
    setMessage("runMessage", `Error al procesar archivo: ${error.message}`, "error");
  }
}

async function createConfig() {
  try {
    ensureSessionAndBu();
  } catch (error) {
    setMessage("configMessage", error.message, "error");
    return;
  }

  const baseInstructions = el("cfgPromptBase").value;
  const responseFormat = getEffectiveResponseFormat();
  const composedPrompt = composeBasePrompt(baseInstructions, responseFormat);

  const payload = {
    name: el("cfgName").value.trim(),
    description: el("cfgDescription").value.trim() || null,
    base_prompt: composedPrompt,
    variables: state.variablesDraft,
    model: el("cfgModel").value.trim() || "gpt-4o",
    temperature: 0.0,
  };

  if (!payload.name) {
    setMessage("configMessage", "El nombre es obligatorio", "error");
    return;
  }

  const placeholderToken = getVariablePlaceholderToken(payload.base_prompt);
  if (!placeholderToken) {
    setMessage("configMessage", "El base prompt debe incluir un placeholder {{...}}", "error");
    return;
  }
  if (placeholderToken === "__MULTIPLE__") {
    setMessage("configMessage", "Usa un unico placeholder {{...}} en todo el base prompt", "error");
    return;
  }

  if (!payload.variables.length) {
    setMessage("configMessage", "Agrega al menos una variable", "error");
    return;
  }

  if (!validateResponseFormatJson(true)) {
    return;
  }

  try {
    const created = await api("/prompt-configs/", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    setMessage("configMessage", `Configuración creada: ${created.id}`, "success");
    clearConfigEditor();
    await loadConfigs();
  } catch (error) {
    setMessage("configMessage", `Error: ${error.message}`, "error");
  }
}

async function updateConfig() {
  try {
    ensureSessionAndBu();
  } catch (error) {
    setMessage("configMessage", error.message, "error");
    return;
  }

  if (!state.editingConfigId) {
    setMessage("configMessage", "Carga una configuración existente en el editor", "error");
    return;
  }

  const baseInstructions = el("cfgPromptBase").value;
  const responseFormat = getEffectiveResponseFormat();
  const composedPrompt = composeBasePrompt(baseInstructions, responseFormat);

  const payload = {
    name: el("cfgName").value.trim(),
    description: el("cfgDescription").value.trim() || null,
    base_prompt: composedPrompt,
    variables: state.variablesDraft,
    model: el("cfgModel").value.trim() || "gpt-4o",
    temperature: 0.0,
  };

  if (!payload.name) {
    setMessage("configMessage", "El nombre es obligatorio", "error");
    return;
  }

  const placeholderToken = getVariablePlaceholderToken(payload.base_prompt);
  if (!placeholderToken) {
    setMessage("configMessage", "El base prompt debe incluir un placeholder {{...}}", "error");
    return;
  }
  if (placeholderToken === "__MULTIPLE__") {
    setMessage("configMessage", "Usa un unico placeholder {{...}} en todo el base prompt", "error");
    return;
  }

  if (!payload.variables.length) {
    setMessage("configMessage", "Agrega al menos una variable", "error");
    return;
  }

  if (!validateResponseFormatJson(true)) {
    return;
  }

  try {
    const updated = await api(`/prompt-configs/${state.editingConfigId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });

    setMessage(
      "configMessage",
      `Configuración actualizada: ${updated.id} (version ${updated.version})`,
      "success"
    );
    await loadConfigs();
    selectInspectOptionByConfigId(updated.id);
    loadSelectedConfigToEditor(String(updated.id));
  } catch (error) {
    setMessage("configMessage", `Error: ${error.message}`, "error");
  }
}

function populateCopyToBuSelect() {
  const sel = el("copyToBuSelect");
  if (!sel) return;
  sel.innerHTML = '<option value="">Seleccióna BU destino</option>';
  state.businessUnits.forEach((bu) => {
    if (String(bu.id) === state.selectedBuId) return; // skip current BU
    const opt = document.createElement("option");
    opt.value = bu.id;
    opt.textContent = `${bu.name} (${bu.code})`;
    sel.appendChild(opt);
  });
}

function updateCopyToBuVisibility() {
  const section = el("copyToBuSection");
  if (!section) return;
  const isGlobal = state.currentUser?.role === "admin_global";
  section.style.display = isGlobal ? "" : "none";
  if (isGlobal) populateCopyToBuSelect();
}

async function copyConfigToBu() {
  const configId = getSelectedInspectConfigId();
  if (!configId) {
    setMessage("copyToBuMessage", "Seleccióna una configuración primero", "error");
    return;
  }
  const targetBuId = el("copyToBuSelect")?.value;
  if (!targetBuId) {
    setMessage("copyToBuMessage", "Seleccióna una BU destino", "error");
    return;
  }
  const targetBu = state.businessUnits.find((b) => String(b.id) === targetBuId);
  try {
    const copied = await api(`/prompt-configs/${configId}/copy-to-bu/${targetBuId}`, { method: "POST" });
    setMessage(
      "copyToBuMessage",
      `Copiado a ${targetBu?.name ?? targetBuId}: "${copied.name}"`,
      "success"
    );
  } catch (error) {
    setMessage("copyToBuMessage", `Error: ${error.message}`, "error");
  }
}

function addVariable() {
  const name = el("varName").value.trim();
  const description = el("varDescription").value.trim();
  const type = el("varType").value;
  const required = el("varRequired").checked;

  if (!name || !description) {
    setMessage("configMessage", "Nombre y descripcion son obligatorios", "error");
    return;
  }

  if (state.variablesDraft.some((v) => v.name === name)) {
    setMessage("configMessage", "No puede haber variables duplicadas", "error");
    return;
  }

  state.variablesDraft.push({
    name,
    description,
    required,
    type,
    válidation_regex: null,
    max_length: null,
  });

  if (state.variablesDraft.length === 1) {
    state.previewVariableIndex = 0;
  }

  clearVariableInputs();
  renderVariablesDraft();
  setMessage("configMessage", "Variable agregada", "success");
}

function updateVariable() {
  if (state.editingVariableIndex === null) {
    setMessage("configMessage", "Seleccióna una variable para editar", "error");
    return;
  }

  const name = el("varName").value.trim();
  const description = el("varDescription").value.trim();
  const type = el("varType").value;
  const required = el("varRequired").checked;

  if (!name || !description) {
    setMessage("configMessage", "Nombre y descripcion son obligatorios", "error");
    return;
  }

  const duplicate = state.variablesDraft.some((v, idx) => {
    return idx !== state.editingVariableIndex && v.name === name;
  });

  if (duplicate) {
    setMessage("configMessage", "No puede haber variables duplicadas", "error");
    return;
  }

  const current = state.variablesDraft[state.editingVariableIndex] || {};
  state.variablesDraft[state.editingVariableIndex] = {
    ...current,
    name,
    description,
    type,
    required,
  };

  state.editingVariableIndex = null;
  clearVariableInputs();
  renderVariablesDraft();
  setMessage("configMessage", "Variable actualizada", "success");
}

function cancelVariableEdit() {
  state.editingVariableIndex = null;
  clearVariableInputs();
  renderPromptPreview();
  setMessage("configMessage", "Edicion de variable cancelada", "idle");
}

function formatHistoryDate(value) {
  if (!value) return "-";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("es-ES", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function renderHistory(rows) {
  const body = el("historyTableBody");
  body.innerHTML = "";

  if (!Array.isArray(rows) || !rows.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = '<td colspan="8" class="empty-row">No hay ejecuciones con esos filtros. Ajusta filtros o lanza una nueva extracción.</td>';
    body.appendChild(tr);
    return;
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const docName = row.document_name && row.document_name.trim() ? row.document_name : "Sin nombre";
    const statusClass = String(row.status || "").toLowerCase();
    const createdAt = formatHistoryDate(row.created_at);
    tr.innerHTML = `
      <td>${docName}</td>
      <td>${row.id}</td>
      <td><span class="status-badge status-${statusClass}">${row.status}</span></td>
      <td>${row.prompt_config_id}</td>
      <td>${row.latency_ms ?? "-"} ms</td>
      <td>${createdAt}</td>
      <td>${row.document_id ? `<button type="button" data-doc-id="${row.document_id}" class="secondary icon-btn" aria-label="Abrir documento" title="Abrir documento"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5c-5.5 0-9.5 5.5-9.5 7s4 7 9.5 7 9.5-5.5 9.5-7-4-7-9.5-7zm0 11a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm0-2.2a1.8 1.8 0 1 0 0-3.6 1.8 1.8 0 0 0 0 3.6z"/></svg></button>` : "-"}</td>
      <td><button type="button" data-open-id="${row.id}" class="secondary icon-btn" aria-label="Ver detalle" title="Ver detalle"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v2H5V5zm0 6h14v2H5v-2zm0 6h10v2H5v-2z"/></svg></button></td>
    `;
    body.appendChild(tr);
  });

  body.querySelectorAll("button[data-open-id]").forEach((btn) => {
    btn.addEventListener("click", () => loadExtractionDetail(btn.dataset.openId));
  });

  body.querySelectorAll("button[data-doc-id]").forEach((btn) => {
    btn.addEventListener("click", () => openDocumentFromHistory(btn.dataset.docId));
  });
}

async function openDocumentFromHistory(documentId) {
  if (!hasSession() || !state.selectedBuId) {
    el("historyDetail").textContent = "Haz login y seleccióna una BU";
    return;
  }

  try {
    const doc = await api(`/documents/${documentId}`);
    const runs = await api(`/documents/${documentId}/runs?limit=20`);
    const recentRuns = Array.isArray(runs)
      ? runs.slice(0, 5).map((run) => `- ${run.id} | ${run.status} | ${run.created_at}`).join("\n")
      : "- Sin ejecuciones recientes";

    el("historyDetail").textContent = [
      `Documento: ${doc.title || doc.filename || doc.id}`,
      `ID: ${doc.id}`,
      `Archivo: ${doc.filename}`,
      `Tipo: ${doc.mime_type}`,
      `Tamano: ${doc.size_bytes} bytes`,
      `BU: ${doc.bu_id}`,
      `Creado: ${doc.created_at}`,
      "",
      `Ejecuciones: ${Array.isArray(runs) ? runs.length : 0}`,
      recentRuns,
    ].join("\n");

    el("historyDetail").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) {
    el("historyDetail").textContent = `Error cargando documento: ${error.message}`;
    el("historyDetail").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

async function loadHistory() {
  if (!hasSession() || !state.selectedBuId) {
    renderHistory([]);
    el("historyDetail").textContent = "Haz login y seleccióna una BU para ver historial.";
    return;
  }

  const status = el("historyStatus").value;
  const configId = el("historyConfigId").value.trim();
  const limit = el("historyLimit").value || "20";

  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (configId) params.set("config_id", configId);
  params.set("limit", limit);

  try {
    const rows = await api(`/extractions/?${params.toString()}`);
    renderHistory(rows);
  } catch (error) {
    el("historyDetail").textContent = `Error cargando historial: ${error.message}`;
  }
}

async function loadExtractionDetail(extractionId) {
  if (!hasSession() || !state.selectedBuId) {
    el("historyDetail").textContent = "Haz login y seleccióna una BU";
    return;
  }

  try {
    const detail = await api(`/extractions/${extractionId}`);
    el("historyDetail").textContent = JSON.stringify(detail, null, 2);
  } catch (error) {
    el("historyDetail").textContent = `Error cargando detalle: ${error.message}`;
  }
}

async function checkApiStatus() {
  setApiStatus("loading", "API status: checking...");
  try {
    const response = await fetch("/health");
    if (!response.ok) {
      throw new Error("healthcheck failed");
    }
    setApiStatus("online", "API status: online");
  } catch (_) {
    setApiStatus("offline", "API status: offline");
  }
}

// ══════════════════════ COLECCIONES ════════════════════════════════════════

const colState = {
  files: [],
  collectionId: null,
};

async function loadColConfigs() {
  const sel = el("colConfigSelect");
  if (!sel) return;

  if (!hasSession() || !state.selectedBuId) {
    sel.innerHTML = '<option value="">Haz login y seleccióna una BU</option>';
    return;
  }

  let configs = Object.values(state.configsById || {});
  if (!configs.length) {
    configs = await api("/prompt-configs/");
  }

  sel.innerHTML = "";
  if (!configs.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No hay configuraciones";
    sel.appendChild(opt);
    return;
  }

  configs.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.name} (${c.id})`;
    sel.appendChild(opt);
  });
}

function renderColQueue() {
  const table = el("colQueueTable");
  const body = el("colQueueBody");
  body.innerHTML = "";
  if (!colState.files.length) {
    table.style.display = "none";
    return;
  }
  table.style.display = "";
  colState.files.forEach((item) => {
    const tr = document.createElement("tr");
    tr.id = `col-row-${item.id}`;
    tr.innerHTML = `
      <td>${item.name}</td>
      <td class="col-status col-status--${item.status}">${item.status}</td>
      <td>${item.fields ?? "-"}</td>
      <td>${item.latency != null ? item.latency + " ms" : "-"}</td>
      <td class="col-error">${item.error || ""}</td>
    `;
    body.appendChild(tr);
  });
}

function updateColRow(id, patch) {
  const item = colState.files.find((f) => f.id === id);
  if (!item) return;
  Object.assign(item, patch);
  const tr = document.getElementById(`col-row-${id}`);
  if (!tr) return;
  if (patch.status !== undefined) {
    tr.querySelector(".col-status").textContent = patch.status;
    tr.querySelector(".col-status").className = `col-status col-status--${patch.status}`;
  }
  if (patch.fields !== undefined) tr.cells[2].textContent = patch.fields;
  if (patch.latency !== undefined) tr.cells[3].textContent = patch.latency + " ms";
  if (patch.error !== undefined) tr.querySelector(".col-error").textContent = patch.error || "";
}

let _colFileIdCounter = 0;
function addFilesToQueue(files) {
  files.forEach((f) => {
    colState.files.push({ id: ++_colFileIdCounter, name: f.name, file: f, status: "pendiente", fields: null, latency: null, error: null });
  });
  el("colUploadLabel").textContent = `${colState.files.length} archivo(s) en cola`;
  renderColQueue();
}

async function extractTextFromFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  const data = await api("/documents/parse", { method: "POST", body: formData });
  return { text: data.text, name: data.filename };
}

async function processCollection() {
  try {
    ensureSessionAndBu();
  } catch (error) {
    setMessage("colMessage", error.message, "error");
    return;
  }

  if (!colState.files.length) {
    setMessage("colMessage", "Añade al menos un archivo", "error");
    return;
  }
  const configId = el("colConfigSelect").value;
  if (!configId) {
    setMessage("colMessage", "Seleccióna una configuración", "error");
    return;
  }
  const rawName = el("colName").value.trim();
  const colName = rawName || `Coleccion_${new Date().toISOString().slice(0, 10)}`;

  el("colProcessBtn").disabled = true;
  el("colSummary").style.display = "none";
  setMessage("colMessage", "Creando colección...", "loading");

  try {
    const col = await api("/collections/", {
      method: "POST",
      body: JSON.stringify({ name: colName, config_id: configId }),
    });
    colState.collectionId = col.id;
  } catch (err) {
    setMessage("colMessage", `Error creando colección: ${err.message}`, "error");
    el("colProcessBtn").disabled = false;
    return;
  }

  setMessage("colMessage", `Procesando 0 / ${colState.files.length}...`, "loading");
  renderColQueue();

  let done = 0;
  for (const item of colState.files) {
    updateColRow(item.id, { status: "extrayendo" });
    let docText, docName;
    try {
      const parsed = await extractTextFromFile(item.file);
      docText = parsed.text;
      docName = parsed.name;
    } catch (err) {
      updateColRow(item.id, { status: "error", error: "No se pudo leer el archivo" });
      done++;
      setMessage("colMessage", `Procesando ${done} / ${colState.files.length}...`, "loading");
      continue;
    }

    updateColRow(item.id, { status: "procesando" });
    try {
      const result = await api("/extract/", {
        method: "POST",
        body: JSON.stringify({
          config_id: configId,
          document_text: docText,
          document_name: docName,
          collection_id: colState.collectionId,
        }),
      });
      const fieldCount = Array.isArray(result.result) ? result.result.length : 0;
      updateColRow(item.id, { status: "ok", fields: fieldCount });
    } catch (err) {
      updateColRow(item.id, { status: "error", error: err.message });
    }
    done++;
    setMessage("colMessage", `Procesando ${done} / ${colState.files.length}...`, "loading");
  }

  const ok = colState.files.filter((f) => f.status === "ok").length;
  const fail = colState.files.filter((f) => f.status === "error").length;
  setMessage("colMessage", `Completado: ${ok} OK, ${fail} errores`, ok && !fail ? "success" : "error");
  el("colSummaryText").textContent = `${ok} extracción(es) correctas · ${fail} error(es)`;
  el("colSummary").style.display = "flex";
  el("colProcessBtn").disabled = false;
  await loadColHistory();
}

async function loadColHistory() {
  try {
    const cols = await api("/collections/?limit=50");
    renderColHistory(cols);
  } catch (err) {
    el("colHistoryBody").innerHTML = `<tr><td colspan="6" class="empty-row">Error: ${err.message}</td></tr>`;
  }
}

function renderColHistory(cols) {
  const body = el("colHistoryBody");
  body.innerHTML = "";
  if (!cols.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty-row">No hay colecciones todavia.</td></tr>';
    return;
  }
  cols.forEach((col) => {
    const tr = document.createElement("tr");
    const date = col.created_at ? new Date(col.created_at).toLocaleString("es-ES") : "-";
    tr.innerHTML = `
      <td>${col.name}</td>
      <td>${col.total_docs}</td>
      <td>${col.success_count + col.validated_count}</td>
      <td>${col.failed_count}</td>
      <td>${date}</td>
      <td><button class="export-btn" onclick="downloadColXlsx('${col.id}','${col.name}')">Excel</button></td>
    `;
    body.appendChild(tr);
  });
}

async function downloadColXlsx(colId, colName) {
  try {
    const res = await fetch(`/collections/${colId}/export/xlsx`, {
      credentials: "include",
      headers: buildAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error(await getErrorDetailFromResponse(res));
    }
    const blob = await res.blob();
    const safe = colName.replace(/[^a-zA-Z0-9_\-]/g, "_");
    downloadBlob(blob, `coleccion_${safe}.xlsx`);
  } catch (err) {
    alert(`Error al exportar: ${err.message}`);
  }
}

async function colExportCurrent(format) {
  if (!colState.collectionId) return;
  if (format === "xlsx") {
    await downloadColXlsx(colState.collectionId, el("colName").value.trim() || "coleccion");
    return;
  }
  try {
    const exts = await api(`/collections/${colState.collectionId}/extractions`);
    if (format === "json") {
      const blob = new Blob([JSON.stringify(exts, null, 2)], { type: "application/json" });
      downloadBlob(blob, "coleccion.json");
    } else {
      const allTitles = [...new Set(exts.flatMap((e) => (e.validated_result || []).map((r) => r.title)))];
      const metaCols = ["id", "documento", "estado", "fecha"];
      const lines = [metaCols.concat(allTitles).map((c) => `"${c}"`).join(",")];
      exts.forEach((e) => {
        const fieldMap = Object.fromEntries((e.validated_result || []).map((r) => [r.title, r.answer ?? ""]));
        const row = [
          e.id, e.document_name || "", e.status,
          e.created_at ? new Date(e.created_at).toLocaleString("es-ES") : "",
          ...allTitles.map((t) => fieldMap[t] ?? ""),
        ].map((v) => `"${String(v).replace(/"/g, '""')}"`);
        lines.push(row.join(","));
      });
      const blob = new Blob(["\uFEFF" + lines.join("\r\n")], { type: "text/csv;charset=utf-8;" });
      downloadBlob(blob, "coleccion.csv");
    }
  } catch (err) {
    alert(`Error al exportar: ${err.message}`);
  }
}

// ═══════════════════════════════════════════════════════════════════════════

function wireNavigation() {
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      activateView(btn.dataset.view, "push");
      if (btn.dataset.view === "apikeys" && canManageApiKeys()) { loadApiKeys(); }
      if (btn.dataset.view === "users" && canManageUsers()) {
        loadUsersAdminData();
      }
      if (btn.dataset.view === "documents") {
        loadDocuments();
      }
      if (btn.dataset.view === "assessments") {
        loadAssessments();
        populateAssessConfigSelect();
        populateAssessDocSelect();
      }
    });
  });

  window.addEventListener("popstate", (event) => {
    const parsed = event.state?.view ? event.state : parseCurrentPath();
    const { view, docId, runId } = parsed;
    activateView(view, "none", parsed);
    if (view === "apikeys" && canManageApiKeys()) loadApiKeys();
    if (view === "users" && canManageUsers()) loadUsersAdminData();
    if (view === "documents") loadDocuments();
    if (view === "assessments") { loadAssessments(); populateAssessConfigSelect(); populateAssessDocSelect(); }
    if (view === "doc-detail" && docId) loadDocumentDetail(docId);
    if (view === "run-detail" && docId && runId) loadRunDetail(docId, runId);
  });
}

function wireActions() {
  const on = (id, eventName, handler) => {
    const node = el(id);
    if (node) {
      node.addEventListener(eventName, handler);
    }
  };

  on("loginForm", "submit", login);
  on("logoutBtn", "click", logout);
  on("sidebarToggleBtn", "click", toggleSidebar);
  on("themeToggleBtn", "click", toggleTheme);
  on("buSelect", "change", async () => {
    state.selectedBuId = el("buSelect").value || null;
    persistSession();
    stopDocsPolling();
    state.docsItems = [];
    state.docsTotal = 0;
    state.docsOffset = 0;
    await loadConfigs();
    await loadColConfigs();
    await loadHistory();
    if (canManageUsers()) {
      await loadUsersAdminData();
    }
    if (canManageApiKeys()) {
      const activeApiKeys = document.querySelector(".nav-btn.active[data-view='apikeys']");
      if (activeApiKeys) await loadApiKeys();
    }
    const docsView = document.querySelector(".nav-btn.active[data-view='documents']");
    if (docsView) loadDocuments();
    await loadAssessments();
    populateAssessConfigSelect();
    populateAssessDocSelect();
    populateCopyToBuSelect();
  });
  on("refreshInspectConfigsBtn", "click", loadConfigs);
  on("configInspectSelect", "change", () => {
    loadSelectedConfigToEditor(getSelectedInspectConfigId());
  });
  on("cfgPromptBase", "input", renderPromptPreview);
  on("documentText", "input", renderDocumentPreview);
  on("cfgResponseFormat", "input", () => {
    if (state.responseFormatMode === "custom") {
      válidateResponseFormatJson(true);
    }
    renderPromptPreview();
  });
  on("cfgResponseFormatMode", "change", () => {
    setResponseFormatMode(el("cfgResponseFormatMode").value);
    renderPromptPreview();
  });
  on("loadConfigToEditorBtn", "click", () => loadSelectedConfigToEditor(getSelectedInspectConfigId()));
  on("clearEditorBtn", "click", clearConfigEditor);
  on("parseFileBtn", "click", parseUploadedFile);
  on("runExtractionBtn", "click", runExtraction);
  on("saveValidationBtn", "click", saveValidation);
  on("addVariableBtn", "click", addVariable);
  on("updateVariableBtn", "click", updateVariable);
  on("cancelVariableEditBtn", "click", cancelVariableEdit);
  on("createConfigBtn", "click", createConfig);
  on("updateConfigBtn", "click", updateConfig);
  on("copyToBuBtn", "click", copyConfigToBu);
  on("docDetailBackBtn", "click", () => activateView("documents", "push"));
  on("docDetailRunBtn", "click", runAssessmentFromDetail);
  on("runDetailBackBtn", "click", () => {
    const doc = state.docDetailDoc;
    if (doc) openDocumentDetail(doc.id);
    else activateView("documents", "push");
  });
  on("loadHistoryBtn", "click", loadHistory);
  on("loadAuditBtn", "click", loadAuditEvents);
  on("reloadUsersAdminBtn", "click", loadUsersAdminData);
  on("createUserInBuBtn", "click", createUserInCurrentBu);
  on("reloadApiKeysBtn", "click", loadApiKeys);
  on("createApiKeyBtn", "click", createApiKey);
  on("apikeyNewKeyCopyBtn", "click", copyApiKeyToClipboard);
  on("confirmModalCancelBtn", "click", () => closeConfirmModal(false));
  on("confirmModalAcceptBtn", "click", () => closeConfirmModal(true));
  on("exportJsonBtn", "click", exportJson);
  on("exportCsvBtn", "click", exportCsv);
  on("exportXlsxBtn", "click", exportXlsx);
  // Colecciones
  on("colProcessBtn", "click", processCollection);
  on("colClearBtn", "click", () => {
    colState.files = [];
    _colFileIdCounter = 0;
    colState.collectionId = null;
    el("colUploadLabel").textContent = "Arrastra archivos aquí o haz clic para selecciónar";
    el("colSummary").style.display = "none";
    setMessage("colMessage", "", "");
    renderColQueue();
  });
  on("colLoadHistoryBtn", "click", loadColHistory);
  on("colExportXlsxBtn", "click", () => colExportCurrent("xlsx"));
  on("colExportJsonBtn", "click", () => colExportCurrent("json"));
  on("colExportCsvBtn", "click", () => colExportCurrent("csv"));
  el("colUploadArea").addEventListener("click", () => {
    if (isViewerRole()) return;
    el("colFileInput").click();
  });
  el("colUploadArea").addEventListener("dragover", (e) => {
    if (isViewerRole()) return;
    e.preventDefault();
    el("colUploadArea").classList.add("drag-over");
  });
  el("colUploadArea").addEventListener("dragleave", () => el("colUploadArea").classList.remove("drag-over"));
  el("colUploadArea").addEventListener("drop", (e) => {
    if (isViewerRole()) return;
    e.preventDefault();
    el("colUploadArea").classList.remove("drag-over");
    addFilesToQueue([...e.dataTransfer.files]);
  });
  el("colFileInput").addEventListener("change", () => {
    if (isViewerRole()) return;
    addFilesToQueue([...el("colFileInput").files]);
    el("colFileInput").value = "";
  });

  // ── Documents upload zone ──────────────────────────────────────
  const docsZone = el("docsUploadZone");
  const docsInput = el("docsFileInput");

  if (docsZone && docsInput) {
    docsZone.addEventListener("click", (e) => {
      if (!isViewerRole()) docsInput.click();
    });
    docsZone.addEventListener("dragover", (e) => {
      if (isViewerRole()) return;
      e.preventDefault();
      docsZone.classList.add("drag-over");
    });
    docsZone.addEventListener("dragleave", () => docsZone.classList.remove("drag-over"));
    docsZone.addEventListener("drop", (e) => {
      if (isViewerRole()) return;
      e.preventDefault();
      docsZone.classList.remove("drag-over");
      uploadDocumentFiles(e.dataTransfer.files);
    });
    docsInput.addEventListener("change", () => {
      uploadDocumentFiles(docsInput.files);
      docsInput.value = "";
    });
  }

  on("docsRefreshBtn", "click", () => loadDocuments());
  on("docsLoadMoreBtn", "click", () => loadDocuments(true));

  // ── Assessments ───────────────────────────────────────────────
  on("assessAddConfigBtn", "click", () => {
    const sel = el("assessConfigSelect");
    if (!sel || !sel.value) return;
    const already = state.assessConfigsDraft.some((c) => c.config_id === sel.value);
    if (already) { setMessage("assessFormMessage", "Esta configuración ya esta en la lista", "error"); return; }
    const name = sel.options[sel.selectedIndex]?.dataset.name || sel.options[sel.selectedIndex]?.text || sel.value;
    state.assessConfigsDraft.push({ config_id: sel.value, config_name: name });
    renderAssessConfigDraft();
    setMessage("assessFormMessage", "", "idle");
  });
  on("assessSaveBtn", "click", saveAssessment);
  on("assessCancelBtn", "click", cancelAssessEdit);
  on("assessRunBtn", "click", runAssessment);
  on("assessRunSelect", "change", () => {
    // sync selected assessment in card list too (highlight?)
  });

  const confirmModal = el("confirmModal");
  if (confirmModal) {
    confirmModal.addEventListener("click", (event) => {
      if (event.target && event.target.dataset && event.target.dataset.confirmClose === "backdrop") {
        closeConfirmModal(false);
      }
    });
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.confirmModalResolver) {
      closeConfirmModal(false);
    }
  });
}

async function bootstrap() {
  // Remove legacy localStorage token keys from pre-cookie auth
  localStorage.removeItem("centinell.accessToken");
  localStorage.removeItem("centinell.refreshToken");

  initTheme();
  loadSessionFromStorage();
  applySidebarState();
  wireNavigation();
  wireActions();
  updateAuthUi();
  renderBuOptions();
  setResponseFormatMode("standard");
  clearConfigEditor();
  renderPreviewVariableSelector();
  renderVariablesDraft();
  renderDocumentPreview();

  // Restore view from URL on first load
  const initialParsed = parseCurrentPath();
  activateView(initialParsed.view, "replace", initialParsed);

  await checkApiStatus();
  const buLoadState = await loadBusinessUnits();
  if (buLoadState?.pendingAssignment) {
    clearSessionForPendingAssignment("");
    return;
  }
  await loadConfigs();
  await loadColConfigs();
  await loadHistory();
  await loadAssessments();
  populateAssessConfigSelect();
  const { view: iv, docId: iDocId, runId: iRunId } = initialParsed;
  if (iv === "documents") loadDocuments();
  else if (iv === "doc-detail" && iDocId) loadDocumentDetail(iDocId);
  else if (iv === "run-detail" && iDocId && iRunId) loadRunDetail(iDocId, iRunId);
}

bootstrap();
