"use strict";
function runStaffPopupChecks(api) {
  let checks = 0;
  function equal(actual, expected) {
    if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error(`Expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`);
    checks += 1;
  }
  const people = [
    { id: '001', name: 'First Person', unit: 'U1', department: 'HR', physical: 'Pandoki' },
    { id: '002', name: 'Second Person', unit: 'U1', department: 'IT', physical: 'Pandoki' },
    { id: '003', name: 'Third Person', unit: 'U2', department: 'HR', physical: 'Karachi' }
  ];
  equal(api.filterStaff(people, { unit: 'U1', department: 'HR' }).map(row => row.id), ['001']);
  equal(api.filterStaff(people, { department: 'IT' }).map(row => row.id), ['002']);
  equal(api.filterStaff([{ ...people[2], department: null }], { department: 'Not assigned' }).map(row => row.id), ['003']);
  equal(api.filterStaff(people, { physical: 'Karachi' }, 'THIRD').map(row => row.id), ['003']);
  equal(api.filterStaff(people, { unit: 'U1' }, 'third').length, 0);
  equal(api.filterStaff(people.slice(0, 1), { unit: 'U2' }).length, 0);
  equal(api.groupStaff([people[0], { ...people[0], id: '004' }]), [{ unit: 'U1', department: 'HR', count: 2 }]);
  equal(people.length, 3);
  return checks;
}
if (typeof module !== 'undefined' && module.exports) module.exports = runStaffPopupChecks;
