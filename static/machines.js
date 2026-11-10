"use strict";
document.querySelectorAll('[data-dialog]').forEach(tile => tile.addEventListener('click', () => document.getElementById(tile.dataset.dialog).showModal()));
document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('click', event => {
  const rect = dialog.getBoundingClientRect();
  if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
}));
document.querySelectorAll('#machine-filters,[data-auto-filter]').forEach(form => form.addEventListener('change', () => form.requestSubmit()));
const clock = document.getElementById('wall-clock');
const formatter = new Intl.DateTimeFormat('en-GB', {timeZone:'Asia/Karachi',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
function tick() { if (clock) { const now=new Date(); clock.textContent=formatter.format(now)+' PKT'; clock.dateTime=now.toISOString(); } }
tick(); setInterval(tick,1000);
const settingsElement = document.getElementById('wall-settings');
const wallSettings = settingsElement ? JSON.parse(settingsElement.textContent) : null;
document.querySelectorAll('.wall-grid').forEach(grid => {
  function fitTiles() {
    const count = grid.querySelectorAll('.wall-tile').length;
    const width=grid.clientWidth, height=grid.clientHeight;
    if (!count || !width || !height || !wallSettings) return;
    const gap=Number(width<Number(wallSettings.compact_breakpoint_pixels) ? wallSettings.compact_gap_pixels : wallSettings.gap_pixels);
    let best=null;
    for (let cols=1;cols<=count;cols+=1) {
      const rows=Math.ceil(count/cols),w=(width-(cols-1)*gap)/cols,h=(height-(rows-1)*gap)/rows;
      if (w<=0 || h<=0) continue;
      const scale=Math.min(w/Number(wallSettings.reference_tile_width),h/Number(wallSettings.reference_tile_height));
      const score=scale-(cols*rows-count)/count*0.03;
      if (!best || score>best.score) best={cols,rows,scale,score};
    }
    if (!best) return;
    grid.style.setProperty('--cols',best.cols); grid.style.setProperty('--rows',best.rows); grid.style.setProperty('--gap',gap+'px');
    const scale=Math.min(best.scale,Number(wallSettings.max_font_scale));
    for (const [name,base] of Object.entries({'name-size':28,'time-size':23,'person-size':21,'unit-size':18,'label-size':11,'pad':20,'field-gap':9})) grid.style.setProperty('--'+name,base*scale+'px');
  }
  new ResizeObserver(fitTiles).observe(grid); fitTiles();
});
const seconds=Number(document.body.dataset.refreshSeconds);
if (Number.isFinite(seconds) && seconds>=10) {
  const refreshAt=Date.now()+seconds*1000;
  let reloading=false;
  setInterval(() => {
    if (!reloading && Date.now()>=refreshAt && !document.hidden && !document.querySelector('dialog[open]')) {
      reloading=true;
      location.reload();
    }
  },1000);
}
