import {signSession,verifySession,isSameOrigin,verifyDeviceKey,validJobPath,cookieValue} from './security.mjs';
import {normalizeGeckoNewPools,normalizeDexQuotes} from '../desktop/ui/live-feed.mjs';
export {MikaQueue} from './coordinator.mjs';
const json=(value,status=200,headers={})=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff',...headers}});
const urlOf=r=>new URL(r.url);
const mintOk=m=>typeof m==='string' && /^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(m);
const sameOrigin=(r,env)=>isSameOrigin(r.headers.get('Origin'),env.PUBLIC_ORIGIN);
async function readJsonBounded(request,maxBytes=3000){const reader=request.body?.getReader();if(!reader)return {};const decoder=new TextDecoder('utf-8',{fatal:true});let size=0,value='';try{while(true){const next=await reader.read();if(next.done)break;size+=next.value.byteLength;if(size>maxBytes)throw Error('Payload too large');value+=decoder.decode(next.value,{stream:true});}value+=decoder.decode();return JSON.parse(value);}catch(e){await reader.cancel().catch(()=>{});throw e;}}
const session=async(r,env)=>verifySession(cookieValue(r.headers.get('Cookie'),'mika_chat'),Date.now(),env.SESSION_HMAC_SECRET);
const stub=env=>env.MIKA_QUEUE.get(env.MIKA_QUEUE.idFromName('mika-public-global'));
async function queue(env,path,method='GET',body=null){const r=await stub(env).fetch('https://internal.mika'+path,{method,headers:body?{'Content-Type':'application/json'}:{},...(body?{body:JSON.stringify(body)}:{})});return {status:r.status,body:await r.json()};}
const timeout=ms=>AbortSignal.timeout(ms);
async function verifiedTurnstile(challenge,env,ip){
 if(!env.TURNSTILE_SECRET||typeof challenge!=='string'||challenge.length>2400||challenge.length<10)return false;
 try{const response=await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({secret:env.TURNSTILE_SECRET,response:challenge,remoteip:ip||''}),signal:timeout(8000)});const data=await response.json();return response.ok&&data.success===true&&data.hostname===new URL(env.PUBLIC_ORIGIN).hostname;}catch{return false;}
}
async function cachedProvider(request,fetcher,seconds){const cache=caches.default;const key=new Request(request.url,{method:'GET'});const hit=await cache.match(key);if(hit)return hit;
 const out=await fetcher();if(out.ok){const copy=out.clone();await cache.put(key,new Response(copy.body,{status:copy.status,headers:{...Object.fromEntries(copy.headers),'Cache-Control':`public, max-age=${seconds}`}}));}return out;
}
async function feed(request){return cachedProvider(request,async()=>{
 try{const res=await fetch('https://api.geckoterminal.com/api/v2/networks/solana/new_pools?include=base_token,dex&page=1',{signal:timeout(9000),headers:{'Accept':'application/json'}});if(!res.ok)return json({error:'GECKO_UNAVAILABLE'},503);
 const data=await res.json();const rows=normalizeGeckoNewPools(data).slice(0,30);
 if(rows.length){try{const tokenMints=rows.map(x=>x.contract);const dr=await fetch('https://api.dexscreener.com/tokens/v1/solana/'+tokenMints.join(','),{signal:timeout(8000),headers:{'Accept':'application/json'}});if(dr.ok){const quotes=normalizeDexQuotes(await dr.json(),tokenMints);for(const row of rows){const q=quotes.filter(x=>x.contract===row.contract).sort((a,b)=>(b.liquidity||0)-(a.liquidity||0))[0];if(q){row.image_url=row.image_url||q.image_url;row.socials=q.socials||[];row.market_cap=q.market_cap??row.market_cap;row.source_url=row.source_url||q.source_url;row.metadata_source='DEX Screener';}}}}catch{/* independently available market feed survives enrich failure */}}
 return json({rows,source:'GeckoTerminal / DEX Screener',checked_at:Date.now(),status:'OK'});
 }catch{return json({error:'MARKET_PROVIDER_UNAVAILABLE'},503)}
 },40)}
async function quotes(request,mint){return cachedProvider(request,async()=>{
 try{const r=await fetch(`https://api.dexscreener.com/tokens/v1/solana/${mint}`,{signal:timeout(9000)});if(!r.ok)return json({error:'DEX_PROVIDER_UNAVAILABLE'},503);return json({rows:normalizeDexQuotes(await r.json(),[mint]),source:'DEX Screener',checked_at:Date.now()});}catch{return json({error:'DEX_PROVIDER_UNAVAILABLE'},503)}
 },15)}
