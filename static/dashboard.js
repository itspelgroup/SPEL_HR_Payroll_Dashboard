"use strict";

const detailData = document.getElementById("attendance-details");
if (detailData) {
  const employees = JSON.parse(detailData.textContent);
  const dialog = document.getElementById("employee-details");
  const search = document.getElementById("detail-search");
  const body = document.getElementById("employee-rows");
  const count = document.getElementById("detail-count");
  const more = document.createElement("button");
  more.type = "button";
  more.textContent = "Show more employees";
  more.className = "show-more";
  body.closest(".table-scroll").after(more);
  let selected = [];
  let limit = 100;

  function render() {
    const term = search.value.trim().toLocaleLowerCase();
    const matches = selected.filter((employee) =>
      !term || employee.id.toLocaleLowerCase().includes(term) ||
      employee.name.toLocaleLowerCase().includes(term));
    const fragment = document.createDocumentFragment();
    matches.slice(0, limit).forEach((employee) => {
      const row = document.createElement("tr");
      [employee.id, employee.name, employee.location, employee.unit, employee.department,
        employee.punched ? "Recorded" : "No punch recorded"].forEach((value, index) => {
        const cell = document.createElement(index === 0 ? "th" : "td");
        if (index === 0) cell.scope = "row";
        cell.textContent = value;
        row.append(cell);
      });
      fragment.append(row);
    });
    if (!matches.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 6;
      cell.className = "empty";
      cell.textContent = "No employees match this selection.";
      row.append(cell);
      fragment.append(row);
    }
    body.replaceChildren(fragment);
    count.textContent = "Showing " + Math.min(limit, matches.length) + " of " + matches.length + " employees";
    more.hidden = matches.length <= limit;
  }

  document.querySelectorAll("[data-detail]").forEach((tile) => {
    tile.addEventListener("click", () => {
      const kind = tile.dataset.detail;
      selected = employees.filter((employee) => {
        if (kind === "unmapped") return !employee.mapped;
        if (!employee.mapped) return false;
        if (kind === "punched") return employee.punched;
        if (kind === "no-punch") return !employee.punched;
        if (kind === "unit") return employee.unit_token === tile.dataset.unit;
        return true;
      });
      document.getElementById("detail-title").textContent = tile.dataset.title;
      document.getElementById("detail-scope").textContent = kind === "unmapped"
        ? "All locations — punched IDs without an employee record."
        : "Selected location and unit — " + selected.length + " employees.";
      search.value = "";
      limit = 100;
      render();
      dialog.showModal();
      body.closest(".table-scroll").scrollTop = 0;
    });
  });
  search.addEventListener("input", () => { limit = 100; render(); });
  more.addEventListener("click", () => { limit += 100; render(); });
  dialog.addEventListener("click", (event) => {
    const bounds = dialog.getBoundingClientRect();
    if (event.target === dialog &&
        (event.clientX < bounds.left || event.clientX > bounds.right ||
         event.clientY < bounds.top || event.clientY > bounds.bottom)) dialog.close();
  });
}

const locationSelect = document.getElementById("location");
const unitSelect = document.getElementById("unit");
const unitData = document.getElementById("unit-options");
if (locationSelect && unitSelect && unitData) {
  const options = JSON.parse(unitData.textContent);
  locationSelect.addEventListener("change", () => {
    const previous = unitSelect.value;
    const location = locationSelect.value;
    const allowed = options.filter((unit) => !location ||
      (location === "null" ? unit.unassigned : unit.locations.includes(location)));
    unitSelect.replaceChildren(new Option("All units", ""));
    allowed.forEach((unit) => unitSelect.add(new Option(unit.label, unit.value)));
    unitSelect.value = allowed.some((unit) => unit.value === previous) ? previous : "";
  });
}
