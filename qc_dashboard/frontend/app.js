(async function () {
  const REFRESH_MS = 10000;

  function fmtCell(v) {
    return v == null || v === "" ? '<span class="empty">-</span>' : String(v);
  }

  async function loadAlerts() {
    const tbody = document.querySelector("#alerts tbody");
    tbody.innerHTML = "";
    try {
      const res = await fetch("/api/alerts");
      const data = await res.json();
      const alerts = (data.alerts || []).slice().reverse();
      if (alerts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty">no alerts</td></tr>';
        return;
      }
      for (const a of alerts) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${fmtCell(a.ts)}</td>
          <td class="sev-${a.severity}">${fmtCell(a.severity)}</td>
          <td>${fmtCell(a.actor)}</td>
          <td>${fmtCell(a.code)}</td>
          <td>${fmtCell(a.message)}</td>
        `;
        tbody.appendChild(tr);
      }
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="5" class="sev-critical">error: ${err}</td></tr>`;
    }
  }

  async function loadRuns() {
    const tbody = document.querySelector("#runs tbody");
    tbody.innerHTML = "";
    try {
      const res = await fetch("/api/runs");
      const data = await res.json();
      const runs = (data.runs || []).slice().reverse();
      if (runs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty">no runs yet</td></tr>';
        return;
      }
      for (const r of runs) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${fmtCell(r.run_id)}</td>
          <td>${fmtCell(r.brand)}</td>
          <td>${fmtCell(r.env)}</td>
          <td>${fmtCell(r.last_actor)}</td>
          <td>${fmtCell(r.last_action)}</td>
          <td class="gate-${(r.last_gate_status || "").replace(/\s+/g, "-")}">${fmtCell(r.last_gate_status)}</td>
          <td>${fmtCell(r.last_ts)}</td>
        `;
        tbody.appendChild(tr);
      }
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="7" class="sev-critical">error: ${err}</td></tr>`;
    }
  }

  async function refresh() {
    await Promise.all([loadAlerts(), loadRuns()]);
  }

  refresh();
  setInterval(refresh, REFRESH_MS);
})();
