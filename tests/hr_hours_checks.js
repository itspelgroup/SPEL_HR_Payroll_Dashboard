"use strict";
// Run with Node: node tests/hr_hours_checks.js
const assert = require("node:assert/strict");
const {hrSelect, hrGroup} = require("../static/hr-hours.js");
const {periodDelta,stackHours,periodGroups,chartLayout,comparisonLayout,comparisonBuckets} = require("../static/hr-comparison.js");
const rows = [
  {id:"01",name:"First",unit:"U1",date:"2026-11-01",net:"8",overtime:"2",flags:[]},
  {id:"01",name:"First",unit:"U1",date:"2026-11-02",net:"8",overtime:"-1",flags:["adjustment"]},
  {id:"02",name:"Second",unit:"U2",date:"2026-11-01",net:"4",overtime:"0",flags:[]}
];
assert.equal(hrSelect(rows,"overtime").length,2);
assert.equal(hrSelect(rows,"ot-employees").length,1);
assert.equal(hrSelect(rows,"review").length,1);
const grouped=hrGroup(rows,"employee");
assert.equal(grouped.length,2);
assert.equal(grouped[0].employees,1);
assert.equal(grouped[0].net,16);
assert.equal(grouped[0].overtime,1);
assert.equal(hrGroup(rows,"date")[0].label,"2026-11-01");
assert.equal(hrGroup(rows,"unit")[0].employees,1);
assert.equal(grouped[0].total,17);
assert.equal(periodDelta("120","100").percent,20);
assert.equal(periodDelta("10","0").percent,null);
assert.equal(periodDelta(null,"100").hours,null);
assert.equal(periodDelta("-5","-10").percent,50);
const stack=stackHours("8","2");
assert.equal(stack.net.from,0);
assert.equal(stack.net.to,8);
assert.equal(stack.overtime.from,8);
assert.equal(stack.overtime.to,10);
assert.equal(stack.total,10);
assert.equal(stackHours("8","-1").total,7);
const fiscalRows=[{month:"2023-07-01"},{month:"2024-01-01"},{month:"2024-06-01"},{month:"2024-07-01"}];
assert.equal(periodGroups(fiscalRows,{start:"2023-07-01",end:"2024-06-30"}).length,3);
assert.equal(chartLayout(1080,900,12).width,1080);
assert.equal(chartLayout(1080,900,12).orientation,"vertical");
assert.equal(chartLayout(360,780,12).width,360);
assert.equal(chartLayout(360,780,12).orientation,"horizontal");
assert.equal(chartLayout(1080,900,36).orientation,"horizontal");
assert.equal(chartLayout(360,780,12,"vertical").orientation,"vertical");
assert.equal(chartLayout(1080,900,4,"horizontal").orientation,"horizontal");
assert.equal(chartLayout(1080,900,12,"auto",true).height>chartLayout(1080,900,12).height,true);
const monthBars=[{month_index:0,role:"current",key:"2026-07"},
  {month_index:0,role:"previous",key:"2025-07"},{month_index:6,role:"previous",key:"2026-01"},
  {month_index:6,role:"current",key:"2027-01"}];
const paired=comparisonBuckets(monthBars,"monthly");
assert.equal(paired.length,12);
assert.equal(paired[0].label,"Jul");
assert.equal(paired[0].rows[0].key,"2025-07");
assert.equal(paired[0].rows[1].key,"2026-07");
assert.equal(paired[6].label,"Jan");
assert.equal(paired[6].rows[0].key,"2026-01");
assert.equal(paired[6].rows[1].key,"2027-01");
assert.equal(comparisonBuckets([{label:"FY 2010/11"},{label:"FY 2026/27"}],"yearly").length,2);
assert.equal(comparisonLayout(360,780,24,"monthly").orientation,"vertical");
assert.equal(comparisonLayout(360,780,24,"monthly").width,1100);
assert.equal(comparisonLayout(1600,900,24,"monthly").width,1600);
assert.equal(comparisonLayout(900,800,24,"monthly",true).orientation,"vertical");
assert.equal(comparisonLayout(360,780,12,"yearly").orientation,"horizontal");
console.log("HR hours: 42 calculation/layout/matched-month checks passed");
