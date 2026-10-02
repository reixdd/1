const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];
const state = {
  overview:null, radar:[], selected:null, dossier:null, chart:null, radarTab:'core', workTab:'overview',
  lastAttention:null, gmgnHot:null, gmgnNew:null, chartBasis:'market_cap', sound:false, speak:false,
  notificationPermission: ('Notification' in window ? Notification.permission : 'unsupported'), refreshBusy:false, dossierBusy:false,
};
const esc = v => String(v ?? '').replace(/[&<>'"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const num = v => { const n=Number(v); return Number.isFinite(n)?n:null };
const fmt = v => {
  const n=num(v); if(n===null)return '—'; const a=Math.abs(n);
  if(a>=1e9)return '$'+(n/1e9).toFixed(a>=1e11?0:2)+'B';
  if(a>=1e6)return '$'+(n/1e6).toFixed(a>=1e8?0:2)+'M';
  if(a>=1e3)return '$'+(n/1e3).toFixed(a>=1e5?0:1)+'K';
  if(a>=1)return '$'+n.toFixed(2); if(a===0)return '$0';
  return '$'+n.toPrecision(3);
};
const short = (v,n=8) => { const s=String(v||''); return s.length<=n*2+3?s:s.slice(0,n)+'…'+s.slice(-n); };
const age = sec => { const n=num(sec); if(n===null||n<0)return '—'; if(n<60)return Math.round(n)+'s'; if(n<3600)return Math.round(n/60)+'m'; if(n<86400)return (n/3600).toFixed(1)+'h'; return (n/86400).toFixed(1)+'d'; };
const pct = v => { const n=num(v); return n===null?'—':`${n>=0?'+':''}${n.toFixed(1)}%`; };
const ago = t => { const n=num(t); return n?age(Date.now()/1000-n)+' ago':'—'; };
const clamp = (n,a,b)=>Math.max(a,Math.min(b,n));

async function api(url, options={}){
  const ctl=new AbortController(); const timeout=setTimeout(()=>ctl.abort(), options.timeout||20000);
  try{
    const res=await fetch(url,{...options,signal:ctl.signal,headers:{'Content-Type':'application/json',...(options.headers||{})}});
    if(!res.ok){let text='';try{text=(await res.json()).detail||''}catch{text=await res.text()}throw new Error(`${res.status} ${text}`.trim())}
    return await res.json();
  } finally { clearTimeout(timeout); }
}
function toast(text, ms=2600){ const el=$('#toast'); el.textContent=text;el.classList.remove('hidden');clearTimeout(el._timer);el._timer=setTimeout(()=>el.classList.add('hidden'),ms); }
function setStatus(id,label,kind=''){const el=$(id);if(!el)return;el.className='status '+kind;el.innerHTML=`<i></i> ${esc(label)}`;}
function playCue(kind='tick'){
  if(!state.sound)return;
  try{const C=window.AudioContext||window.webkitAudioContext;const ctx=new C();const o=ctx.createOscillator();const g=ctx.createGain();o.type='sine';o.frequency.value=kind==='attention'?620:kind==='select'?340:480;g.gain.setValueAtTime(.025,ctx.currentTime);g.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+.12);o.connect(g);g.connect(ctx.destination);o.start();o.stop(ctx.currentTime+.13);}catch{}
}
function maybeSpeak(text){if(!state.speak||!('speechSynthesis' in window))return; speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text.slice(0,1200));u.rate=1.08;u.pitch=.92;speechSynthesis.speak(u);}

function boot(){
  const savedSound=localStorage.getItem('jarvisSound')==='1';state.sound=savedSound;$('#soundButton').textContent=state.sound?'SOUND ON':'SOUND OFF';$('#soundButton').classList.toggle('active',state.sound);
  const savedSpeak=localStorage.getItem('jarvisSpeak')==='1';state.speak=savedSpeak;$('#speakButton').textContent=state.speak?'VOICE ON':'VOICE OFF';
  setInterval(()=>$('#clock').textContent=new Date().toLocaleTimeString([],{hour12:false}),500);
  bind(); refresh(true).then(()=>{setTimeout(()=>{$('#boot').classList.add('hidden');$('#app').classList.remove('hidden')},250)}).catch(err=>{document.querySelector('#boot div').textContent='CORE UNAVAILABLE · '+err.message});
  setInterval(()=>refresh(false),4000);
}

