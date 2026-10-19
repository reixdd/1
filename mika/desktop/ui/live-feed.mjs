import {safeImageUrl,normalizeSocials} from './token-media.mjs';
import {finite, normalizeRadarRow} from './domain.mjs';
const ts = value => {if(typeof value==='number')return value>1e11?value/1000:value;const n=Date.parse(String(value||''));return Number.isFinite(n)?n/1000:null};
const mint = row => String(row?.address||row?.contract||row?.mint||row?.token_address||row?.tokenAddress||row?.base_token_address||row?.baseToken?.address||'').trim();
const isMint = s => /^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(s||'');
const findStr = (...values) => values.find(v=>typeof v==='string' && v.trim())||'';
const normalizePlatform = value => String(value||'').toLowerCase().replace(/[^a-z0-9]/g,'');
export function pumpProof(row){
 const id=normalizePlatform(row?.dexId||row?.dex_id||row?.launchpad_platform||row?.launchpadPlatform||row?.platform||row?.dex?.id||row?.dex).replace(/^solana/, '');
 return ['pumpfun','pumpswap','pumpmayhem'].includes(id);
}
function safeRow(raw,source,now=Date.now()/1000){
 const contract=mint(raw);if(!isMint(contract))return null;
 const row={chain:'sol',contract,pool:raw?.pool||raw?.pairAddress||null,
  symbol:findStr(raw?.symbol,raw?.ticker,raw?.baseToken?.symbol).slice(0,30)||'?',
  name:findStr(raw?.name,raw?.baseToken?.name).slice(0,120)||'Unknown',
  category:'NEW',provider:source,providers:[source],source,
  observed_at:ts(raw?.observed_at)||now,
  market_cap:finite(raw?.market_cap??raw?.marketCap),
  liquidity:finite(raw?.liquidity_usd??raw?.liquidity?.usd??raw?.liquidity),
  volume_5m:finite(raw?.volume_5m??raw?.volume?.m5),
  buys_5m:finite(raw?.buys_5m??raw?.txns?.m5?.buys),
  sells_5m:finite(raw?.sells_5m??raw?.txns?.m5?.sells),
  image_url:safeImageUrl(findStr(raw?.image_url,raw?.logo_url,raw?.logo,raw?.icon,raw?.imageUrl,raw?.logoURI,raw?.image?.url,raw?.metadata?.image,raw?.info?.imageUrl)),
  socials:normalizeSocials(raw?.socials||raw?.info?.socials||[]),
  pair_created_at:ts(raw?.pair_created_at??raw?.pairCreatedAt)||null,
  source_url:findStr(raw?.url,raw?.pair_url)||null,
  launchpad_proof:raw?.launchpad_proof||source,
 };
 return normalizeRadarRow(row);
}
function sections(body){
 let data=body?.data??body;
 if(data?.data && typeof data.data==='object' && !Array.isArray(data.data))data=data.data;
 if(Array.isArray(data))return data;
 if(!data||typeof data!=='object')return [];
 return [data.new_creation,data.pump,data.near_completion,data.completed,data.tokens,data.items,data.data].filter(Array.isArray).flat();
}
export function normalizeTrenches(body,now=Date.now()/1000){
 return sections(body).filter(pumpProof).map(raw=>safeRow(raw,'GMGN',now)).filter(Boolean);
}
export function normalizeGeckoNewPools(body,now=Date.now()/1000){
 const included=new Map((body?.included||[]).map(r=>[r?.id,r?.attributes||{}]));
 return (body?.data||[]).flatMap(pool=>{
  const dex=pool?.relationships?.dex?.data?.id;
  if(!pumpProof({dexId:dex}))return [];
  const attrs=pool?.attributes||{}, tokenId=pool?.relationships?.base_token?.data?.id||'';
  const token=included.get(tokenId)||{},address=tokenId.replace(/^solana_/,''),m5=attrs.transactions?.m5||{};
  const row=safeRow({address,symbol:token.symbol,name:token.name,pool:attrs.address,
   liquidity_usd:attrs.reserve_in_usd,volume_5m:attrs.volume_usd?.m5,image_url:token.image_url||token.imageUrl||token.logo_url,
   buys_5m:m5.buys,sells_5m:m5.sells,pair_created_at:attrs.pool_created_at,
   launchpad_proof:'DEX relationship',url:attrs?.url},'GeckoTerminal',now);
  return row?[row]:[];
 });
}
export function normalizeDexQuotes(pairs,requested=[],now=Date.now()/1000){
 const mints=new Set(requested);return (Array.isArray(pairs)?pairs:[]).flatMap(pair=>{
  const contract=pair?.baseToken?.address;
  if(pair?.chainId!=='solana'|| !isMint(contract)||!mints.has(contract))return [];
  const row=safeRow({...pair,contract,pool:pair.pairAddress,
    symbol:pair.baseToken.symbol,name:pair.baseToken.name,
    volume_5m:pair.volume?.m5,buys_5m:pair.txns?.m5?.buys,sells_5m:pair.txns?.m5?.sells,
    liquidity_usd:pair.liquidity?.usd,image_url:pair.info?.imageUrl||pair.image?.url||pair.baseToken?.imageUrl,socials:pair.info?.socials,source_url:pair.url},'DEX Screener',now);
  if(!row)return [];
  row.dex_id=pair.dexId||null;row.launchpad_proof=pumpProof(pair)?'Pump.fun DEX':'Token quote only';
  return [row];
 });
}
export function mergeLiveRows(collections){
 const grouped=new Map();
 for(const rows of collections){for(const row of rows||[]){
  if(!row?.contract)continue;
  const k=`sol:${row.contract}`,prev=grouped.get(k);
  if(!prev){grouped.set(k,{...row,providers:[row.source||row.provider].filter(Boolean)});continue;}
  const providers=[...new Set([...(prev.providers||[]),row.source||row.provider].filter(Boolean))];
  const chosen=(row.observed_at||0)>=(prev.observed_at||0)?row:prev;
  const other=chosen===row?prev:row;
  const merged={...other,...chosen,providers};
  for(const key of ['market_cap','liquidity','volume_5m','buys_5m','sells_5m','image_url','socials','source_url'])if(merged[key]==null || (key==='socials' && !merged[key]?.length))merged[key]=other[key]??null;
  grouped.set(k,merged);
 }}return [...grouped.values()].sort((a,b)=>(b.observed_at||0)-(a.observed_at||0));
}

/** GMGN token-info details can enrich watched coins absent from new-pairs feed. */
export function metadataFromTokenDossier(gmgn,mintAddress){
 const wrapper=gmgn?.info||gmgn?.token_info||gmgn?.data||gmgn||{};
 const info=wrapper?.data?.data||wrapper?.data||wrapper;
 if(!info||typeof info!=='object'||Array.isArray(info))return null;
 const socials=Array.isArray(info.socials)?info.socials:
  (info.twitter||info.twitter_url?[{type:'twitter',url:info.twitter||info.twitter_url}]:[]);
 return safeRow({...info,address:mintAddress,socials},'GMGN token info');
}

/** Original Pump.fun uploaded metadata; never a replacement market quote. */
export function normalizePumpMetadata(payload,mintAddress){
 const info=payload?.data?.data||payload?.data||payload;
 if(!info||typeof info!=='object'||Array.isArray(info))return null;
 if(info.mint && info.mint!==mintAddress)return null;
 const social=(typeof info.twitter==='string'&&info.twitter)?[{type:'twitter',url:info.twitter}]:[];
 return safeRow({...info,address:mintAddress,image_url:info.image_uri||info.image||info.image_url,socials:social},'Pump.fun metadata');
}
