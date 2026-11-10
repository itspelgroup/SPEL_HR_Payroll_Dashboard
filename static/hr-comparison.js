"use strict";

function periodDelta(current, baseline) {
  if (current === null || baseline === null) return {hours:null, percent:null};
  const value = Number(current), prior = Number(baseline);
  return {hours:value-prior, percent:prior !== 0 ? (value-prior)/Math.abs(prior)*100 : null};
}
function stackHours(net, overtime) {
  const working=Number(net),ot=Number(overtime);
  return {net:{from:0,to:working},overtime:{from:working,to:working+ot},total:working+ot};
}
function periodGroups(groups, period) {
  if (!period) return groups;
  return groups.filter(row=>row.month.slice(0,7)>=period.start.slice(0,7) &&
                            row.month.slice(0,7)<=period.end.slice(0,7));
}
function chartLayout(availableWidth, viewportHeight, count, orientation="auto", expanded=false) {
  const width=Math.max(1,Math.floor(availableWidth));
  const direction=orientation==="auto" ?
    ((width<620 && count>5) || (width-110)/Math.max(1,count)<40 ? "horizontal":"vertical") : orientation;
  const availableHeight=Math.max(260,Math.min(expanded?viewportHeight-190:viewportHeight*.4,expanded?900:460));
  return {width,height:Math.round(direction==="horizontal"?Math.max(availableHeight,count*27+100):availableHeight),orientation:direction};
}
function comparisonLayout(availableWidth, viewportHeight, count, analysis, expanded=false) {
  // Keep monthly comparisons on one common vertical plot at every screen size.
  return chartLayout(analysis==="monthly"?Math.max(1100,availableWidth):availableWidth,
    viewportHeight,count,analysis==="monthly"?"vertical":"auto",expanded);
}
function visibleChartHeight(viewportHeight,chartTop,noteHeight,expanded=false) {
  const minimum=expanded?300:340;
  return Math.round(Math.max(minimum,Math.min(760,viewportHeight-Math.max(0,chartTop)-noteHeight-38)));
}
if (typeof module !== "undefined" && module.exports) module.exports = {periodDelta,stackHours,periodGroups,chartLayout,comparisonLayout,visibleChartHeight};

function comparisonBuckets(periods,analysis) {
  if(analysis!=="monthly")return periods.map(row=>({label:row.label,rows:[row]}));
  const names=["Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar","Apr","May","Jun"];
  return names.map((label,index)=>({label,rows:[
    periods.find(row=>row.month_index===index&&row.role==="previous"),
    periods.find(row=>row.month_index===index&&row.role==="current")].filter(Boolean)}));
}
if(typeof module!=="undefined"&&module.exports)module.exports.comparisonBuckets=comparisonBuckets;