function bind(){
  $$('.radar-tabs button').forEach(b=>b.onclick=()=>{state.radarTab=b.dataset.radarTab;$$('.radar-tabs button').forEach(x=>x.classList.toggle('active',x===b));renderRadar();if(state.radarTab==='gmgn-hot')loadGmgn('hot');if(state.radarTab==='gmgn-new')loadGmgn('new')});
  $$('.workspace-tabs button').forEach(b=>b.onclick=()=>{state.workTab=b.dataset.workTab;$$('.workspace-tabs button').forEach(x=>x.classList.toggle('active',x===b));renderDetails()});
  $('#searchForm').onsubmit=async e=>{e.preventDefault();await searchToken()};
  $('#watchButton').onclick=toggleWatch; $('#copyButton').onclick=copyContract;
  $('#contractButton').onclick=copyContract;
  $('#dexButton').onclick=()=>openExternal(`https://dexscreener.com/search?q=${encodeURIComponent(state.dossier?.market?.contract||'')}`);
  $('#xButton').onclick=()=>{const d=state.dossier;const q=d?.market?.symbol?`$${d.market.symbol} ${d.market.contract}`:d?.market?.contract||'';openExternal(`https://x.com/search?q=${encodeURIComponent(q)}&src=typed_query&f=live`)};
  $('#gmgnEnrich').onclick=()=>loadDossier(state.selected,true,true);
  $('#chartMc').onclick=()=>{state.chartBasis='market_cap';$('#chartMc').classList.add('active');$('#chartPrice').classList.remove('active');renderChart()};
  $('#chartPrice').onclick=()=>{state.chartBasis='price';$('#chartPrice').classList.add('active');$('#chartMc').classList.remove('active');renderChart()};
  $('#chatForm').onsubmit=e=>{e.preventDefault();sendChat()};
  $$('.quick-prompts button').forEach(b=>b.onclick=()=>{$('#chatInput').value=b.dataset.prompt;sendChat()});
  $('#micButton').onclick=startMic;
  $('#soundButton').onclick=()=>{state.sound=!state.sound;localStorage.setItem('jarvisSound',state.sound?'1':'0');$('#soundButton').textContent=state.sound?'SOUND ON':'SOUND OFF';$('#soundButton').classList.toggle('active',state.sound);playCue('select')};
  $('#speakButton').onclick=()=>{state.speak=!state.speak;localStorage.setItem('jarvisSpeak',state.speak?'1':'0');$('#speakButton').textContent=state.speak?'VOICE ON':'VOICE OFF'};
  $('#alertsButton').onclick=enableAlerts; $('#systemButton').onclick=()=>openDrawer('systemDrawer'); $('#activityExpand').onclick=()=>openDrawer('activityDrawer');
  $$('[data-close]').forEach(b=>b.onclick=()=>$('#'+b.dataset.close).classList.add('hidden'));
}
function openExternal(url){ if(/^https:\/\//i.test(url))window.open(url,'_blank','noopener,noreferrer'); }
function openDrawer(id){$('#'+id).classList.remove('hidden');if(id==='systemDrawer')renderSystem();if(id==='activityDrawer')renderActivityDrawer()}

async function refresh(first=false){
  if(state.refreshBusy)return;state.refreshBusy=true;
  try{
    const [overview,radar,attention]=await Promise.all([
      api('/api/operator/overview',{timeout:12000}),api('/api/operator/radar?limit=120',{timeout:12000}),api('/api/attention?limit=60',{timeout:12000})
    ]);
    state.overview=overview;state.radar=radar.items||[];
    setStatus('#coreStatus',overview.pipeline?.end_to_end_live?'CORE LIVE':'CORE DEGRADED',overview.pipeline?.end_to_end_live?'live':'warn');
    const gs=overview.gmgn?.state||'UNKNOWN';setStatus('#gmgnStatus',`GMGN ${gs}`,gs==='READY'?'live':gs==='COOLING'?'warn':gs==='NO_CLI'||gs==='NO_KEY'?'warn':'bad');
    const oa=overview.ollama?.available??overview.agents?.ollama_available;setStatus('#ollamaStatus',oa?'OLLAMA LIVE':'OLLAMA OFF',oa?'live':'warn');
    const st=overview.pipeline?.stages||{};$('#systemLine').textContent=`OBS ${st.provider_observations||0} · QUANT ${st.quant_evaluations||0} · EXP ${st.experiments||0} · LABELS ${st.online_labels||0} · MODEL ${st.online_updates||0}`;
    const top=state.radar[0];$('#catLine').textContent=top?`[=^._.^=] ${top.symbol||short(top.contract,4)} · ${fmt(top.market_cap)} · ${top.category}`:'[=^._.^=] watching the tape';
    $('#radarCount').textContent=`${radar.eligible||0} LIVE`;
    $('#jarvisPresence').textContent=overview.agents?.ollama_available?'ONLINE':'CORE ONLY';
    $('#jarvisModeLabel').textContent=overview.agents?.ollama_available?'LOCAL AGENT TEAM':'AGENTS OFFLINE';
    renderRadar(); updateAttention(attention.items||[],first);
    if(state.selected && !state.dossierBusy) await loadDossier(state.selected,false,false,true);
    if(!state.selected && state.radar.length && first) selectToken(state.radar[0].identity_key);
  }catch(err){setStatus('#coreStatus','CORE ERROR','bad');$('#systemLine').textContent='WORKBENCH REFRESH ERROR · '+err.message}
  finally{state.refreshBusy=false}
}

function filteredRadar(){
  if(state.radarTab==='surging')return state.radar.filter(r=>r.live_eligible!==false&&(r.category==='SURGING'||(num(r.quant?.rank_velocity_per_min)||0)>0.5));
  if(state.radarTab==='watched')return state.radar.filter(r=>r.watching);
  return state.radar.filter(r=>r.live_eligible!==false);
}
function renderRadar(){
  const list=$('#radarList');
  if(state.radarTab==='gmgn-hot'||state.radarTab==='gmgn-new'){renderGmgnList();return}
  const rows=filteredRadar();
  if(!rows.length){list.innerHTML='<div class="empty">No markets in this view right now.</div>';return}
  list.innerHTML=rows.map(r=>{
    const q=r.quant||{};const reason=(r.why_surfaced||[])[0]||'fresh market observation';
    return `<button class="token-row ${r.identity_key===state.selected?'selected':''}" data-id="${esc(r.identity_key)}">
      <span class="token-main"><strong>${esc(r.symbol||short(r.contract,5))}<i class="badge ${r.category==='SURGING'||r.category==='ATTENTION'?'hot':''}">${esc(r.category)}</i></strong><small>${esc(String(r.chain||'').toUpperCase())} · ${age(r.age_seconds)} · ${r.live_eligible===false?'HISTORY · ':''}${esc(short(r.contract,4))}</small></span>
      <span class="token-metrics"><b>${fmt(r.market_cap)}</b><small>L ${fmt(r.liquidity)}</small></span>
      <span class="token-why"><span>${esc(reason)}</span><small>${q.rank?'#'+q.rank:'rank —'} ${num(q.rank_velocity_per_min)!==null?'· '+(num(q.rank_velocity_per_min)>=0?'+':'')+num(q.rank_velocity_per_min).toFixed(1)+'/m':''}</small></span>
    </button>`
  }).join('');
  $$('.token-row',list).forEach(b=>b.onclick=()=>selectToken(b.dataset.id));
  $('#radarFoot').textContent='Attention ordering surfaces novelty and evidence changes only — not a buy/sell score.';
}
async function loadGmgn(kind){
  const key=kind==='hot'?'gmgnHot':'gmgnNew'; if(state[key]?.loading)return;state[key]={loading:true};renderGmgnList();
  const chain=$('#searchChain').value;
  try{state[key]=kind==='hot'?await api(`/api/operator/gmgn/trending?chain=${encodeURIComponent(chain)}&interval=5m&limit=40`,{timeout:35000}):await api(`/api/operator/gmgn/trenches?chain=${encodeURIComponent(chain)}&limit=50`,{timeout:35000})}
  catch(err){state[key]={ok:false,error:err.message}}
  renderGmgnList();
}
function walkObjects(node,out=[]){
  if(Array.isArray(node)){node.forEach(x=>walkObjects(x,out));return out}
  if(!node||typeof node!=='object')return out;
  const addr=node.address||node.token_address||node.contract_address||node.tokenAddress;
  const symbol=node.symbol||node.token_symbol||node.base_symbol;
  if(addr&&(symbol||node.name))out.push(node);
  Object.values(node).forEach(v=>{if(v&&typeof v==='object')walkObjects(v,out)});return out;
}
function renderGmgnList(){
  const list=$('#radarList'),blob=state.radarTab==='gmgn-hot'?state.gmgnHot:state.gmgnNew;
  if(!blob||blob.loading){list.innerHTML='<div class="empty">Querying the official GMGN read-only CLI…</div>';return}
  if(!blob.ok){list.innerHTML=`<div class="empty">GMGN ${esc(blob.state||'unavailable')}<br>${esc(blob.error||'Check GMGN status in SYSTEM.')}</div>`;return}
  const rows=walkObjects(blob.data).slice(0,80); if(!rows.length){list.innerHTML='<div class="empty">GMGN returned data, but no token rows were recognized by the display adapter.</div>';return}
  list.innerHTML=rows.map((r,i)=>{const addr=r.address||r.token_address||r.contract_address||r.tokenAddress;const sym=r.symbol||r.token_symbol||r.name||'TOKEN';const mc=r.market_cap||r.marketcap||r.mc;const liq=r.liquidity||r.liquidity_usd;return `<button class="token-row gmgn-row" data-address="${esc(addr)}"><span class="token-main"><strong>${esc(sym)}<i class="badge">GMGN</i></strong><small>${esc($('#searchChain').value.toUpperCase())} · ${esc(short(addr,4))}</small></span><span class="token-metrics"><b>${fmt(mc)}</b><small>L ${fmt(liq)}</small></span><span class="token-why"><span>${state.radarTab==='gmgn-hot'?'GMGN 5m trending':'GMGN new creation'}</span><small>read-only source</small></span></button>`}).join('');
  $$('.gmgn-row',list).forEach(b=>b.onclick=()=>selectByContract($('#searchChain').value,b.dataset.address,true));
  $('#radarFoot').textContent='GMGN tab is an optional read-only source. Canonical JARVIS state remains provider-neutral.';
}

async function selectToken(identity){state.selected=identity;playCue('select');renderRadar();await loadDossier(identity,false,false)}
async function selectByContract(chain,contract,gmgnFallback=false){
  const local=state.radar.find(r=>String(r.chain)===String(chain)&&String(r.contract).toLowerCase()===String(contract).toLowerCase());
  if(local)return selectToken(local.identity_key);
  if(gmgnFallback)return loadGmgnOnly(chain,contract);
  toast('Token is not in the current canonical JARVIS universe.');
}
async function loadDossier(identity,gmgn=false,holders=false,silent=false){
  if(!identity)return;state.dossierBusy=true;
  try{
    const [d,c]=await Promise.all([api(`/api/operator/dossier?identity_key=${encodeURIComponent(identity)}&gmgn=${gmgn?'true':'false'}&holders=${holders?'true':'false'}`,{timeout:gmgn?50000:15000}),api(`/api/operator/chart?identity_key=${encodeURIComponent(identity)}&limit=500`,{timeout:15000})]);
    state.dossier=d;state.chart=c;renderToken();
    if(gmgn&&!silent)toast(d.gmgn?.error?'GMGN enrichment returned an error.':'GMGN token evidence loaded.');
  }catch(err){if(!silent)toast('Dossier error: '+err.message)}finally{state.dossierBusy=false}
}
async function loadGmgnOnly(chain,contract){
  $('#noSelection').classList.add('hidden');$('#tokenView').classList.remove('hidden');state.selected=null;state.chart={points:[]};
  try{
    const bundle=await api(`/api/operator/gmgn/token?chain=${encodeURIComponent(chain)}&address=${encodeURIComponent(contract)}&holders=false`,{timeout:50000});
    state.dossier={found:false,gmgn_only:true,market:{chain,contract,symbol:findDeep(bundle,'symbol')||'GMGN',name:findDeep(bundle,'name')||'GMGN token'},gmgn:bundle,synthesis:{what_changed:['GMGN-only lookup; this token is not yet in the canonical JARVIS market tape.'],support:[],counter_evidence:[],unknowns:['No canonical Quant/experiment history is available yet.']},risk:{evidence:[],conflicts:[],unknown_fields:[]},graph:{edges:[]},social:{mentions:[]},experiments:{open:[],recent:[]},quant:{history:[]},source_links:[],watching:false};
    renderToken();state.workTab='gmgn';$$('.workspace-tabs button').forEach(x=>x.classList.toggle('active',x.dataset.workTab==='gmgn'));renderDetails();
  }catch(err){toast('GMGN lookup failed: '+err.message)}
}
function findDeep(node,key){if(!node||typeof node!=='object')return null;if(node[key]!=null)return node[key];for(const v of Object.values(node)){if(v&&typeof v==='object'){const found=findDeep(v,key);if(found!=null)return found}}return null}

function renderToken(){
  const d=state.dossier;if(!d)return;const m=d.market||{},q=d.quant?.latest||{};
  $('#noSelection').classList.add('hidden');$('#tokenView').classList.remove('hidden');
  $('#tokenSymbol').textContent=m.symbol||short(m.contract,5)||'TOKEN';$('#tokenName').textContent=m.name||'Unnamed token';$('#tokenChain').textContent=String(m.chain||'').toUpperCase();$('#tokenMonogram').textContent=(m.symbol||'?').slice(0,2).toUpperCase();$('#contractButton').textContent=m.contract||'—';
  $('#selectedContext').textContent=`${m.symbol||'TOKEN'} · ${String(m.chain||'').toUpperCase()} · ${short(m.contract,5)}`;
  $('#tokenState').textContent=d.gmgn_only?'GMGN ONLY · NOT CANONICAL':(m.observation_age_seconds<=180?'LIVE CANONICAL':'KNOWN / AGING');
  $('#mc').textContent=fmt(m.market_cap);$('#liq').textContent=fmt(m.liquidity);$('#vol5').textContent=fmt(m.volume_5m);$('#txns').textContent=`${m.buys_5m??'—'} / ${m.sells_5m??'—'}`;$('#age').textContent=age(m.age_seconds);$('#freshness').textContent=m.observation_age_seconds!=null?`observed ${age(m.observation_age_seconds)} ago`:'freshness unknown';
  $('#rank').textContent=q.rank?`#${q.rank}`:'—';const rv=num(q.rank_velocity_per_min);$('#rankVel').textContent=rv===null?'velocity —':`${rv>=0?'+':''}${rv.toFixed(1)} / min`;$('#rankVel').className=rv>0?'positive':rv<0?'negative':'';
  const im=num(q.buy_sell_imbalance);$('#imbalance').textContent=im===null?'imbalance —':`imbalance ${(im*100).toFixed(0)}%`;$('#imbalance').className=im>0.25?'positive':im<-.25?'negative':'';
  const liq=num(m.liquidity),vol=num(m.volume_5m);$('#turnover').textContent=liq&&vol?`${(vol/liq).toFixed(2)}x liq turnover`:'turnover —';
  $('#mcDelta').textContent=m.price_change_5m_pct!=null?`${pct(m.price_change_5m_pct)} price 5m`:' ';$('#mcDelta').className=num(m.price_change_5m_pct)>0?'positive':num(m.price_change_5m_pct)<0?'negative':'';
  $('#liqDelta').textContent=`${m.provider_count||0} provider${m.provider_count===1?'':'s'}`;
  $('#watchButton').disabled=d.gmgn_only;$('#watchButton').textContent=d.watching?'★ WATCHING':'☆ WATCH';$('#copyButton').disabled=!m.contract;$('#dexButton').disabled=!m.contract;$('#xButton').disabled=!m.contract;
  renderList('#changed',d.synthesis?.what_changed);renderList('#support',d.synthesis?.support);renderList('#counter',d.synthesis?.counter_evidence);renderList('#unknown',d.synthesis?.unknowns);$('#briefTime').textContent=m.last_observed_at?ago(m.last_observed_at):'—';
  renderChart();renderDetails();
}
function renderList(sel,items){$(sel).innerHTML=(items?.length?items:['None recorded.']).map(x=>`<li>${esc(x)}</li>`).join('')}

function renderChart(){
  const el=$('#chart'),rows=(state.chart?.points||[]).filter(p=>num(p[state.chartBasis])!==null&&num(p.t)!==null);if(rows.length<2){el.innerHTML='<div class="empty">Not enough local observations for a line yet.</div>';return}
  const W=900,H=180,P=18;const vals=rows.map(p=>num(p[state.chartBasis]));let lo=Math.min(...vals),hi=Math.max(...vals);if(hi===lo){hi+=1;lo-=1}const t0=rows[0].t,t1=rows.at(-1).t||t0+1;
  const pts=rows.map(p=>{const x=P+(p.t-t0)/(t1-t0||1)*(W-2*P);const y=H-P-(num(p[state.chartBasis])-lo)/(hi-lo)*(H-2*P);return [x,y]}).filter(x=>Number.isFinite(x[0])&&Number.isFinite(x[1]));
  const line=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ');const area=`${line} L ${pts.at(-1)[0]} ${H-P} L ${pts[0][0]} ${H-P} Z`;
  el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><defs><linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#d7dfda" stop-opacity=".14"/><stop offset="1" stop-color="#d7dfda" stop-opacity="0"/></linearGradient></defs>${[.25,.5,.75].map(f=>`<line class="chart-grid" x1="${P}" y1="${H*f}" x2="${W-P}" y2="${H*f}"/>`).join('')}<path class="chart-area" d="${area}"/><path class="chart-line" d="${line}"/><circle class="chart-dot" cx="${pts.at(-1)[0]}" cy="${pts.at(-1)[1]}" r="3"/><text class="chart-label" x="${P}" y="12">${esc(state.chartBasis==='market_cap'?fmt(hi):String(hi.toPrecision(4)))}</text><text class="chart-label" x="${P}" y="${H-4}">${esc(state.chartBasis==='market_cap'?fmt(lo):String(lo.toPrecision(4)))}</text></svg>`;
}

function renderDetails(){
  const el=$('#detailPanel'),d=state.dossier;if(!d){el.innerHTML='';return}const m=d.market||{};
  if(state.workTab==='overview'){
    const links=(d.source_links||[]).map(x=>`<div class="evidence-row"><b>${esc(x.label)}</b><small>${esc(x.source||'source')}</small><button class="mini external-link" data-url="${esc(x.url)}">OPEN ↗</button></div>`).join('')||'<div class="empty">No profile/source links captured yet.</div>';
    el.innerHTML=`<div class="detail-grid"><div class="detail-box"><h3>CANONICAL STATE</h3>${kv({Provider:m.provider,'Provider count':m.provider_count,'Observations':m.observation_count,'Observed':m.last_observed_at?ago(m.last_observed_at):'—','Pool':short(m.pool,8)})}</div><div class="detail-box"><h3>SOURCE LINKS / BROWSER RESEARCH</h3>${links}</div></div>`;
  } else if(state.workTab==='security'){
    const r=d.risk||{},rows=(r.evidence||[]).slice(0,80).map(x=>`<div class="evidence-row"><b>${esc(x.field)} = ${esc(String(x.value))}</b><small>${esc(x.provider)} · ${esc(x.classification)} · ${ago(x.observed_at)}</small></div>`).join('');
    el.innerHTML=`<div class="detail-grid"><div class="detail-box"><h3>SECURITY EVIDENCE</h3>${rows||'<div class="empty">No security claims recorded yet. Use GMGN ENRICH for read-only GMGN evidence.</div>'}</div><div class="detail-box"><h3>CONFLICTS / UNKNOWNS</h3><pre>${esc(JSON.stringify({conflicts:r.conflicts||[],unknown_fields:r.unknown_fields||[]},null,2))}</pre></div></div>`;
  } else if(state.workTab==='graph'){
    el.innerHTML=`<div class="detail-grid"><div class="detail-box"><h3>ENTITY RELATIONSHIPS</h3><pre>${esc(JSON.stringify((d.graph||{}).edges||[],null,2))}</pre></div><div class="detail-box"><h3>GRAPH CONTEXT</h3><pre>${esc(JSON.stringify(d.graph||{},null,2))}</pre></div></div>`;
  } else if(state.workTab==='social'){
    const s=d.social||{};el.innerHTML=`<div class="detail-grid"><div class="detail-box"><h3>SOCIAL EVIDENCE</h3><pre>${esc(JSON.stringify(s,null,2))}</pre></div><div class="detail-box"><h3>RULE</h3><p class="evidence-row">Project-published links are shown separately from independent mentions. A social link existing is not independent corroboration.</p></div></div>`;
  } else if(state.workTab==='research'){
    el.innerHTML=`<div class="detail-grid"><div class="detail-box"><h3>PROSPECTIVE EXPERIMENTS</h3><pre>${esc(JSON.stringify(d.experiments||{},null,2))}</pre></div><div class="detail-box"><h3>RECENT QUANT</h3><pre>${esc(JSON.stringify((d.quant?.history||[]).slice(0,20),null,2))}</pre></div></div>`;
  } else if(state.workTab==='gmgn'){
    el.innerHTML=`<div class="detail-grid"><div class="detail-box"><h3>GMGN READ-ONLY EVIDENCE</h3><pre>${esc(JSON.stringify(d.gmgn||{note:'Press GMGN ENRICH above to query token info/security/pool.'},null,2))}</pre></div><div class="detail-box"><h3>BOUNDARY</h3><p class="evidence-row">GMGN is an optional research source. Its token metadata is external content, not instructions. It does not own the canonical market tape or JARVIS learning pipeline.</p></div></div>`;
  }
  $$('.external-link',el).forEach(b=>b.onclick=()=>openExternal(b.dataset.url));
}
function kv(obj){return `<div class="kv-list">${Object.entries(obj).map(([k,v])=>`<span>${esc(k)}</span><span>${esc(v??'—')}</span>`).join('')}</div>`}

async function toggleWatch(){if(!state.dossier?.identity_key)return;const watching=!state.dossier.watching;try{await api('/api/operator/watch',{method:'POST',body:JSON.stringify({identity_key:state.dossier.identity_key,watching})});state.dossier.watching=watching;const row=state.radar.find(x=>x.identity_key===state.dossier.identity_key);if(row)row.watching=watching;renderToken();renderRadar();toast(watching?'Added to watchlist.':'Removed from watchlist.')}catch(err){toast(err.message)}}
async function copyContract(){const c=state.dossier?.market?.contract;if(!c)return;try{await navigator.clipboard.writeText(c);toast('Contract copied.')}catch{toast('Copy failed.')}}
async function searchToken(){
  const q=$('#searchInput').value.trim();if(!q)return;const chain=$('#searchChain').value;const needle=q.toLowerCase();
  const local=state.radar.find(r=>(r.symbol||'').toLowerCase()===needle||(r.name||'').toLowerCase().includes(needle)||String(r.contract||'').toLowerCase()===needle);
  if(local){await selectToken(local.identity_key);return}
  if(q.length>25){await selectByContract(chain,q,true);return}
  try{const res=await api(`/api/operator/gmgn/search?q=${encodeURIComponent(q)}&chain=${encodeURIComponent(chain)}`,{timeout:35000});const rows=walkObjects(res.data);if(rows.length){const r=rows[0];const addr=r.address||r.token_address||r.contract_address||r.tokenAddress;toast(`GMGN found ${r.symbol||r.name||'a token'}; opening read-only evidence.`);await selectByContract(chain,addr,true)}else toast('No local or GMGN result found.')}catch(err){toast('Search failed: '+err.message)}
}

function chatMessage(role,text,thinking=false){const log=$('#chatLog'),el=document.createElement('div');el.className='message '+(role==='user'?'user-msg':role==='jarvis'?'jarvis-msg':'system-msg');el.innerHTML=`<b>${role==='user'?'YOU':role==='jarvis'?'JARVIS':'SYSTEM'}</b><p${thinking?' class="thinking"':''}></p>`;el.querySelector('p').textContent=text;log.appendChild(el);log.scrollTop=log.scrollHeight;return el.querySelector('p')}
async function sendChat(){
  const input=$('#chatInput'),message=input.value.trim();if(!message||$('#chatForm').dataset.busy==='1')return;input.value='';chatMessage('user',message);const target=chatMessage('jarvis','',true);$('#chatForm').dataset.busy='1';$('#chatState').textContent='THINKING';
  try{
    const res=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,identity_key:state.dossier?.identity_key||state.selected||null,mode:$('#chatMode').value})});
    if(!res.ok)throw new Error(res.status+' '+await res.text());const reader=res.body.getReader(),dec=new TextDecoder();let buf='',answer='';
    while(true){const {done,value}=await reader.read();if(done)break;buf+=dec.decode(value,{stream:true});let idx;while((idx=buf.indexOf('\n'))>=0){const line=buf.slice(0,idx).trim();buf=buf.slice(idx+1);if(!line)continue;let e;try{e=JSON.parse(line)}catch{continue}if(e.type==='heartbeat'){$('#chatState').textContent=`THINKING ${e.elapsed_s}s`}else if(e.type==='state'){$('#chatState').textContent='CHECKING EVIDENCE'}else if(e.type==='answer'){answer=e.text||'';target.classList.remove('thinking');target.textContent=answer;$('#chatState').textContent='READY';maybeSpeak(answer)}else if(e.type==='error'){target.classList.remove('thinking');target.textContent=e.text||'JARVIS error';$('#chatState').textContent='ERROR'}}}
    if(!answer&&!target.textContent){target.classList.remove('thinking');target.textContent='No answer returned.'}
  }catch(err){target.classList.remove('thinking');target.textContent='JARVIS is unavailable: '+err.message;$('#chatState').textContent='OFFLINE'}finally{$('#chatForm').dataset.busy='0';$('#chatLog').scrollTop=$('#chatLog').scrollHeight}
}
function startMic(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){toast('Speech recognition is not available in this Chrome build.');return}
  const rec=new SR();rec.lang='en-US';rec.interimResults=true;rec.maxAlternatives=1;const b=$('#micButton');b.classList.add('listening');b.textContent='■';let final='';
  rec.onresult=e=>{let interim='';for(let i=e.resultIndex;i<e.results.length;i++){const t=e.results[i][0].transcript;if(e.results[i].isFinal)final+=t;else interim+=t}$('#chatInput').value=(final||interim).trim()};rec.onerror=e=>toast('Microphone: '+e.error);rec.onend=()=>{b.classList.remove('listening');b.textContent='●'};try{rec.start()}catch(err){toast(err.message)}
}

