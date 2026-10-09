const storageKey = "noc-tefe-dashboard";

const initialSites = [
  {
    id: crypto.randomUUID(),
    nome: "AM_TFE_01",
    ip: "10.50.0.21",
    usuarios: 415,
    consumo: 57.2,
    ping: 13,
    status: "normal",
    alertas: true,
    aau: [
      { nome: "N78_S1", valor: 15 },
      { nome: "N78_S2", valor: 23 },
      { nome: "N78_S3", valor: 4 },
    ],
    eventos: ["Coleta DSP S1INTERFACE concluida", "DSP NRCELLUENUMBER atualizado"],
  },
  {
    id: crypto.randomUUID(),
    nome: "AM_TFE_02",
    ip: "10.50.0.22",
    usuarios: 72,
    consumo: 13.2,
    ping: 13,
    status: "normal",
    alertas: true,
    aau: [],
    eventos: ["Coleta DSP S1INTERFACE concluida"],
  },
  {
    id: crypto.randomUUID(),
    nome: "AM_TFE_03",
    ip: "10.50.0.23",
    usuarios: null,
    consumo: 0,
    ping: null,
    status: "falha",
    alertas: true,
    aau: [],
    eventos: ["Web timeout"],
  },
  {
    id: crypto.randomUUID(),
    nome: "AM_TFE_04",
    ip: "10.50.0.24",
    usuarios: 17,
    consumo: 29.4,
    ping: 14,
    status: "normal",
    alertas: true,
    aau: [
      { nome: "N78_S1", valor: 3 },
      { nome: "N78_S2", valor: 0 },
      { nome: "N78_S3", valor: 3 },
    ],
    eventos: ["Coleta de AAU concluida"],
  },
  {
    id: crypto.randomUUID(),
    nome: "AM_TFE_05",
    ip: "10.31.0.35",
    usuarios: 63,
    consumo: 9,
    ping: 13,
    status: "normal",
    alertas: false,
    aau: [],
    eventos: ["Alertas silenciados pelo bot"],
  },
  {
    id: crypto.randomUUID(),
    nome: "AM_TFE_06",
    ip: "10.31.0.37",
    usuarios: 68,
    consumo: 5.4,
    ping: 18,
    status: "normal",
    alertas: true,
    aau: [],
    eventos: ["Sessao web mantida ativa"],
  },
];

let sites = loadSites();
let selectedId = sites[0]?.id;
let filter = "todos";
let editingId = null;

const els = {
  clock: document.querySelector("#clock"),
  nextRun: document.querySelector("#nextRun"),
  metricOnline: document.querySelector("#metricOnline"),
  metricUsers: document.querySelector("#metricUsers"),
  metricTraffic: document.querySelector("#metricTraffic"),
  metricAlerts: document.querySelector("#metricAlerts"),
  searchInput: document.querySelector("#searchInput"),
  sitesTable: document.querySelector("#sitesTable"),
  detailStatus: document.querySelector("#detailStatus"),
  detailBody: document.querySelector("#detailBody"),
  aauTotal: document.querySelector("#aauTotal"),
  aauList: document.querySelector("#aauList"),
  eventsList: document.querySelector("#eventsList"),
  dialog: document.querySelector("#siteDialog"),
  form: document.querySelector("#siteForm"),
  dialogTitle: document.querySelector("#dialogTitle"),
  deleteSiteBtn: document.querySelector("#deleteSiteBtn"),
};

function loadSites() {
  const saved = localStorage.getItem(storageKey);
  if (!saved) return initialSites;

  try {
    const parsed = JSON.parse(saved);
    return Array.isArray(parsed) && parsed.length ? parsed : initialSites;
  } catch {
    return initialSites;
  }
}

function saveSites() {
  localStorage.setItem(storageKey, JSON.stringify(sites));
}

function fmtTraffic(value) {
  if (!value) return "0 b/s";
  if (value < 1) return `${Math.round(value * 1000)} kb/s`;
  return `${value.toFixed(value >= 10 ? 1 : 2)} Mb/s`;
}

