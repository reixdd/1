import {createClient} from './data.mjs';
import {normalizeRadarRow,freshness,finite,tokenKey} from './domain.mjs';
import {mergeLiveRows,metadataFromTokenDossier} from './live-feed.mjs';
import {classifyRisk,extractGMGNEvidence} from './risk.mjs';
import {compareSnapshots,rankTractionRows,latestActivityByMint} from './traction.mjs';
import {createPreferencesStore} from './storage.mjs';
import {marketCapRelative, safeExternalUrl} from './token-media.mjs';
import {selectChatModel,pruneConversation} from './chat-utils.mjs';
const $=id=>document.getElementById(id);
const store=createPreferencesStore(window.localStorage);
const invoke=window.__TAURI__?.core?.invoke;
const client=createClient(async path=>{if(!invoke)throw Error('Native MIKA bridge unavailable');return invoke('core_get',{path})},async(command,args)=>{if(!invoke)throw Error('Native bridge unavailable');return invoke(command,args)});
const state={connection:'OFFLINE',rows:[],selected:null,active:'scan',busy:false,feedBusy:false,quoteBusy:false,
 quoteCursor:0,quotes:new Map(),events:[],sources:{},lastFeed:0,lastQuote:0,quoteRetryAt:0,quoteErrors:0,
 chatHistory:[],models:[],modelError:null};
const short=s=>s?`${s.slice(0,6)}…${s.slice(-5)}`:'—';
const fmt=(value,unit='$')=>{const v=finite(value);if(v===null)return '—';return unit+(Math.abs(v)>=1e6?(v/1e6).toFixed(2)+'M':Math.abs(v)>=1e3?(v/1e3).toFixed(1)+'K':v<.01?v.toPrecision(3):v.toFixed(2))};
const el=(tag,cls,content)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(content!==undefined)n.textContent=String(content);return n};
const clear=n=>n.replaceChildren();
function button(text,handler,cls=''){const b=el('button',cls,text);b.type='button';b.addEventListener('click',handler);return b}
async function copyCA(mint){try{if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(mint);else {const field=document.createElement('textarea');field.value=mint;document.body.append(field);field.select();if(!document.execCommand('copy'))throw Error('Clipboard unavailable');field.remove()}$('globalError').hidden=false;$('globalError').textContent='Copied full contract address.'}catch(e){showError(`Copy failed: ${e.message||e}`)}}
function showError(t){$('globalError').hidden=!t;$('globalError').textContent=t||''}
function character(mode){if(state.busy && mode==='IDLE')return;$('app').dataset.character=mode;const lines={OFFLINE:'Research providers are unavailable right now.',IDLE:'I am watching the latest observations.',SCANNING:'Checking the evidence. No guesses.',WARNING:'Some risk indicators need attention.',ACTIVITY:'Market activity changed. Check the evidence.',THINKING:'Working through your question…'};$('characterCaption').textContent=lines[mode]||lines.IDLE;const prefs=store.preferences();$('portrait').src=mode==='WARNING'?'./assets/warning.webp':mode==='ACTIVITY'?'./assets/activity.webp':prefs.mode==='full'?'./assets/fullbody.webp':prefs.mode==='icon'?'./assets/icon.webp':'./assets/portrait.webp'}
function tab(name){if(!['scan','traction','watch','ask'].includes(name))return;state.active=name;for(const b of document.querySelectorAll('.tab')){b.classList.toggle('current',b.dataset.tab===name);b.setAttribute('aria-selected',String(b.dataset.tab===name))}for(const v of document.querySelectorAll('.view'))v.hidden=v.id!==`view-${name}`;if(name==='traction')renderTraction();if(name==='watch')renderWatch();if(name==='ask')loadModels()}
function stat(k,v){const d=el('div','stat');d.append(el('label','',k),el('strong','',v));return d}
function market(mint){return state.quotes.get(mint)||state.rows.find(r=>r.contract===mint)||null}
function activeSourceText(){return Object.entries(state.sources).map(([k,v])=>`${k} ${v}`).join(' · ')||'Waiting for providers'}
function sourceStatus(){const now=Date.now();$('feedSources').textContent=`${activeSourceText()} · provider prices may be cached`;const count=state.rows.length;$('feedStamp').textContent=`${count} Pump.fun pairs · ${state.lastFeed?new Date(state.lastFeed).toLocaleTimeString():'no fetch'}`;
 $('lastUpdated').textContent=state.lastQuote?`Quote check ${Math.floor((now-state.lastQuote)/1000)}s ago`:'No quotes';$('quoteStatus').textContent=state.quoteErrors?`Quote provider delayed · retrying · last check ${state.lastQuote?new Date(state.lastQuote).toLocaleTimeString():'none'}`:`Quotes requested ~1s apart when tokens are present · ${state.lastQuote?new Date(state.lastQuote).toLocaleTimeString():'awaiting first response'} · provider caching possible`;
 $('tractionStatus').textContent=state.rows.length?`${state.rows.length} launchpad tokens observed · ${store.events().length} historical changes`:'No verified launchpad tokens from configured providers yet';}
