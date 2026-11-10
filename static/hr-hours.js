"use strict";

// Shared pure helpers also support offline checks; no per-tile network requests.
function hrSelect(rows, kind) {
  if (kind === "overtime") return rows.filter(row => row.overtime !== null && Number(row.overtime) !== 0);
  if (kind === "ot-employees") return rows.filter(row => row.id && Number(row.overtime) > 0);
  if (kind === "review") return rows.filter(row => row.flags.length > 0);
  return rows;
}

function hrGroup(rows, dimension) {
  const groups = new Map();
  rows.forEach(row => {
    const key = dimension === "employee" ? row.id.trim().toLocaleLowerCase() : row[dimension];
    // Missing IDs contribute hours, but must not collapse into a fake employee.
    const token = key || "\u0000missing";
    if (!groups.has(token)) groups.set(token, {
      label: dimension === "employee" ? (row.id || "Missing employee ID") : key,
      name: dimension === "employee" ? row.name : "", records: 0,
      net: 0, overtime: 0, total: 0, employees: new Set(), review: 0
    });
    const group = groups.get(token);
    group.records += 1;
    if (row.net !== null) group.net += Number(row.net);
    if (row.overtime !== null) group.overtime += Number(row.overtime);
    if (row.total !== null && row.total !== undefined) group.total += Number(row.total);
    else group.total = group.net + group.overtime;
    if (row.id) group.employees.add(row.id.toLocaleLowerCase());
    group.review += Number(row.flags.length > 0);
  });
  return [...groups.values()].map(group => ({...group, employees: group.employees.size}))
    .sort((left, right) => dimension === "date"
      ? String(left.label).localeCompare(String(right.label)) : right.net - left.net);
}

if (typeof module !== "undefined" && module.exports) module.exports = {hrSelect, hrGroup};

if (typeof document !== "undefined") {
  const source = document.getElementById("hr-hours-data");
  if (source) {
    const all = JSON.parse(source.textContent);
    const dialog = document.getElementById("hr-details");
    const search = document.getElementById("hr-search");
    const view = document.getElementById("hr-view");
    const head = document.getElementById("hr-detail-head");
    const body = document.getElementById("hr-detail-rows");
    const more = document.getElementById("hr-more");
    const format = value => value === null ? "—" : Number(value).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    let selected = [], limit = 100;

    function render() {
      const term = search.value.trim().toLocaleLowerCase();
      const matches = selected.filter(row => !term || [row.id, row.name, row.unit, row.department,
        row.worker, row.date, row.source, ...row.flags].join(" ").toLocaleLowerCase().includes(term));
      const grouped = view.value !== "records";
      const records = grouped ? hrGroup(matches, view.value) : matches;
      let columns;
      if (!grouped) columns = ["Date", "Employee ID", "Employee name", "Unit", "Department", "Worker type", "DirectWorker", "Net hours", "OT hours", "Total hours", "Time in", "Time out", "Source", "Review"];
      else columns = [view.value === "employee" ? "Employee ID" : "Group", ...(view.value === "employee" ? ["Employee name"] : []), "Employees", "Records", "Net hours", "OT hours", "Total hours", "OT share of total", "Review records"];
      const headerRow = document.createElement("tr");
      columns.forEach(title => { const cell = document.createElement("th"); cell.scope = "col"; cell.textContent = title; headerRow.append(cell); });
      head.replaceChildren(headerRow);
      const fragment = document.createDocumentFragment();
      records.slice(0, limit).forEach(record => {
        const row = document.createElement("tr");
        const values = grouped ? [record.label, ...(view.value === "employee" ? [record.name] : []), record.employees,
          record.records, format(record.net), format(record.overtime), format(record.total), record.total > 0 ? format(record.overtime / record.total * 100) + '%' : "—", record.review]
          : [record.date, record.id || "Not available", record.name, record.unit, record.department, record.worker,
            record.direct, format(record.net), format(record.overtime), format(record.total), record.time_in || "—", record.time_out || "—", record.source, record.flags.join("; ") || "—"];
        values.forEach((value, index) => { const cell = document.createElement(index === 0 ? "th" : "td"); if (index === 0) cell.scope = "row"; cell.textContent = value; row.append(cell); });
        fragment.append(row);
      });
      if (!records.length) {
        const row = document.createElement("tr"), cell = document.createElement("td");
        cell.colSpan = columns.length; cell.className = "hr-empty"; cell.textContent = "No records match this selection.";
        row.append(cell); fragment.append(row);
      }
      body.replaceChildren(fragment);
      more.hidden = records.length <= limit;
      const ids = new Set(matches.filter(row => row.id).map(row => row.id.toLocaleLowerCase()));
      document.getElementById("hr-detail-count").textContent = matches.length.toLocaleString() + " source records · " + ids.size.toLocaleString() + " distinct IDs · showing " + Math.min(records.length, limit) + " of " + records.length + (grouped ? " groups" : " rows");
    }

    document.querySelectorAll("[data-hr-kind],[data-hr-group],[data-hr-date]").forEach(tile => {
      tile.addEventListener("click", () => {
        selected = tile.dataset.hrDate ? all.filter(row => row.date === tile.dataset.hrDate) : hrSelect(all, tile.dataset.hrKind);
        view.value = tile.dataset.hrGroup || (["employees", "ot-employees"].includes(tile.dataset.hrKind) ? "employee" : "records");
        document.getElementById("hr-detail-title").textContent = tile.dataset.title;
        search.value = ""; limit = 100; render(); dialog.showModal();
        document.querySelector(".hr-detail-table").scrollTop = 0;
      });
    });
    search.addEventListener("input", () => { limit = 100; render(); });
    view.addEventListener("change", () => { limit = 100; render(); });
    more.addEventListener("click", () => { limit += 100; render(); });
    // Close/Escape/backdrop handling and refresh pause reuse machines.js.
  }
}