function fmtUsers(value) {
  return value === null || value === undefined ? "N/I" : `${value} usuarios`;
}

function nextHourlyRun() {
  const now = new Date();
  const next = new Date(now);
  next.setMinutes(55, 0, 0);
  if (next <= now) next.setHours(next.getHours() + 1);
  return next.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function tickClock() {
  els.clock.textContent = new Date().toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  els.nextRun.textContent = `Proxima coleta ${nextHourlyRun()}`;
}

function getVisibleSites() {
  const term = els.searchInput.value.trim().toLowerCase();
  return sites.filter((site) => {
    const matchesFilter = filter === "todos" || site.status === filter;
    const haystack = `${site.nome} ${site.ip} ${site.status}`.toLowerCase();
    return matchesFilter && haystack.includes(term);
  });
}

function renderMetrics() {
  const online = sites.filter((site) => site.status === "normal").length;
  const users = sites.reduce((total, site) => total + (site.usuarios ?? 0), 0);
  const traffic = sites.reduce((total, site) => total + (site.consumo || 0), 0);
  const alerts = sites.filter((site) => site.status !== "normal" && site.alertas).length;

  els.metricOnline.textContent = `${online}/${sites.length}`;
  els.metricUsers.textContent = users.toString();
  els.metricTraffic.textContent = fmtTraffic(traffic);
  els.metricAlerts.textContent = alerts.toString();
}

function statusLabel(site) {
  if (site.status === "normal") return `Normal ${site.ping ?? "-"}ms`;
  if (site.status === "manutencao") return "Manutencao";
  return site.ping === null ? "Sem ping" : "Web timeout";
}

function renderTable() {
  const visible = getVisibleSites();
  els.sitesTable.innerHTML = "";

  if (!visible.length) {
    els.sitesTable.innerHTML = `<tr><td colspan="7" class="empty">Nenhum site encontrado</td></tr>`;
    return;
  }

  visible.forEach((site) => {
    const row = document.createElement("tr");
    row.className = site.id === selectedId ? "selected" : "";
    row.innerHTML = `
      <td><button class="row-button" type="button" data-select="${site.id}">${site.nome}</button></td>
      <td>${site.ip}</td>
      <td>${fmtUsers(site.usuarios)}</td>
      <td>${fmtTraffic(site.consumo)}</td>
      <td>${site.ping === null ? "100% loss" : `${site.ping}ms`}</td>
      <td><span class="status ${site.status}">${statusLabel(site)}</span></td>
      <td>
        <button class="mini-button" type="button" data-alert="${site.id}">
          ${site.alertas ? "Ativo" : "Silenciado"}
        </button>
        <button class="mini-button" type="button" data-edit="${site.id}">Editar</button>
      </td>
    `;
    els.sitesTable.appendChild(row);
  });
}

function renderDetails() {
  const site = sites.find((item) => item.id === selectedId) || sites[0];
  if (!site) return;
  selectedId = site.id;

  els.detailStatus.textContent = statusLabel(site);
  els.detailStatus.className = `pill ${site.status}`;
  els.detailBody.innerHTML = `
    <div><span>Site</span><strong>${site.nome}</strong></div>
    <div><span>IP</span><strong>${site.ip}</strong></div>
    <div><span>Usuarios</span><strong>${fmtUsers(site.usuarios)}</strong></div>
    <div><span>Consumo</span><strong>${fmtTraffic(site.consumo)}</strong></div>
    <div><span>Ping</span><strong>${site.ping === null ? "100% loss" : `${site.ping}ms`}</strong></div>
    <div><span>Alertas</span><strong>${site.alertas ? "Ativos" : "Silenciados"}</strong></div>
  `;

  const totalAau = site.aau.reduce((total, item) => total + item.valor, 0);
  els.aauTotal.textContent = `${totalAau} UE/RRC`;
  els.aauList.innerHTML = site.aau.length
    ? site.aau.map((item) => `<div><span>${item.nome}</span><strong>${item.valor} UE/RRC</strong></div>`).join("")
    : `<div class="empty">Sem AAU para este site</div>`;

  els.eventsList.innerHTML = site.eventos
    .slice(-5)
    .reverse()
    .map((event) => `<div><span>${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</span>${event}</div>`)
    .join("");
}

function render() {
  renderMetrics();
  renderTable();
  renderDetails();
}

function simulateCollection() {
  sites = sites.map((site) => {
    if (site.status !== "normal") {
      return {
        ...site,
        eventos: [...site.eventos, "Nova tentativa agendada"],
      };
    }

    const usuarios = Math.max(0, (site.usuarios ?? 0) + Math.floor(Math.random() * 9) - 4);
    const consumo = Math.max(0, site.consumo + (Math.random() * 4 - 2));
    return {
      ...site,
      usuarios,
      consumo: Number(consumo.toFixed(2)),
      ping: Math.max(8, (site.ping ?? 14) + Math.floor(Math.random() * 5) - 2),
      eventos: [...site.eventos, "Coleta manual simulada"],
    };
  });
  saveSites();
  render();
}

function openDialog(site) {
  editingId = site?.id ?? null;
  els.dialogTitle.textContent = editingId ? "Editar site" : "Adicionar site";
  els.deleteSiteBtn.hidden = !editingId;
  document.querySelector("#siteName").value = site?.nome ?? "";
  document.querySelector("#siteIp").value = site?.ip ?? "";
  document.querySelector("#siteTraffic").value = site?.consumo ?? "";
  document.querySelector("#siteUsers").value = site?.usuarios ?? 0;
  document.querySelector("#sitePing").value = site?.ping ?? 0;
  document.querySelector("#siteStatus").value = site?.status ?? "normal";
  els.dialog.showModal();
}

function handleFormSubmit() {
  const payload = {
    nome: document.querySelector("#siteName").value.trim(),
    ip: document.querySelector("#siteIp").value.trim(),
    consumo: Number(document.querySelector("#siteTraffic").value),
    usuarios: Number(document.querySelector("#siteUsers").value),
    ping: Number(document.querySelector("#sitePing").value),
    status: document.querySelector("#siteStatus").value,
  };

  if (editingId) {
    sites = sites.map((site) => (site.id === editingId ? { ...site, ...payload } : site));
  } else {
    const id = crypto.randomUUID();
    sites.push({ id, ...payload, alertas: true, aau: [], eventos: ["Site cadastrado"] });
    selectedId = id;
  }

  saveSites();
  render();
}

document.querySelectorAll(".segment").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".segment").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    filter = button.dataset.filter;
    renderTable();
  });
});