function imageFor(row){
 const holder=el('span','avatar',(row.symbol||'?').slice(0,1).toUpperCase());
 const url=row.image_url;
 if(url){const img=el('img','token-art');img.src=url;img.alt=`${row.symbol||'Token'} artwork (provider supplied)`;img.loading='lazy';img.referrerPolicy='no-referrer';img.addEventListener('error',()=>img.replaceWith(holder),{once:true});return img;}
 return holder;
}
function externalLink(url,label){const safe=safeExternalUrl(url);if(!safe)return null;const a=el('a','mini-link',label);a.href=safe;a.target='_blank';a.rel='noopener noreferrer';a.title=`Open ${label}`;return a;}
function tokenActions(row){const actions=el('div','token-actions');actions.append(button('⧉ CA',()=>copyCA(row.contract),'mini-action'));
 const x=row.socials?.find(x=>x.kind==='x');const link=externalLink(x?.url,'𝕏');if(link)actions.append(link);
 const source=externalLink(row.source_url,'↗ Chart');if(source)actions.append(source);return actions;}
function capBar(cap,max){const wrap=el('div','cap-meter'),fill=el('div','cap-meter-fill');const percent=marketCapRelative(finite(cap),max);if(percent!==null){fill.style.width=`${percent}%`;wrap.append(fill);}else wrap.textContent='Market cap not verified';wrap.title=percent===null?'No comparable market cap':`${percent.toFixed(1)}% of largest displayed market cap ${fmt(max)}`;return wrap;}
function tokenCard(row,{traction=false,maxCap=null,event=null}={}){
 const wrap=el('div','token-card');wrap.dataset.mint=row.contract;const top=el('div','token-item');const inspect=button('',()=>scanToken(row.contract),'token-open');inspect.setAttribute('aria-label',`Inspect ${row.symbol} ${row.contract}`);
 const content=el('span','token-meta');const title=el('span','token-name',row.symbol);title.append(el('small','',` · ${row.name||''}`));
 content.append(title,el('div','token-address',short(row.contract)+` · ${row.source||row.provider}`));
 const m=market(row.contract)||row,price=el('span','token-values');price.append(el('strong','',fmt(m.market_cap)),el('span','',m.volume_5m!=null?`5m ${fmt(m.volume_5m)}`:freshness(m.observed_at)));inspect.append(imageFor({...row,image_url:row.image_url||m.image_url}),content,price);top.append(inspect);wrap.append(top);
 if(traction){
  wrap.append(capBar(m.market_cap,maxCap));
  const label=event?`${event.kind.replaceAll('_',' ')} · ${event.change_pct>0?'+':''}${event.change_pct}% observed`:'Collecting comparable snapshots';
  const status=el('span','traction-indicator'+(event?.change_pct<0?' down':event?'':' unknown'),label);
  wrap.dataset.activity=event?.kind||'BASELINE';wrap.append(status);
 }
 const actions=tokenActions({...row,socials:row.socials?.length?row.socials:m.socials,source_url:row.source_url||m.source_url});wrap.append(actions);
 return wrap;
}
function renderTokens(){
 const root=$('tokenList');
 if(!state.rows.length){clear(root);root.append(el('p','empty',`No confirmed Pump.fun launchpad pairs from connected sources. ${activeSourceText()}. JARVIS canonical eligibility is not required here.`));return}
 // Reuse the same card/IMG nodes; a 1s quote refresh must not restart image downloads,
 // collapse the flex list or reset the user's scroll position.
 const previous=new Map([...root.querySelectorAll('.token-card[data-mint]')].map(card=>[card.dataset.mint,card]));
 const oldScroll=root.scrollTop,fragment=document.createDocumentFragment();
 for(const row of state.rows.slice(0,60)){
  const m=market(row.contract)||row,known=store.tokenMeta(row.contract)||{},resolved={...known,...row,
   image_url:row.image_url||m.image_url||known.image_url||null};
  let card=previous.get(row.contract);
  if(!card){card=tokenCard(resolved);}else{
   const number=card.querySelector('.token-values strong'),detail=card.querySelector('.token-values span');
   if(number)number.textContent=fmt(m.market_cap);
   if(detail)detail.textContent=m.volume_5m!=null?`5m ${fmt(m.volume_5m)}`:freshness(m.observed_at);
   const fallback=card.querySelector('.avatar');
   if(fallback&&resolved.image_url)fallback.replaceWith(imageFor(resolved));
   const actions=card.querySelector('.token-actions');
   if(actions&&resolved.socials?.length&&!actions.querySelector('a[title="Open 𝕏"]'))actions.replaceWith(tokenActions(resolved));
  }
  fragment.append(card);
 }
 root.replaceChildren(fragment);root.scrollTop=oldScroll;
}
function analysis(){const root=$('analysis');clear(root);if(!state.selected)return;const token=state.selected,m=market(token.mint)||token.market||{},fields=extractGMGNEvidence(token.gmgn||{}),risk=classifyRisk(fields);
 const section=el('section','dossier'),head=el('div','dossier-heading'),details=el('div');details.append(el('strong','',m.symbol||token.market?.symbol||short(token.mint)),el('small','ca-full',token.mint));
 const watchKey=tokenKey('sol',token.mint),watch=button(store.watched().includes(watchKey)?'★ SAVED':'☆ WATCH',()=>{store.setWatched(watchKey,!store.watched().includes(watchKey));analysis();renderWatch()},'save-btn');
 head.append(details,button('⧉',()=>copyCA(token.mint),'save-btn'),watch);section.append(head);
 const grid=el('div','grid-two');grid.append(stat('MARKET CAP',fmt(m.market_cap)),stat('LIQUIDITY',fmt(m.liquidity)),stat('5M VOLUME',fmt(m.volume_5m)),stat('5M BUYS / SELLS',`${finite(m.buys_5m)??'—'} / ${finite(m.sells_5m)??'—'}`));section.append(grid);
 const verdict=el('div','verdict '+(risk.verdict==='HIGH_RISK'?'high':risk.verdict==='NO_MAJOR_FLAGS_DETECTED'?'clear':''));verdict.append(el('strong','',risk.verdict.replaceAll('_',' ')),el('span','',`${token.canonical?'Canonical dossier':'GMGN/direct quote fallback'} · no safety guarantee`));section.append(verdict);
 for(const f of fields){const item=el('div','finding',`${f.field.replaceAll('_',' ')} · ${f.severity} · ${String(f.value)}`);item.append(el('span','',`${f.provider} · ${f.status}`));section.append(item)}
 if(risk.unknowns.length){const item=el('div','finding',`Not verified: ${risk.unknowns.join(', ').replaceAll('_',' ')}`);item.append(el('span','','Missing values cannot be treated as safe.'));section.append(item)}
 const last=el('div','finding',`Quote checked: ${m.observed_at?new Date(m.observed_at*1000).toLocaleTimeString():'not available'}`);last.append(el('span','',`${m.source||m.provider||'No quote provider'} · API responses may be cached`));section.append(last);root.append(section)
}
function renderTraction(){
 sourceStatus();const root=$('tractionList');clear(root);
 const rows=rankTractionRows(state.rows,state.quotes,24),latest=latestActivityByMint(store.events());
 if(!rows.length){root.append(el('p','empty','Awaiting confirmed Pump.fun observations.'));return}
 const maxCap=Math.max(0,...rows.map(r=>finite(market(r.contract)?.market_cap??r.market_cap)||0));
 root.append(el('p','support','Observed 5m volume order · market-cap bars relative to highest displayed · no price prediction'));
 for(const row of rows){
  const m=market(row.contract)||row,known=store.tokenMeta(row.contract)||{};
  root.append(tokenCard({...known,...row,image_url:row.image_url||m.image_url||known.image_url||null,
   socials:row.socials?.length?row.socials:m.socials||known.socials||[]},{traction:true,maxCap,event:latest.get(row.contract)||null}));
 }
}
function renderWatch(){sourceStatus();const root=$('watchList');clear(root);const watched=store.watched();$('watchCount').textContent=`${watched.length} SAVED`;
 if(!watched.length){root.append(el('p','empty','No saved tokens yet. Select one on Scan.'));return}
 const maxCap=Math.max(0,...watched.map(key=>finite(market(key.startsWith('sol:')?key.slice(4):key)?.market_cap)||0));
 for(const key of watched){const mint=key.startsWith('sol:')?key.slice(4):key;const quote=market(mint)||{},known=store.tokenMeta(mint)||{},m={...known,...quote,
 image_url:quote.image_url||known.image_url||null,socials:quote.socials?.length?quote.socials:known.socials||[],source_url:quote.source_url||known.source_url||null};
 const card=el('div','watch-item');
 const head=el('div','watch-head');head.append(imageFor({...m,contract:mint,symbol:m.symbol||'?',image_url:m.image_url}),el('strong','',`${m.symbol||'Unknown'} · ${fmt(m.market_cap)}`));card.append(head);
 card.append(el('small','ca-full',mint),el('small','',`${m.observed_at?new Date(m.observed_at*1000).toLocaleTimeString():'Quote unavailable'} · ${m.source||m.provider||'No provider yet'} · provider may cache`));
 const bar=capBar(m.market_cap,maxCap);bar.classList.add('watch-cap');card.append(bar);const actions=el('div','watch-actions');actions.append(button('⧉ Copy CA',()=>copyCA(mint)),button('Inspect',()=>{tab('scan');scanToken(mint)}));const x=externalLink(m.socials?.find(x=>x.kind==='x')?.url,'𝕏');if(x)actions.append(x);const chart=externalLink(m.source_url,'↗ Chart');if(chart)actions.append(chart);
 actions.append(button('×',()=>{store.setWatched(key,false);renderWatch()}));card.append(actions);root.append(card)}
}
function recordSnapshot(row){store.saveTokenMeta(row.contract,row);const norm=normalizeRadarRow(row),old=store.recentSnapshot(norm.market_key);if(old){const events=compareSnapshots(old,norm);if(events.length){store.saveEvents(events);if(state.active==='traction')character('ACTIVITY')}}store.saveSnapshot(norm.market_key,norm)}
async function refreshQuotes(){if(state.quoteBusy||Date.now()<state.quoteRetryAt)return;const keys=[...new Set([...store.watched().map(k=>k.slice(4)),...state.rows.map(r=>r.contract),...(state.selected?[state.selected.mint]:[])])];if(!keys.length){sourceStatus();return}
 const offset=state.quoteCursor%keys.length,chunk=Array.from({length:Math.min(30,keys.length)},(_,i)=>keys[(offset+i)%keys.length]);state.quoteCursor=(offset+chunk.length)%keys.length;
 state.quoteBusy=true;try{const all=await client.quotes(chunk);const grouped=new Map();for(const quote of all){const old=grouped.get(quote.contract);if(!old||(quote.liquidity??0)>(old.liquidity??0))grouped.set(quote.contract,quote)}for(const quote of grouped.values()){recordSnapshot(quote);state.quotes.set(quote.contract,{...state.quotes.get(quote.contract),...quote,image_url:quote.image_url||market(quote.contract)?.image_url||null,socials:quote.socials?.length?quote.socials:market(quote.contract)?.socials||[]})}state.lastQuote=Date.now();state.quoteErrors=0;state.quoteRetryAt=0;renderTokens();if(state.selected)analysis();if(state.active==='traction')renderTraction();if(state.active==='watch')renderWatch()}catch(e){state.quoteErrors++;state.quoteRetryAt=Date.now()+Math.min(60000,1000*2**Math.min(state.quoteErrors,6));showError(`DEX quote provider unavailable: ${e.message||e}`)}finally{state.quoteBusy=false;sourceStatus()}}
