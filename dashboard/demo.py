"""Entirely fictional sample records; never loaded from production."""

EMPLOYEES = (
    {'id': 'DEMO001', 'unit': 'UNIT3', 'department': 'Production'},
    {'id': 'DEMO002', 'unit': 'UNIT3', 'department': 'Production'},
    {'id': 'DEMO003', 'unit': 'UNIT3', 'department': 'Quality'},
    {'id': 'DEMO004', 'unit': 'UNIT5RYK', 'department': 'Production'},
    {'id': 'DEMO005', 'unit': 'UNIT5RYK', 'department': 'Quality'},
    {'id': 'DEMO006', 'unit': 'UNIT6', 'department': 'Administration'},
    {'id': 'DEMO007', 'unit': 'UNIT6', 'department': 'Administration'},
    {'id': 'DEMO008', 'unit': 'UNIT8', 'department': 'Production'},
)
# A set represents distinct IDs: repeat punches do not multiply headcounts.
PUNCHED_IDS = frozenset({'DEMO001', 'DEMO003', 'DEMO004', 'DEMO006',
                         'DEMO007', 'DEMO_UNMAPPED'})