if (typeof document !== "undefined" && document.getElementById("period-series")) {
  const periods=JSON.parse(document.getElementById("period-series").textContent);
  const groups=JSON.parse(document.getElementById("period-groups").textContent);
  const scope=JSON.parse(document.getElementById("period-scope").textContent);
  const buckets=comparisonBuckets(periods,scope.analysis),paired=scope.analysis==="monthly";
  const dialog=document.getElementById("period-details"),search=document.getElementById("period-search"),more=document.getElementById("period-more");
  const num=value=>value===null?"--":Number(value).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
  const compact=value=>Number(value).toLocaleString(undefined,{notation:"compact",maximumFractionDigits:1});
  let selected=[],limit=100;
  function renderDetails(){
    const term=search.value.trim().toLocaleLowerCase();
    const matches=selected.filter(row=>!term||[row.month,row.unit,row.department,row.worker].join(" ").toLocaleLowerCase().includes(term));
    const fragment=document.createDocumentFragment();
    matches.slice(0,limit).forEach(row=>{
      const tr=document.createElement("tr");
      [row.month.slice(0,7),row.unit,row.department,row.worker,row.records,num(row.net),num(row.overtime),num(row.total)].forEach((value,index)=>{
        const cell=document.createElement(index===0?"th":"td");cell.textContent=value;if(index===0)cell.scope="row";tr.append(cell);
      });
      const cell=document.createElement("td"),link=document.createElement("a");
      const year=Number(row.month.slice(0,4)),month=Number(row.month.slice(5,7));
      const last=new Date(Date.UTC(year,month,0)).toISOString().slice(0,10);
      const query=new URLSearchParams({analysis:"daily",start:row.month>scope.start?row.month:scope.start,
        end:last<scope.end?last:scope.end,unit:row.unit_filter,department:row.department_filter,
        worker:row.worker_filter,direct:row.direct_filter});
      link.href="/hr-hours?"+query.toString();link.textContent="View employees";cell.append(link);tr.append(cell);fragment.append(tr);
    });
    if(!matches.length){const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=9;td.textContent="No records for this selection.";tr.append(td);fragment.append(tr);}
    document.getElementById("period-rows").replaceChildren(fragment);more.hidden=matches.length<=limit;
    document.getElementById("period-detail-count").textContent="Showing "+Math.min(limit,matches.length)+" of "+matches.length+" unit/department groups. All hours are included.";
  }
  function openPeriod(key,title){
    selected=key==="current-ytd"?groups.filter(row=>row.month>=scope.current_start):
      key?periodGroups(groups,periods.find(row=>row.key===key)):groups;
    document.getElementById("period-detail-title").textContent=title;limit=100;search.value="";renderDetails();dialog.showModal();dialog.querySelector(".hr-detail-table").scrollTop=0;
  }
  document.querySelectorAll("[data-period]").forEach(button=>button.addEventListener("click",()=>openPeriod(button.dataset.period,button.textContent.trim())));
  document.querySelectorAll("[data-current-year]").forEach(button=>button.addEventListener("click",()=>openPeriod("current-ytd",button.dataset.title)));
  search.addEventListener("input",()=>{limit=100;renderDetails();});more.addEventListener("click",()=>{limit+=100;renderDetails();});
  const ns="http://www.w3.org/2000/svg";
  function element(name,attrs={},content){const node=document.createElementNS(ns,name);for(const[key,value]of Object.entries(attrs))node.setAttribute(key,value);if(content!==undefined)node.textContent=content;return node;}
  const chart=document.getElementById("period-chart"),focusDialog=document.getElementById("chart-focus"),panel=document.getElementById("hours-chart-panel"),expand=document.getElementById("chart-expand");
  const placeholder=document.createComment("hours chart home");panel.before(placeholder);
  let lastLayout="",pendingFrame=false;
  function schedule(){if(pendingFrame)return;pendingFrame=true;requestAnimationFrame(()=>{pendingFrame=false;draw();});}
  function draw(){
    const availableWidth=chart.clientWidth;if(!availableWidth)return;
    const layout=comparisonLayout(availableWidth,window.innerHeight,paired?24:buckets.length,scope.analysis,focusDialog.open);
    const width=layout.width;
    const horizontal=layout.orientation==="horizontal";
    const chartTop=chart.getBoundingClientRect().top-(focusDialog.open?focusDialog.getBoundingClientRect().top:0);
    const noteHeight=panel.querySelector('.hr-note')?.getBoundingClientRect().height||48;
    const screenHeight=focusDialog.open?focusDialog.clientHeight:window.innerHeight;
    const fittedHeight=Math.max(paired?480:0,visibleChartHeight(screenHeight,chartTop,noteHeight,focusDialog.open));
    const height=horizontal?Math.max(fittedHeight,buckets.length*(paired?128:78)+70):fittedHeight;
    const key=[width,height,horizontal,focusDialog.open].join(":");if(lastLayout===key)return;lastLayout=key;chart.replaceChildren();
    if(!periods.some(row=>row.has_data)){const note=document.createElement("p");note.className="hr-empty";note.textContent="No hours match the selected filters.";chart.append(note);return;}
    const left=horizontal?78:90,right=horizontal?20:18,top=horizontal?24:30,bottom=height-(horizontal?55:155),plotWidth=Math.max(1,width-left-right);
    const values=periods.filter(row=>row.has_data).flatMap(row=>[Number(row.net),Number(row.total)]);
    let high=Math.max(0,...values),low=Math.min(0,...values);if(high===low)high=low+1;else{if(high>0)high*=1.08;if(low<0)low*=1.08;}
    const span=high-low,scale=value=>horizontal?left+(value-low)/span*plotWidth:top+(high-value)/span*(bottom-top);
    const category=paired?"Month (July to June)":"Fiscal year (July to June)",xName=horizontal?"Hours":category,yName=horizontal?category:"Hours";
    const svg=element("svg",{width:"100%",height,viewBox:`0 0 ${width} ${height}`,role:"group","aria-label":paired?"Current fiscal year versus previous fiscal year by month":"All available fiscal years including current year to date"});
    svg.append(element("title",{},"Working hours, overtime and total hours. X axis: "+xName+". Y axis: "+yName));
    const defs=element("defs"),pattern=element("pattern",{id:"negative-hours",patternUnits:"userSpaceOnUse",width:6,height:6});pattern.append(element("rect",{width:6,height:6,fill:"#ffc15c"}));pattern.append(element("path",{d:"M0,6 L6,0",stroke:"#6e4b20","stroke-width":2}));defs.append(pattern);svg.append(defs);
    const slot=(horizontal?bottom-top:plotWidth)/Math.max(1,buckets.length);
    for(let index=0;index<=4;index++){
      const value=low+span*index/4,point=scale(value);
      svg.append(element("line",horizontal?{x1:point,y1:top,x2:point,y2:bottom,class:"chart-grid"}:{x1:left,y1:point,x2:width-right,y2:point,class:"chart-grid"}));
      svg.append(element("text",horizontal?{x:point,y:bottom+20,"text-anchor":"middle",class:"chart-axis"}:{x:left-9,y:point+4,"text-anchor":"end",class:"chart-axis"},compact(value)));
    }
    svg.append(element("path",{d:`M${left},${top} V${bottom} H${width-right}`,class:"chart-axis-line",fill:"none"}));
    svg.append(element("line",horizontal?{x1:scale(0),y1:top,x2:scale(0),y2:bottom,class:"chart-zero"}:{x1:left,y1:scale(0),x2:width-right,y2:scale(0),class:"chart-zero"}));
    svg.append(element("text",{x:left+plotWidth/2,y:height-10,"text-anchor":"middle",class:"chart-axis-title"},xName));
    svg.append(element("text",{x:17,y:(top+bottom)/2,transform:`rotate(-90 17 ${(top+bottom)/2})`,"text-anchor":"middle",class:"chart-axis-title"},yName));
    if(!horizontal){for(const[label,offset,color]of[["Working",42,"net"],["Overtime",63,"overtime"],["Total",84,"total"]])svg.append(element("text",{x:left-10,y:bottom+offset,"text-anchor":"end",class:"bar-value-label "+color},label));}
    buckets.forEach((bucket,index)=>{
      const groupStart=(horizontal?top:left)+slot*index;
      const groupCentre=groupStart+slot/2;
      if(paired&&index)svg.append(element("line",{x1:groupStart,y1:top,x2:groupStart,y2:bottom+126,class:"month-pair-divider"}));
      if(!paired&&horizontal)svg.append(element("text",{x:left,y:groupStart+12,class:"simple-month-label"},bucket.label));
      bucket.rows.forEach((row,barIndex)=>{
        const centre=horizontal?groupStart+(paired?43+barIndex*44:32):groupStart+slot*(paired?(barIndex === 0 ? 0.25 : 0.75):.5);
        const barSize=horizontal?20:Math.min(paired?46:84,slot*(paired ? 0.38 : 0.56));
        const cellWidth=paired?slot/2:slot;
        const labelNumber=value=>!horizontal&&cellWidth>=125?num(value):
          Number(value).toLocaleString(undefined,{notation:"compact",maximumFractionDigits:horizontal&&plotWidth<240?0:1});
        const roleLabel=paired?(row.role==="current"?"This":"Last"):(row.role==="current"?"YTD":"");
        if(row.has_data){
          const stack=stackHours(row.net,row.overtime),bar=element("g",{class:"stacked-period "+(row.role==="current"?"current-fy-bar":"previous-fy-bar"),tabindex:0,role:"button","data-period-key":row.key,"aria-label":row.label+", "+row.fiscal_year+": Working "+num(row.net)+", overtime "+num(row.overtime)+", total "+num(row.total)+" hours"});
          bar.append(element("title",{},row.label+" | "+row.fiscal_year+(row.partial?" (to date)":"")+" | Working: "+num(row.net)+" | Overtime: "+num(row.overtime)+" | Total: "+num(row.total)));
          for(const component of["net","overtime"]){const segment=stack[component],a=scale(segment.from),b=scale(segment.to),length=segment.to-segment.from;
            bar.append(element("rect",{...(horizontal?{x:Math.min(a,b),y:centre-barSize/2,width:length===0?0:Math.max(1,Math.abs(b-a)),height:barSize}:{x:centre-barSize/2,y:Math.min(a,b),width:barSize,height:length===0?0:Math.max(1,Math.abs(b-a))}),class:"period-bar "+component+(length<0?" correction":"")}));}
          const total=scale(stack.total);bar.append(element("line",horizontal?{x1:total,y1:centre-barSize/2-2,x2:total,y2:centre+barSize/2+2,class:"stack-total-marker"}:{x1:centre-barSize/2-2,y1:total,x2:centre+barSize/2+2,y2:total,class:"stack-total-marker"}));
          for(const[component,offset,prefix]of[["net",42,"Working "],["overtime",63,"OT "],["total",84,"Total "]]){
            const attrs=horizontal?{x:left+plotWidth*(["net","overtime","total"].indexOf(component))/3,y:centre+22,class:"bar-value "+component}:{x:centre,y:bottom+offset,"text-anchor":"middle",class:"bar-value "+component};
            bar.append(element("text",attrs,(horizontal?(prefix==="Working "&&plotWidth<240?"Work ":prefix):"")+labelNumber(row[component])));
          }
          bar.addEventListener("click",()=>openPeriod(row.key,row.label+" | "+row.fiscal_year));bar.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();openPeriod(row.key,row.label+" | "+row.fiscal_year);}});svg.append(bar);
        }else{
          svg.append(element("text",horizontal?{x:left+6,y:centre+4,class:"chart-axis"}:{x:centre,y:bottom-10,"text-anchor":"middle",class:"chart-axis"},row.upcoming?"Not yet":"No data"));
          if(!horizontal)for(const offset of[42,63,84])svg.append(element("text",{x:centre,y:bottom+offset,"text-anchor":"middle",class:"bar-value missing"},"--"));
        }
        if(roleLabel)svg.append(element("text",horizontal?{x:left-8,y:centre+4,"text-anchor":"end",class:"bar-year-label"}:{x:centre,y:bottom+21,"text-anchor":"middle",class:"bar-year-label"},roleLabel+(row.partial?" *":"")));
      });
      if(!horizontal){
        svg.append(element("text",{x:groupCentre,y:bottom+114,"text-anchor":"middle",class:"simple-month-label"},bucket.label));
        if(!paired&&index)svg.append(element("line",{x1:groupStart,y1:bottom+9,x2:groupStart,y2:bottom+91,class:"simple-value-divider"}));
      }
    });
    chart.append(svg);
  }
  expand.addEventListener("click",()=>{if(focusDialog.open){focusDialog.close();return;}focusDialog.append(panel);expand.textContent="Close expanded graph";focusDialog.showModal();lastLayout="";schedule();});
  focusDialog.addEventListener("close",()=>{placeholder.after(panel);expand.textContent="Expand graph";lastLayout="";schedule();expand.focus();});
  document.querySelector('.hr-simple-filters')?.addEventListener('toggle',()=>{lastLayout="";schedule();});
  window.addEventListener("resize",schedule);if(typeof ResizeObserver!=="undefined")new ResizeObserver(schedule).observe(chart);schedule();
}