async function refreshFeed(){if(state.feedBusy)return;state.feedBusy=true;try{const health=await client.status();state.connection=health.connection;$('connection').textContent=health.connection==='CONNECTED'?'● CORE CONNECTED':'● CORE OFFLINE';$('connection').classList.toggle('online',health.connection==='CONNECTED');const feed=await client.liveFeed();state.sources=feed.sources;state.rows=mergeLiveRows([feed.rows]);state.lastFeed=Date.now();for(const row of state.rows){recordSnapshot(row)}if(feed.errors.length&&!state.rows.length)showError(feed.errors.join(' · ').slice(0,350));else showError('');character(state.rows.length?'IDLE':health.connection==='CONNECTED'?'IDLE':'OFFLINE');renderTokens();if(state.active==='traction')renderTraction();if(state.active==='watch')renderWatch();sourceStatus()}catch(e){showError(`Feed refresh failed: ${e.message||e}`)}finally{state.feedBusy=false}}
async function scanToken(mint){if(state.busy)return;state.busy=true;showError('');$('tokenInput').value=mint;$('tokenForm').querySelector('button').disabled=true;character('SCANNING');try{state.selected=await client.token('sol',mint);const tokenMeta=metadataFromTokenDossier(state.selected.gmgn,mint);if(tokenMeta)store.saveTokenMeta(mint,tokenMeta);if(!state.selected.found && !market(mint))showError(state.selected.error||'Research sources unavailable');analysis();character(classifyRisk(extractGMGNEvidence(state.selected.gmgn||{})).verdict==='HIGH_RISK'?'WARNING':'IDLE');await refreshQuotes()}catch(e){showError(`Token research failed: ${e.message||e}`);character('IDLE')}finally{state.busy=false;$('tokenForm').querySelector('button').disabled=false}}
function chatLine(role,text){const box=el('div',`chat-line ${role}`);box.append(el('strong','',role==='user'?'YOU':'MIKA'),el('p','',text));$('chatHistory').append(box);$('chatHistory').scrollTop=$('chatHistory').scrollHeight}
async function loadModels(){if(state.models.length)return;try{const models=await client.models();state.models=models.map(x=>x.name||x.model).filter(Boolean).filter(x=>!/(embed|embedding|rerank|nomic)/i.test(x));const menu=$('chatModel');clear(menu);for(const m of state.models)menu.append(el('option','',m));for(const o of menu.options)o.value=o.textContent;if(!state.models.length)menu.append(el('option','','No conversational local models'));else menu.value=selectChatModel(state.models);state.modelError=null}catch(e){state.modelError=String(e.message||e);clear($('chatModel'));$('chatModel').append(el('option','','Ollama offline'))}}
async function ask(question){const text=String(question||'').trim();if(!text)return;chatLine('user',text);state.chatHistory.push({role:'user',content:text});const send=$('askForm').querySelector('button');send.disabled=true;character('THINKING');try{await loadModels();if(state.modelError||!state.models.length)throw Error(state.modelError||'No Ollama model installed');const context={current_token:state.selected?{mint:state.selected.mint,market:market(state.selected.mint),risk:classifyRisk(extractGMGNEvidence(state.selected.gmgn||{}))}:null,feed_sources:state.sources,observed_pairs:state.rows.length};const reply=await client.chat($('chatModel').value,pruneConversation(state.chatHistory),context);state.chatHistory.push({role:'assistant',content:reply});state.chatHistory=state.chatHistory.slice(-16);chatLine('assistant',reply)}catch(e){chatLine('assistant',`Local AI unavailable: ${e.message||e}. Start Ollama and check installed models; research tabs will still work.`)}finally{send.disabled=false;character('IDLE')}}
function init(){const prefs=store.preferences();$('app').dataset.accent=prefs.accent;$('app').dataset.mode=prefs.mode;$('app').dataset.animation=prefs.animation;$('accentColor').value=prefs.accent;$('avatarMode').value=prefs.mode;$('companionMood').value=prefs.mood;$('animationIntensity').value=prefs.animation;$('alwaysOnTop').checked=prefs.alwaysOnTop;
 for(const b of document.querySelectorAll('.tab'))b.addEventListener('click',()=>tab(b.dataset.tab));$('refresh').addEventListener('click',()=>{refreshFeed();refreshQuotes()});$('tokenForm').addEventListener('submit',e=>{e.preventDefault();scanToken($('tokenInput').value.trim())});$('askForm').addEventListener('submit',e=>{e.preventDefault();const input=$('askInput'),message=input.value;input.value='';ask(message)});$('settingsToggle').addEventListener('click',()=>{const c=$('settingsContent');c.hidden=!c.hidden;$('settingsToggle').setAttribute('aria-expanded',String(!c.hidden))});for(const [id,key] of [['avatarMode','mode'],['accentColor','accent'],['companionMood','mood'],['animationIntensity','animation']])$(id).addEventListener('change',e=>{store.setPreference(key,e.target.value);$('app').dataset[key==='mode'?'mode':key==='accent'?'accent':'animation']=e.target.value;character($('app').dataset.character)});$('alwaysOnTop').addEventListener('change',async e=>{try{if(invoke)await invoke('set_always_on_top',{enabled:e.target.checked});store.setPreference('alwaysOnTop',e.target.checked)}catch(err){e.target.checked=!e.target.checked;showError(String(err))}});
 character('OFFLINE');refreshFeed().then(refreshQuotes);setInterval(refreshFeed,40000);setInterval(refreshQuotes,1000);setInterval(sourceStatus,1000);
}
init();
