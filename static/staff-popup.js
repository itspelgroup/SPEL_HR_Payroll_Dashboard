"use strict";

function staffValue(person, key) {
  const value = person[key];
  return value === null || value === undefined || String(value).trim() === '' ? 'Not assigned' : String(value);
}

function filterStaff(people, filters, term = '') {
  term = term.trim().toLocaleLowerCase();
  return people.filter(person => Object.entries(filters).every(([key, value]) => !value || staffValue(person, key) === value) &&
    (!term || Object.values(person).some(value => value !== null && String(value).toLocaleLowerCase().includes(term))));
}

function groupStaff(people) {
  const groups = new Map();
  people.forEach(person => {
    const unit = staffValue(person, 'unit'), department = staffValue(person, 'department');
    const key = JSON.stringify([unit, department]);
    const group = groups.get(key) || { unit, department, count: 0 };
    group.count += 1;
    groups.set(key, group);
  });
  return Array.from(groups.values()).sort((a, b) => a.unit.localeCompare(b.unit) || a.department.localeCompare(b.department));
}

if (typeof module !== 'undefined' && module.exports) module.exports = { staffValue, filterStaff, groupStaff };

if (typeof document !== 'undefined') {
  const source = document.querySelector('[data-staff-source]');
  const dialog = document.querySelector('[data-staff-mode]');
  if (source && dialog) {
    const people = JSON.parse(source.textContent);
    const alertMode = dialog.dataset.staffMode === 'alerts';
    const selects = Array.from(dialog.querySelectorAll('[data-staff-filter]'));
    const search = dialog.querySelector('[data-staff-search]');
    const sort = dialog.querySelector('[data-staff-sort]');
    const rows = dialog.querySelector('[data-staff-rows]');
    const groupBody = dialog.querySelector('[data-staff-groups]');
    const breakdown = dialog.querySelector('[data-staff-breakdown]');
    let selected = [];

    function values() { return Object.fromEntries(selects.map(select => [select.dataset.staffFilter, select.value])); }

    function refreshChoices() {
      let available = selected;
      selects.forEach(select => {
        const key = select.dataset.staffFilter, previous = select.value;
        select.replaceChildren(new Option('All', ''));
        Array.from(new Set(available.map(person => staffValue(person, key)))).sort((a, b) => a.localeCompare(b))
          .forEach(value => select.add(new Option(value, value)));
        select.value = Array.from(select.options).some(option => option.value === previous) ? previous : '';
        if (select.value) available = filterStaff(available, { [key]: select.value });
      });
    }

    function render() {
      const matches = filterStaff(selected, values(), search.value);
      matches.sort((a, b) => sort.value === 'elapsed_seconds'
        ? (b.elapsed_seconds ?? -1) - (a.elapsed_seconds ?? -1)
        : staffValue(a, sort.value).localeCompare(staffValue(b, sort.value), undefined, { numeric: true }));
      const columns = alertMode ? ['id', 'name', 'branch', 'unit', 'department', 'employee_location', 'in_location', 'last_in', 'last_out', 'last_in_hours', 'duration']
        : ['id', 'name', 'unit', 'department', 'physical', 'status'];
      const fragment = document.createDocumentFragment();
      matches.forEach(person => {
        const row = document.createElement('tr');
        if (person.overdue) row.classList.add('overdue-row');
        columns.forEach(key => {
          const cell = document.createElement('td');
          cell.textContent = key === 'status' ? 'Active' : (person[key] ?? '—');
          row.append(cell);
        });
        fragment.append(row);
      });
      if (!matches.length) {
        const row = document.createElement('tr'), cell = document.createElement('td');
        cell.colSpan = columns.length; cell.textContent = 'No employees match these filters.'; row.append(cell); fragment.append(row);
      }
      rows.replaceChildren(fragment);
      const units = new Set(matches.map(person => staffValue(person, 'unit'))).size;
      const departments = new Set(matches.map(person => staffValue(person, 'department'))).size;
      dialog.querySelector('[data-staff-count]').textContent = `${matches.length} of ${selected.length} employees · ${units} units · ${departments} departments`;
      if (!alertMode) {
        const groups = groupStaff(matches);
        breakdown.querySelector('[data-staff-breakdown-count]').textContent = `${groups.length} groups`;
        const groupedFragment = document.createDocumentFragment();
        groups.forEach(group => {
          const row = document.createElement('tr');
          [group.unit, group.department].forEach(value => { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); });
          const countCell = document.createElement('td'), button = document.createElement('button');
          button.type = 'button'; button.textContent = String(group.count);
          button.setAttribute('aria-label', `${group.unit}, ${group.department}: ${group.count} employees`);
          button.addEventListener('click', () => {
            selects.forEach(select => { select.value = ''; });
            search.value = '';
            const unit = selects.find(select => select.dataset.staffFilter === 'unit');
            unit.value = group.unit; refreshChoices();
            selects.find(select => select.dataset.staffFilter === 'department').value = group.department;
            refreshChoices(); render();
          });
          countCell.append(button); row.append(countCell); groupedFragment.append(row);
        });
        groupBody.replaceChildren(groupedFragment);
      }
    }

    function clearFilters() {
      selects.forEach(select => { select.value = ''; }); search.value = ''; sort.value = 'name'; refreshChoices(); render();
    }

    document.querySelectorAll('[data-staff-kind]').forEach(tile => tile.addEventListener('click', () => {
      selected = people.filter(person => tile.dataset.staffKind === 'all' || person[tile.dataset.staffKind]);
      dialog.querySelector('[data-staff-title]').textContent = tile.dataset.title;
      clearFilters();
      if (breakdown) breakdown.open = tile.dataset.staffGrouped === 'true';
      dialog.showModal(); rows.closest('.punch-scroll').scrollTop = 0;
    }));
    selects.forEach(select => select.addEventListener('change', () => { refreshChoices(); render(); }));
    search.addEventListener('input', render); sort.addEventListener('change', render);
    dialog.querySelector('[data-staff-reset]').addEventListener('click', clearFilters);
  }
}
