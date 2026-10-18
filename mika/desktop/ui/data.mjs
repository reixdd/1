import {groupMarkets,normalizeRadarRow} from './domain.mjs';
import {normalizeTrenches,normalizeGeckoNewPools,normalizeDexQuotes,mergeLiveRows} from './live-feed.mjs';
/** Native read-only commands; all requests use existing JARVIS GET routes. */
function parse(body){ if(typeof body==='object' && body!==null)return body;try{return JSON.parse(body)}catch{throw Error('Core returned invalid JSON')} }
function validMint(mint){const s=String(mint||'').trim();if(!/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(s))throw Error('Invalid Solana mint address');return s}
async function request(coreGet,path){return parse(await coreGet(path))}
export function createClient(coreGet,nativeInvoke=null){
  if(typeof coreGet!=='function')throw Error('Missing read-only local bridge');
  const native=async(command,args={})=>{
    if(typeof nativeInvoke!=='function')throw Error('Native market provider bridge unavailable');
    const result=await nativeInvoke(command,args);return command==='ollama_chat'?result:parse(result);
  };
  return {
    async liveFeed(){
      const sources={GMGN:'PENDING',GeckoTerminal:'PENDING'};
      const [gmgn,gecko]=await Promise.allSettled([
        request(coreGet,'/api/operator/gmgn/trenches?chain=sol&limit=60'),
        native('market_gecko')]);
      const a=gmgn.status==='fulfilled'?normalizeTrenches(gmgn.value):[];
      const b=gecko.status==='fulfilled'?normalizeGeckoNewPools(gecko.value):[];
      sources.GMGN=gmgn.status==='rejected'?'ERROR':a.length?'OK':'EMPTY';
      sources.GeckoTerminal=gecko.status==='rejected'?'ERROR':b.length?'OK':'EMPTY';
      return {rows:mergeLiveRows([a,b]),sources,
        errors:[gmgn.status==='rejected'?`GMGN: ${String(gmgn.reason)}`:null,
                gecko.status==='rejected'?`GeckoTerminal: ${String(gecko.reason)}`:null].filter(Boolean)};
    },
    async quotes(mints){
      const clean=[...new Set(mints)].filter(validMint);
      if(!clean.length)return [];
      const result=[];
      for(let i=0;i<clean.length;i+=30){
        const batch=clean.slice(i,i+30);
        const raw=await native('market_dex',{mints:batch});
        result.push(...normalizeDexQuotes(raw,batch));
      }
      return result;
    },
    async models(){return (await native('ollama_models')).models||[]},
    async chat(model,history,context){
      const result=await native('ollama_chat',{model,history,context:JSON.stringify(context||{}).slice(0,6500)});
      return typeof result==='string'?result:String(result);
    },
    async status(){try{const h=await request(coreGet,'/health');return {connection:h.ok===true?'CONNECTED':'OFFLINE',core:h}}catch(e){return {connection:'OFFLINE',error:String(e.message||e)}}},
    async gmgnStatus(){try{return await request(coreGet,'/api/operator/gmgn/status')}catch(e){return {ok:false,error:String(e.message||e)}}},
    async radar(){const result=await request(coreGet,'/api/operator/radar?limit=80');if(!Array.isArray(result.items))throw Error('Core radar missing items');return {...result,groups:groupMarkets(result.items)}},
    async trenches(){const r=await request(coreGet,'/api/operator/gmgn/trenches?chain=sol&limit=60');const raw=r.data;if(Array.isArray(raw))return raw;if(Array.isArray(raw?.data))return raw.data;if(Array.isArray(raw?.tokens))return raw.tokens;return []},
    async attention(){return await request(coreGet,'/api/attention')},
    async token(chain,mint){
      if(chain!=='sol')throw Error('MIKA v1 only supports Solana');
      const address=validMint(mint);let dossier=null, gmgn=null;const problems=[];
      try{dossier=await request(coreGet,`/api/operator/dossier?chain=sol&contract=${address}&gmgn=true`)}catch(e){problems.push(`JARVIS dossier: ${String(e.message||e)}`)}
      // The direct token endpoint works even when the canonical JARVIS universe has no entry.
      if(dossier?.found && dossier?.gmgn && !dossier.gmgn.error)gmgn=dossier.gmgn;
      else {try{gmgn=await request(coreGet,`/api/operator/gmgn/token?chain=sol&address=${address}&holders=true`)}catch(e){problems.push(`GMGN: ${String(e.message||e)}`)}}
      const validGMGN=!!gmgn && ['info','security','pool','holders'].some(k=>gmgn[k]?.ok!==false && gmgn[k]!=null);
      const found=!!dossier?.found||validGMGN;
      return {found,canonical:!!dossier?.found,chain,mint:address,market:dossier?.market||null,
        observations:dossier?.observations||[],synthesis:dossier?.synthesis||null,
        graph:dossier?.graph||null,risk:dossier?.risk||null,source_links:dossier?.source_links||[],gmgn:gmgn||null,
        error:found?null:problems.join(' · ')||'No verified token observations available'};
    }
  }
}
