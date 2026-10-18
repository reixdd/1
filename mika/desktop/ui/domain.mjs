import {safeImageUrl,normalizeSocials,safeExternalUrl} from './token-media.mjs';
/** MIKA canonical identities and evidence-safe numeric parsing. */
export const finite = value => value === null || value === undefined || value === '' || typeof value === 'boolean' ? null : (Number.isFinite(Number(value)) ? Number(value) : null);
export function tokenKey(chain, contract) {
  const c=String(chain||'').trim().toLowerCase(), mint=String(contract||'').trim();
  if(!c || !mint || /\s/.test(mint) || mint.length>128 || !/^[a-z0-9]+$/i.test(mint)) throw Error('Invalid token identity');
  return `${c}:${['eth','base','bsc'].includes(c)?mint.toLowerCase():mint}`;
}
export function freshness(observedAt,now=Date.now()/1000) {
  const n=finite(observedAt),t=finite(now);if(n===null||n<=0||t===null)return 'UNAVAILABLE';
  const age=Math.max(0,t-n);return age<=45?'FRESH':age<=180?'DELAYED':'UNAVAILABLE';
}
export function normalizeRadarRow(row) {
  if(!row||typeof row!=='object')throw Error('Invalid market row');
  const chain=String(row.chain||'sol').toLowerCase(),contract=String(row.contract||row.address||row.mint||'').trim();
  const key=tokenKey(chain,contract);
  const provider=String(row.provider||row.providers?.[0]||'JARVIS canonical market');
  const numbers=['price','market_cap','fdv','liquidity','volume_5m','volume_1h','volume_24h','buys_5m','sells_5m','price_change_5m_pct','rank_velocity_per_min'];
  const values=Object.fromEntries(numbers.map(k=>[k,finite(row[k])]));
  const observed_at=finite(row.last_observed_at??row.observed_at);
  const pool=row.pool||null;
  return {chain,contract,token_key:key,market_key:`${key}:${pool||'-'}`,pool,
    symbol:String(row.symbol||'?').slice(0,60),name:String(row.name||'Unknown token').slice(0,100),
    identity_key:String(row.identity_key||`${key}:${pool||'-'}`),
    category:String(row.category||'RESEARCH'),provider,source:String(row.source||provider),source_url:safeExternalUrl(row.source_url),socials:normalizeSocials(row.socials),dex_id:row.dex_id||null,launchpad_proof:row.launchpad_proof||null,image_url:safeImageUrl(row.image_url),pair_created_at:finite(row.pair_created_at),providers:Array.isArray(row.providers)?row.providers:[],
    observed_at,age_seconds:finite(row.age_seconds),observation_age_seconds:finite(row.observation_age_seconds),
    why_surfaced:Array.isArray(row.why_surfaced)?row.why_surfaced:[],
    ...values};
}
export function groupMarkets(rows) {
  const groups=new Map();
  for(const raw of rows||[]) {
    let row;try {row=normalizeRadarRow(raw)} catch {continue}
    if(!groups.has(row.token_key))groups.set(row.token_key,{token_key:row.token_key,chain:row.chain,contract:row.contract,symbol:row.symbol,name:row.name,markets:[]});
    const group=groups.get(row.token_key);
    if(!group.markets.some(m=>m.market_key===row.market_key))group.markets.push(row);
  }
  return Array.from(groups.values());
}
