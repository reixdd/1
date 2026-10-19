import {projectTokenEvidence} from './security-evidence.mjs';
import {validSolMint} from './token-links.mjs';
/** Limited demand-driven token security: preserve source-time separate from market quote updates. */
export function createSecurityCache({getToken,clock=()=>Date.now(),concurrency=2,ttlMs=60000}={}){
 const stored=new Map(),pending=new Map(),queue=[];let active=0;
 function drain(){while(active<concurrency&&queue.length){const task=queue.shift();active++;
  Promise.resolve().then(()=>getToken(task.mint)).then(result=>{
   const now=clock(),raw=result?.gmgn?.security;
   const supplied=raw?.data?.data?.observed_at??raw?.data?.observed_at??raw?.observed_at;
   const observedAt=Number.isFinite(Number(supplied))&&supplied!=null&&Number(supplied)>0?Number(supplied):null;
   const evidence=projectTokenEvidence(result?.gmgn??result,{observedAt});
   const hasEvidence=Object.values(evidence.metrics).some(x=>x!==null);
   const value={status:hasEvidence?'AVAILABLE':'UNVERIFIED',evidence,observedAt,fetchedAt:now,expiry:now+ttlMs};stored.set(task.mint,value);task.resolve(value);
  }).catch(err=>{const now=clock(),previous=stored.get(task.mint);const value={status:previous?.evidence?'DELAYED':'UNAVAILABLE',evidence:previous?.evidence??null,observedAt:previous?.observedAt??null,expiry:now+Math.min(60000,ttlMs),error:String(err?.message||err)};stored.set(task.mint,value);task.resolve(value);
  }).finally(()=>{active--;pending.delete(task.mint);drain()});}}
 return {
  peek:mint=>stored.get(mint)||null,
  status:mint=>stored.get(mint)?.status||'UNVERIFIED',
  get:mint=>{if(!validSolMint(mint))return Promise.resolve({status:'UNVERIFIED',evidence:null,observedAt:null});const entry=stored.get(mint);if(entry&&entry.expiry>clock())return Promise.resolve(entry);if(pending.has(mint))return pending.get(mint);
   const result=new Promise(resolve=>{queue.push({mint,resolve});drain()});pending.set(mint,result);return result;}
 };
}
