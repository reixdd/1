const KEY='mika-creator-evidence-v1';
export function createCreatorCache(storage,{now=()=>Date.now(),ttlMs=86400000}={}){
 let state=[];try{const parsed=JSON.parse(storage.getItem(KEY)||'[]');if(Array.isArray(parsed))state=parsed}catch{}
 const valid=e=>e&&e.mint&&e.creator_pubkey&&e.role;
 const identity=e=>`${e.mint}:${e.role}:${e.signature||e.source+':'+e.observed_at}`;
 const save=()=>{try{storage.setItem(KEY,JSON.stringify(state.slice(-500)))}catch{}};
 return {
  saveEvidence:e=>{if(!valid(e))return false;const id=identity(e);state=state.filter(x=>identity(x)!==id);state.push(e);state=state.slice(-500);save();return true;},
  getCreator:mint=>state.filter(e=>e.mint===mint).sort((a,b)=>(b.observed_at||0)-(a.observed_at||0)),
  launchesFor:creator=>[...new Map(state.filter(e=>e.creator_pubkey===creator&&e.role==='CREATOR').map(e=>[e.mint,e])).values()],
  expire:()=>{state=state.filter(e=>e.observed_at==null||now()-e.observed_at*1000<ttlMs);save()},
 };
}