document.querySelector("#equipToggle").addEventListener("click", () => {
  const group = document.querySelector("#equipGroup");
  const isOpen = group.classList.toggle("open");
  document.querySelector("#equipToggle").setAttribute("aria-expanded", String(isOpen));
});

document.querySelectorAll(".nav-subitem").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-subitem").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
  });
});

els.searchInput.addEventListener("input", renderTable);
document.querySelector("#refreshBtn").addEventListener("click", render);
document.querySelector("#runBtn").addEventListener("click", simulateCollection);
document.querySelector("#addSiteBtn").addEventListener("click", () => openDialog());
document.querySelector("#closeDialogBtn").addEventListener("click", () => els.dialog.close());

els.sitesTable.addEventListener("click", (event) => {
  const selectId = event.target.dataset.select;
  const alertId = event.target.dataset.alert;
  const editId = event.target.dataset.edit;

  if (selectId) {
    selectedId = selectId;
    render();
  }

  if (alertId) {
    sites = sites.map((site) => (site.id === alertId ? { ...site, alertas: !site.alertas } : site));
    saveSites();
    render();
  }

  if (editId) openDialog(sites.find((site) => site.id === editId));
});

els.form.addEventListener("submit", handleFormSubmit);
els.deleteSiteBtn.addEventListener("click", () => {
  sites = sites.filter((site) => site.id !== editingId);
  selectedId = sites[0]?.id;
  saveSites();
  els.dialog.close();
  render();
});

setInterval(tickClock, 1000);
tickClock();
render();
