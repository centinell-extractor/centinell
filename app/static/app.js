const state = {
  variablesDraft: [],
  lastExtractionId: null,
  lastResult: [],
  lastConfigId: null,
  lastDocumentName: null,
  configsById: {},
  editingConfigId: null,
  editingVariableIndex: null,
  previewVariableIndex: 0,
  responseFormatMode: "standard",
};

const defaultPrompt = [
  "Eres Centinell, un sistema de extraccion de informacion de documentos.",
  "Extrae exclusivamente los campos indicados.",
  "No anadas explicaciones ni texto adicional.",
  "",
  "CAMPOS A EXTRAER:",
  "{{VARIABLE_BLOCK}}",
  "",
  "REGLAS:",
  "- Si un campo no existe, responde null.",
  "- No inventes valores.",
  "",
  "FORMATO:",
  "[{\"title\": \"NombreVariable\", \"answer\": \"valor\"}]"
].join("\n");

const strictResponseFormat = '[{"title": "NombreVariable", "answer": "valor"}]';

const defaultResponseFormat = strictResponseFormat;

function el(id) {
  return document.getElementById(id);
}

function setMessage(id, text, variant = "idle") {
  const node = el(id);
  node.textContent = text;
  node.classList.remove("is-idle", "is-loading", "is-success", "is-error");
  node.classList.add(`is-${variant}`);
}

function setApiStatus(variant, text) {
  const node = el("apiStatus");
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

function validateResponseFormatJson(showMessage = false) {
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
  const headers = options.headers ? { ...options.headers } : {};
  const isFormData = options.body instanceof FormData;

  if (!isFormData && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(path, {
    headers,
    ...options,
  });

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

  return response.json();
}

function activateView(view) {
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });

  document.querySelectorAll(".view").forEach((section) => {
    section.classList.toggle("active", section.id === `view-${view}`);
  });
}