const apiError=(err,http=400)=>json({error:err},http);
async function handle(request,env){
 const {pathname,searchParams}=urlOf(request),method=request.method;
 if(!env.PUBLIC_ORIGIN||!env.SESSION_HMAC_SECRET||!env.MIKA_QUEUE)return apiError('RELAY_NOT_CONFIGURED',503);
 if(!['GET','POST','DELETE','HEAD'].includes(method))return apiError('METHOD_NOT_ALLOWED',405);
 if(method==='GET'&&pathname==='/api/config')return json({turnstile_site_key:env.TURNSTILE_SITE_KEY||null});
 if(method==='GET'&&pathname==='/api/chat/status'){const r=await queue(env,'/queue/status');return json(r.body,r.status)}
 if(method==='GET'&&pathname==='/api/market/feed')return feed(request);
 if(method==='GET'&&pathname==='/api/market/quotes'){const mint=searchParams.get('mint');if(!mintOk(mint))return apiError('INVALID_MINT');return quotes(request,mint)}
 if(pathname.startsWith('/api/device/')){
  if(!await verifyDeviceKey(request.headers.get('Authorization'),env.LOCAL_CONNECTOR_SECRET))return apiError('DEVICE_UNAUTHORIZED',401);
  if(method!=='POST')return apiError('METHOD_NOT_ALLOWED',405);
  let body={};try{body=await readJsonBounded(request);}catch{return apiError('BAD_JSON')}
  if(pathname==='/api/device/claim'){const r=await queue(env,'/queue/claim','POST',{lease:crypto.randomUUID()});return json(r.body,r.status)}
  if(pathname==='/api/device/complete'){if(!body||typeof body.id!=='string'||typeof body.lease!=='string')return apiError('INVALID_COMPLETION');const r=await queue(env,'/queue/complete','POST',{id:body.id,lease:body.lease,answer:body.answer,error:body.error});return json(r.body,r.status)}
  if(pathname==='/api/device/heartbeat'){const r=await queue(env,'/queue/heartbeat','POST',{});return json(r.body,r.status)}
  return apiError('NOT_FOUND',404);
 }
 if(!pathname.startsWith('/api/chat/'))return apiError('NOT_FOUND',404);
 if(method==='POST'&&!sameOrigin(request,env))return apiError('ORIGIN_NOT_ALLOWED',403);
 if(pathname==='/api/chat/session'&&method==='POST'){
  if(request.headers.get('Content-Length')&&Number(request.headers.get('Content-Length'))>3500)return apiError('TOO_LARGE',413);
  let body;try{body=await readJsonBounded(request)}catch{return apiError('BAD_JSON')}
  const verified=await verifiedTurnstile(body?.challenge,env,request.headers.get('CF-Connecting-IP'));if(!verified)return apiError('CHALLENGE_FAILED',403);
  const signed=await signSession(crypto.randomUUID(),Date.now()+24*3600000,env.SESSION_HMAC_SECRET);
  return json({ok:true},200,{'Set-Cookie':`mika_chat=${signed}; Path=/api/chat; Max-Age=86400; HttpOnly; Secure; SameSite=Lax`});
 }
 const sid=await session(request,env);if(!sid)return apiError('SESSION_REQUIRED',401);
 if(pathname==='/api/chat/jobs'&&method==='POST'){
  if(request.headers.get('Content-Length')&&Number(request.headers.get('Content-Length'))>2500)return apiError('TOO_LARGE',413);
  let body;try{body=await readJsonBounded(request)}catch{return apiError('BAD_JSON')}
  if(!body||Object.keys(body).some(k=>!['text','selected_mint'].includes(k)))return apiError('INVALID_CHAT_REQUEST');
  if(body.selected_mint!=null && !mintOk(body.selected_mint))return apiError('INVALID_MINT');
  const r=await queue(env,'/queue/admit','POST',{session:sid,text:body.text,selectedMint:body.selected_mint||null,id:crypto.randomUUID()});return json(r.body,r.status);
 }
 if(validJobPath(pathname)&&method==='GET'){
  const r=await queue(env,'/queue/job','POST',{session:sid,id:pathname.split('/').at(-1)});return json(r.body,r.status);
 }
 return apiError('NOT_FOUND',404);
}
export default {async fetch(request,env){const pathname=urlOf(request).pathname;
 if(pathname.startsWith('/api/'))return handle(request,env);
 if(env.ASSETS){const response=await env.ASSETS.fetch(request);const headers=new Headers(response.headers);
  headers.set('Content-Security-Policy',"default-src 'self'; script-src 'self' https://challenges.cloudflare.com; style-src 'self'; img-src 'self' data: https://cdn.dexscreener.com https://dd.dexscreener.com https://coin-images.coingecko.com https://assets.coingecko.com https://coin-images.geckoterminal.com https://images.geckoterminal.com https://ipfs.io https://gateway.pinata.cloud https://cf-ipfs.com https://arweave.net https://pump.mypinata.cloud; connect-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'");
  headers.set('X-Content-Type-Options','nosniff');headers.set('Referrer-Policy','no-referrer');
  return new Response(response.body,{status:response.status,headers});}

 return apiError('ASSETS_UNAVAILABLE',503);
}};