function updateAttention(items,first){
  const latest=items[0];if(latest&&latest.packet_id!==state.lastAttention){const newOne=state.lastAttention!==null;state.lastAttention=latest.packet_id;const text=(latest.what_changed||[])[0]||(latest.trigger_reasons||[])[0]||'Research evidence changed.';$('#activity').innerHTML=`<span><b>${esc(short(latest.identity_key,10))}</b> · ${esc(text)}</span>`;if(newOne){playCue('attention');if(state.notificationPermission==='granted'&&document.hidden){new Notification('JARVIS · evidence changed',{body:text,tag:latest.packet_id})}}}
  state._attentionItems=items;if(first&&items.length)renderActivityDrawer();
}
async function enableAlerts(){if(!('Notification' in window)){toast('Browser notifications are unavailable.');return}try{const p=await Notification.requestPermission();state.notificationPermission=p;$('#alertsButton').classList.toggle('active',p==='granted');toast(p==='granted'?'Chrome alerts enabled.':'Notifications were not enabled.')}catch(err){toast(err.message)}}
function renderActivityDrawer(){const el=$('#activityContent'),rows=state._attentionItems||[];el.innerHTML=rows.length?rows.map(p=>`<div class="activity-item"><b>${esc(short(p.identity_key,12))} · ${esc(p.status)}</b><p>${esc((p.what_changed||[])[0]||(p.trigger_reasons||[]).join(' · ')||'Evidence changed')}</p><small>${new Date((p.created_at||0)*1000).toLocaleString()} · ${(p.unknowns||[]).length} unknown(s)</small></div>`).join(''):'<div class="empty">No semantic attention packets recorded yet.</div>'}
function renderSystem(){const o=state.overview||{};$('#systemContent').innerHTML=`<div class="diagnostic-section"><h3>CANONICAL PIPELINE</h3><pre>${esc(JSON.stringify(o.pipeline||{},null,2))}</pre></div><div class="diagnostic-section"><h3>GMGN READ-ONLY BRIDGE</h3><pre>${esc(JSON.stringify(o.gmgn||{},null,2))}</pre></div><div class="diagnostic-section"><h3>LOCAL MODELS / AGENTS</h3><pre>${esc(JSON.stringify({ollama:o.ollama,agents:o.agents},null,2))}</pre></div><div class="diagnostic-section"><h3>OPERATOR STATE</h3><pre>${esc(JSON.stringify(o.state||{},null,2))}</pre></div>`}

document.addEventListener('DOMContentLoaded',boot);
