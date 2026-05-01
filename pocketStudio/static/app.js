const state = {
  agents: [],
  teams: [],
  queue: [],
  tasks: [],
  events: [],
  providers: [],
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  if (response.status === 204) return null;
  return response.json();
}

function escapeHtml(value = "") {
  return value.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

function setView(view) {
  $$(".view").forEach((item) => item.classList.toggle("active", item.id === view));
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  $("#viewTitle").textContent = view[0].toUpperCase() + view.slice(1);
}

async function loadAll() {
  const [health, providers, agents, teams, queue, tasks, events] = await Promise.all([
    api("/health"),
    api("/providers"),
    api("/agents"),
    api("/teams"),
    api("/queue"),
    api("/tasks"),
    api("/events"),
  ]);
  state.providers = providers;
  state.agents = agents;
  state.teams = teams;
  state.queue = queue;
  state.tasks = tasks;
  state.events = events;
  $("#healthText").textContent = health.status === "ok" ? "Online" : "Offline";
  $("#providerText").textContent = `${providers.length} providers`;
  render();
}

function render() {
  renderProviderOptions();
  renderAgents();
  renderTeams();
  renderScene();
  renderTargets();
  renderQueue();
  renderTasks();
  renderEvents();
  loadChat();
}

function renderProviderOptions() {
  $("#agentProvider").innerHTML = state.providers.map((name) => `<option value="${name}">${name}</option>`).join("");
}

function renderAgents() {
  $("#agentGrid").innerHTML = state.agents.map((agent) => `
    <article class="item-card">
      <h3>${escapeHtml(agent.name)}</h3>
      <p>${escapeHtml(agent.role)}</p>
      <p><span class="badge">${escapeHtml(agent.provider)}</span> <span class="badge">${agent.enabled ? "enabled" : "disabled"}</span></p>
    </article>
  `).join("") || `<p class="empty">No agents yet.</p>`;

  $("#teamAgents").innerHTML = state.agents.map((agent) => (
    `<option value="${agent.id}">${agent.name} (${agent.id})</option>`
  )).join("");
}

function renderTeams() {
  $("#teamGrid").innerHTML = state.teams.map((team) => `
    <article class="item-card">
      <h3>${escapeHtml(team.name)}</h3>
      <p><span class="badge">${escapeHtml(team.mode)}</span></p>
      <p>${team.agent_ids.map(escapeHtml).join(" → ") || "No agents"}</p>
    </article>
  `).join("") || `<p class="empty">No teams yet.</p>`;

  $("#teamSelect").innerHTML = state.teams.map((team) => `<option value="${team.id}">${team.name}</option>`).join("");
  const active = state.teams.find((team) => team.id === $("#teamSelect").value) || state.teams[0];
  $("#activeTeamName").textContent = active ? active.name : "Team chat";
}

function renderScene() {
  const positions = [
    [195, 260],
    [470, 222],
    [725, 300],
    [330, 470],
    [620, 500],
    [820, 455],
  ];
  $("#sceneAgents").innerHTML = state.agents.map((agent, index) => {
    const [left, top] = positions[index % positions.length];
    return `
      <div class="agent-sprite" style="left:${left}px;top:${top}px">
        <div class="agent-label">${escapeHtml(agent.name)}</div>
        <div class="agent-head"></div>
        <div class="agent-body"></div>
      </div>
    `;
  }).join("");
}

function renderTargets() {
  const teamOptions = state.teams.map((team) => `<option value="@team:${team.id}">Team: ${team.name}</option>`);
  const agentOptions = state.agents.map((agent) => `<option value="@agent:${agent.id}">Agent: ${agent.name}</option>`);
  $("#targetSelect").innerHTML = [...teamOptions, ...agentOptions].join("");
}

function renderQueue() {
  $("#queueList").innerHTML = state.queue.map((item) => `
    <article class="queue-item">
      <div>
        <strong>#${item.id} ${escapeHtml(item.target)}</strong>
        <p>${escapeHtml(item.content)}</p>
        ${item.error ? `<p class="status-failed">${escapeHtml(item.error)}</p>` : ""}
      </div>
      <span class="badge status-${item.status}">${item.status}</span>
    </article>
  `).join("") || `<p class="empty">Queue is empty.</p>`;
}

function renderTasks() {
  const columns = {
    todo: $("#todoTasks"),
    in_progress: $("#inProgressTasks"),
    done: $("#doneTasks"),
  };
  Object.values(columns).forEach((column) => { column.innerHTML = ""; });
  state.tasks.forEach((task) => {
    const target = columns[task.status] || columns.todo;
    target.insertAdjacentHTML("beforeend", `
      <article class="task-card">
        <strong>${escapeHtml(task.title)}</strong>
        <p>${escapeHtml(task.description)}</p>
        <span class="badge">${escapeHtml(task.status)}</span>
      </article>
    `);
  });
}

function renderEvents() {
  $("#eventList").innerHTML = state.events.map((event) => `
    <article class="event-item">
      <strong>${escapeHtml(event.type)}</strong>
      <code>${escapeHtml(JSON.stringify(event.payload))}</code>
    </article>
  `).join("") || `<p class="empty">No events yet.</p>`;
}

async function loadChat() {
  const teamId = $("#teamSelect").value || state.teams[0]?.id;
  if (!teamId) {
    $("#chatLog").innerHTML = `<p class="empty">Create a team to start chatting.</p>`;
    return;
  }
  const messages = await api(`/chatroom/${teamId}`);
  $("#chatLog").innerHTML = messages.map((message) => `
    <article class="chat-message">
      <strong>${escapeHtml(message.sender)}</strong>
      <p>${escapeHtml(message.message)}</p>
    </article>
  `).join("") || `<p class="empty">No team messages yet.</p>`;
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

async function seedDemo() {
  await api("/agents", {
    method: "POST",
    body: JSON.stringify({ id: "planner", name: "Planner", role: "Breaks work into clean steps", provider: "local" }),
  });
  await api("/agents", {
    method: "POST",
    body: JSON.stringify({ id: "coder", name: "Coder", role: "Implements Python services", provider: "local" }),
  });
  await api("/agents", {
    method: "POST",
    body: JSON.stringify({ id: "reviewer", name: "Reviewer", role: "Reviews behavior and risks", provider: "local" }),
  });
  await api("/teams", {
    method: "POST",
    body: JSON.stringify({ id: "dev", name: "Dev Team", mode: "chain", agent_ids: ["planner", "coder", "reviewer"] }),
  });
  await api("/tasks", {
    method: "POST",
    body: JSON.stringify({ title: "Wire TinyOffice frontend", description: "Build live workspace panels.", status: "in_progress" }),
  });
  await loadAll();
}

function bindEvents() {
  $$(".nav-item").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
  $("#refreshAll").addEventListener("click", loadAll);
  $("#seedDemo").addEventListener("click", seedDemo);
  $("#teamSelect").addEventListener("change", () => {
    renderTeams();
    loadChat();
  });

  $("#agentForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = formData(event.currentTarget);
    await api("/agents", { method: "POST", body: JSON.stringify(payload) });
    event.currentTarget.reset();
    await loadAll();
  });

  $("#teamForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = formData(event.currentTarget);
    payload.agent_ids = [...event.currentTarget.elements.agent_ids.selectedOptions].map((option) => option.value);
    await api("/teams", { method: "POST", body: JSON.stringify(payload) });
    event.currentTarget.reset();
    await loadAll();
  });

  $("#promptForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const content = $("#promptInput").value.trim();
    const target = $("#targetSelect").value;
    if (!content || !target) return;
    await api("/messages", { method: "POST", body: JSON.stringify({ target, content }) });
    $("#promptInput").value = "";
    await loadAll();
  });

  $("#processNext").addEventListener("click", async () => {
    await api("/queue/process-next", { method: "POST" });
    await loadAll();
  });

  $("#taskForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await api("/tasks", { method: "POST", body: JSON.stringify(formData(event.currentTarget)) });
    event.currentTarget.reset();
    await loadAll();
  });
}

bindEvents();
loadAll().catch((error) => {
  $("#healthText").textContent = "Error";
  $("#providerText").textContent = error.message;
});