function renderVariablesDraft() {
  const body = el("variablesTableBody");
  body.innerHTML = "";

  state.variablesDraft.forEach((v, index) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${v.name}</td>
      <td>${v.description}</td>
      <td>${v.type}</td>
      <td>${v.required ? "true" : "false"}</td>
      <td>
        <button class="secondary" data-edit-index="${index}">Editar</button>
        <button class="danger" data-remove-index="${index}">Eliminar</button>
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
      setMessage("configMessage", "Editando variable seleccionada");
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

async function loadConfigs() {
  const configs = await api("/prompt-configs/");
  state.configsById = Object.fromEntries(configs.map((cfg) => [cfg.id, cfg]));
  const select = el("configSelect");
  const inspectSelect = el("configInspectSelect");
  const colSelect = el("colConfigSelect");
  select.innerHTML = "";
  inspectSelect.innerHTML = "";
  if (colSelect) colSelect.innerHTML = "";

  if (!configs.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No hay configuraciones";
    select.appendChild(option);
    inspectSelect.appendChild(option.cloneNode(true));
    if (colSelect) colSelect.appendChild(option.cloneNode(true));
    renderConfigInspectVariables();
    return;
  }

  configs.forEach((cfg) => {
    const option = document.createElement("option");
    option.value = cfg.id;
    option.textContent = `${cfg.name} (${cfg.id})`;
    select.appendChild(option);

    const inspectOption = document.createElement("option");
    inspectOption.value = cfg.id;
    inspectOption.textContent = `${cfg.name} (${cfg.id})`;
    inspectSelect.appendChild(inspectOption);

    if (colSelect) {
      const colOption = document.createElement("option");
      colOption.value = cfg.id;
      colOption.textContent = `${cfg.name} (${cfg.id})`;
      colSelect.appendChild(colOption);
    }
  });

  renderConfigInspectVariables();

  // Si hay una configuración seleccionada en el desplegable, reflejarla en el editor
  // para que el preview siempre muestre variables reales y no un estado vacío.
  if (!state.editingConfigId && inspectSelect.value) {
    loadSelectedConfigToEditor();
  }
}

function renderConfigInspectVariables() {
  const body = el("configInspectVariablesBody");
  const inspectSelect = el("configInspectSelect");
  const configId = inspectSelect.value;
  const config = state.configsById[configId];

  body.innerHTML = "";

  if (!config || !Array.isArray(config.variables) || !config.variables.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = '<td colspan="4">No hay variables para mostrar</td>';
    body.appendChild(tr);
    return;
  }

  config.variables.forEach((v) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${v.name}</td>
      <td>${v.description || "-"}</td>
      <td>${v.type || "string"}</td>
      <td>${v.required === false ? "false" : "true"}</td>
    `;
    body.appendChild(tr);
  });
}

function loadSelectedConfigToEditor() {
  const configId = el("configInspectSelect").value;
  const config = state.configsById[configId];

  if (!config) {
    setMessage("configMessage", "Selecciona una configuracion valida", "error");
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
        validation_regex: v.validation_regex || null,
        max_length: v.max_length || null,
      }))
    : [];
  renderVariablesDraft();
  clearVariableInputs();
  renderPromptPreview();
  setMessage("configMessage", `Configuracion cargada para edicion: ${config.id}`, "success");
}

function clearConfigEditor() {
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
  setMessage("configMessage", "Editor limpio. Listo para nueva configuracion", "idle");
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
    : "extraccion";
  return `${base}.${ext}`;
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

async function exportXlsx() {
  if (!state.lastExtractionId) return;
  try {
    const res = await fetch(`/extractions/${state.lastExtractionId}/export/xlsx`);
    if (!res.ok) throw new Error(await res.text());
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
    tr.innerHTML = '<td colspan="3" class="empty-row">No se devolvieron campos. Revisa prompt, variables o el contenido del documento.</td>';
    exportActions.style.display = "none";
    body.appendChild(tr);
    return;
  }

  result.forEach((row) => {
    const tr = document.createElement("tr");
    const answer = row.answer === null ? "" : String(row.answer);
    const description = descriptionMap[row.title] || "-";

    const titleTd = document.createElement("td");
    titleTd.textContent = row.title;

    const valueTd = document.createElement("td");
    const input = document.createElement("input");
    input.dataset.answerTitle = row.title;
    input.value = answer;
    valueTd.appendChild(input);

    const descriptionTd = document.createElement("td");
    descriptionTd.textContent = description;

    tr.appendChild(titleTd);
    tr.appendChild(valueTd);
    tr.appendChild(descriptionTd);
    body.appendChild(tr);
  });

  exportActions.style.display = "flex";
}

async function runExtraction() {
  const configId = el("configSelect").value;
  const documentText = el("documentText").value.trim();

  if (!configId) {
    setMessage("runMessage", "Selecciona una configuracion", "error");
    return;
  }

  if (!documentText) {
    setMessage("runMessage", "Introduce el texto del documento", "error");
    return;
  }

  setMessage("runMessage", "Ejecutando extraccion...", "loading");
  el("runExtractionBtn").disabled = true;

  try {
    const docName = state.lastDocumentName || `Documento_${new Date().toISOString().slice(0, 10)}`;
    console.log("Enviando extracción con document_name:", docName);
    
    const result = await api("/extract/", {
      method: "POST",
      body: JSON.stringify({
        config_id: configId,
        document_text: documentText,
        document_name: docName,
      }),
    });

    state.lastExtractionId = result.extraction_id;
    state.lastConfigId = configId;
    state.lastResult = result.result;
    const descriptionMap = buildVariableDescriptionMap(configId);
    renderResult(result.result, descriptionMap);
    if (result.extraction_id) {
      setMessage("runMessage", `Extraccion completada. ID: ${result.extraction_id}`, "success");
    } else {
      setMessage("runMessage", "Extraccion completada pero no se pudo guardar en historial", "error");
    }
  } catch (error) {
    setMessage("runMessage", `Error: ${error.message}`, "error");
  } finally {
    el("runExtractionBtn").disabled = false;
  }
}

async function saveValidation() {
  if (!state.lastExtractionId) {
    setMessage("runMessage", "Primero ejecuta una extraccion para poder validar", "error");
    return;
  }

  const reviewed = [];
  const inputs = document.querySelectorAll("input[data-answer-title]");

  inputs.forEach((input) => {
    const raw = input.value.trim();
    reviewed.push({
      title: input.dataset.answerTitle,
      answer: raw === "" ? null : raw,
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
    setMessage("runMessage", "Validacion humana guardada en historial", "success");
    await loadHistory();
  } catch (error) {
    setMessage("runMessage", `Error al guardar validacion: ${error.message}`, "error");
  }
}

async function parseUploadedFile() {
  const fileInput = el("documentFile");
  const file = fileInput.files && fileInput.files[0];

  if (!file) {
    setMessage("runMessage", "Selecciona un archivo", "error");
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

    el("documentText").value = parsed.text;
    state.lastDocumentName = parsed.filename;
    console.log("Document name set to:", state.lastDocumentName);
    setMessage(
      "runMessage",
      `Archivo cargado: ${parsed.filename} (${parsed.char_count} caracteres)`,
      "success"
    );
  } catch (error) {
    setMessage("runMessage", `Error al procesar archivo: ${error.message}`, "error");
  }
}

async function createConfig() {
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

    setMessage("configMessage", `Configuracion creada: ${created.id}`, "success");
    clearConfigEditor();
    await loadConfigs();
  } catch (error) {
    setMessage("configMessage", `Error: ${error.message}`, "error");
  }
}

async function updateConfig() {
  if (!state.editingConfigId) {
    setMessage("configMessage", "Carga una configuracion existente en el editor", "error");
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
      `Configuracion actualizada: ${updated.id} (version ${updated.version})`,
      "success"
    );
    await loadConfigs();
    el("configInspectSelect").value = updated.id;
    renderConfigInspectVariables();
  } catch (error) {
    setMessage("configMessage", `Error: ${error.message}`, "error");
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
    validation_regex: null,
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
    setMessage("configMessage", "Selecciona una variable para editar", "error");
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

function renderHistory(rows) {
  const body = el("historyTableBody");
  body.innerHTML = "";

  if (!Array.isArray(rows) || !rows.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = '<td colspan="7" class="empty-row">No hay ejecuciones con esos filtros. Ajusta filtros o lanza una nueva extraccion.</td>';
    body.appendChild(tr);
    return;
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    const docName = row.document_name && row.document_name.trim() ? row.document_name : "Sin nombre";
    tr.innerHTML = `
      <td>${docName}</td>
      <td>${row.id}</td>
      <td>${row.status}</td>
      <td>${row.prompt_config_id}</td>
      <td>${row.latency_ms ?? "-"} ms</td>
      <td>${row.created_at}</td>
      <td><button data-open-id="${row.id}" class="secondary">Ver</button></td>
    `;
    body.appendChild(tr);
  });

  body.querySelectorAll("button[data-open-id]").forEach((btn) => {
    btn.addEventListener("click", () => loadExtractionDetail(btn.dataset.openId));
  });
}

async function loadHistory() {
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
    await api("/prompt-configs/");
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
  const res = await fetch("/documents/parse", { method: "POST", body: formData });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return { text: data.text, name: data.filename };
}

async function processCollection() {
  if (!colState.files.length) {
    setMessage("colMessage", "Añade al menos un archivo", "error");
    return;
  }
  const configId = el("colConfigSelect").value;
  if (!configId) {
    setMessage("colMessage", "Selecciona una configuracion", "error");
    return;
  }
  const rawName = el("colName").value.trim();
  const colName = rawName || `Coleccion_${new Date().toISOString().slice(0, 10)}`;

  el("colProcessBtn").disabled = true;
  el("colSummary").style.display = "none";
  setMessage("colMessage", "Creando coleccion...", "loading");

  try {
    const col = await api("/collections/", {
      method: "POST",
      body: JSON.stringify({ name: colName, config_id: configId }),
    });
    colState.collectionId = col.id;
  } catch (err) {
    setMessage("colMessage", `Error creando coleccion: ${err.message}`, "error");
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
  el("colSummaryText").textContent = `${ok} extraccion(es) correctas · ${fail} error(es)`;
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
    const res = await fetch(`/collections/${colId}/export/xlsx`);
    if (!res.ok) throw new Error(await res.text());
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
    btn.addEventListener("click", () => activateView(btn.dataset.view));
  });
}

function wireActions() {
  const on = (id, eventName, handler) => {
    const node = el(id);
    if (node) {
      node.addEventListener(eventName, handler);
    }
  };

  on("refreshConfigsBtn", "click", loadConfigs);
  on("refreshInspectConfigsBtn", "click", loadConfigs);
  on("configInspectSelect", "change", () => {
    renderConfigInspectVariables();
    loadSelectedConfigToEditor();
  });
  on("cfgPromptBase", "input", renderPromptPreview);
  on("cfgResponseFormat", "input", () => {
    if (state.responseFormatMode === "custom") {
      validateResponseFormatJson(true);
    }
    renderPromptPreview();
  });
  on("cfgResponseFormatMode", "change", () => {
    setResponseFormatMode(el("cfgResponseFormatMode").value);
    renderPromptPreview();
  });
  on("loadConfigToEditorBtn", "click", loadSelectedConfigToEditor);
  on("clearEditorBtn", "click", clearConfigEditor);
  on("parseFileBtn", "click", parseUploadedFile);
  on("runExtractionBtn", "click", runExtraction);
  on("saveValidationBtn", "click", saveValidation);
  on("addVariableBtn", "click", addVariable);
  on("updateVariableBtn", "click", updateVariable);
  on("cancelVariableEditBtn", "click", cancelVariableEdit);
  on("createConfigBtn", "click", createConfig);
  on("updateConfigBtn", "click", updateConfig);
  on("loadHistoryBtn", "click", loadHistory);
  on("exportJsonBtn", "click", exportJson);
  on("exportCsvBtn", "click", exportCsv);
  on("exportXlsxBtn", "click", exportXlsx);
  // Colecciones
  on("colProcessBtn", "click", processCollection);
  on("colClearBtn", "click", () => {
    colState.files = [];
    _colFileIdCounter = 0;
    colState.collectionId = null;
    el("colUploadLabel").textContent = "Arrastra archivos aqui o haz clic para seleccionar";
    el("colSummary").style.display = "none";
    setMessage("colMessage", "", "");
    renderColQueue();
  });
  on("colLoadHistoryBtn", "click", loadColHistory);
  on("colExportXlsxBtn", "click", () => colExportCurrent("xlsx"));
  on("colExportJsonBtn", "click", () => colExportCurrent("json"));
  on("colExportCsvBtn", "click", () => colExportCurrent("csv"));
  el("colUploadArea").addEventListener("click", () => el("colFileInput").click());
  el("colUploadArea").addEventListener("dragover", (e) => { e.preventDefault(); el("colUploadArea").classList.add("drag-over"); });
  el("colUploadArea").addEventListener("dragleave", () => el("colUploadArea").classList.remove("drag-over"));
  el("colUploadArea").addEventListener("drop", (e) => {
    e.preventDefault();
    el("colUploadArea").classList.remove("drag-over");
    addFilesToQueue([...e.dataTransfer.files]);
  });
  el("colFileInput").addEventListener("change", () => {
    addFilesToQueue([...el("colFileInput").files]);
    el("colFileInput").value = "";
  });
}

async function bootstrap() {
  wireNavigation();
  wireActions();
  setResponseFormatMode("standard");
  clearConfigEditor();
  renderPreviewVariableSelector();
  renderVariablesDraft();
  await checkApiStatus();
  await loadConfigs();
  await loadColConfigs();
  await loadHistory();
}

bootstrap();
