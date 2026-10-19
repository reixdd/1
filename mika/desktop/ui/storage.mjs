const KEY='mika-preferences-v1';
const defaults={accent:'violet',mode:'half',mood:'focused',animation:'subtle',alwaysOnTop:true,watched:[],snapshots:{},events:[],tokenMeta:{},researchFilters:{maxMarketCap:30000,maxBundlerRatio:.30,enableCap:true,enableBundler:true,sort:'volume5m',view:'review'},density:'comfortable',customAccent:null};
export function createPreferencesStore(storage){
 let state;
 try{state={...defaults,...JSON.parse(storage.getItem(KEY)||'{}')}}catch{state={...defaults}}
 const save=()=>{try{storage.setItem(KEY,JSON.stringify(state))}catch{ /* blocked local storage: usable session fallback */}};
 return {
  preferences:()=>({...state,watched:[...state.watched]}),
  watched:()=>[...state.watched],
  tokenMeta:mint=>state.tokenMeta?.[mint]||null,
  saveTokenMeta:(mint,row)=>{
   if(!mint||!row)return;
   const old=state.tokenMeta?.[mint]||{};
   const next={
    symbol:String(row.symbol&&row.symbol!=='?'?row.symbol:old.symbol||'Unknown').slice(0,40),
    name:String(row.name&&row.name!=='Unknown'?row.name:old.name||'').slice(0,100),
    image_url:row.image_url||old.image_url||null,
    socials:Array.isArray(row.socials)&&row.socials.length?row.socials:old.socials||[],
    source_url:row.source_url||old.source_url||null,
   };
   state.tokenMeta={...state.tokenMeta,[mint]:next};
   const keys=Object.keys(state.tokenMeta);
   if(keys.length>250)delete state.tokenMeta[keys[0]];
   save();
  },
  researchFilters:()=>({...defaults.researchFilters,...state.researchFilters}),
  setResearchFilters:patch=>{state.researchFilters={...defaults.researchFilters,...state.researchFilters,...patch};save()},
  setCustomAccent:hex=>{state.customAccent=hex;save()},
  setDensity:density=>{state.density=density;save()},
  setWatched:(key,on)=>{const set=new Set(state.watched);on?set.add(key):set.delete(key);state.watched=[...set].slice(-250);save()},
  setPreference:(key,value)=>{if(['accent','mode','mood','animation','alwaysOnTop','density'].includes(key)){state[key]=value;save()}},
  recentSnapshot:key=>state.snapshots?.[key]||null,
  saveSnapshot:(key,snapshot)=>{state.snapshots={...state.snapshots,[key]:snapshot};const keys=Object.keys(state.snapshots);if(keys.length>250)delete state.snapshots[keys[0]];save()},
  events:()=>[...state.events],
  saveEvents:items=>{state.events=[...new Map([...items,...state.events].map(x=>[x.event_id,x])).values()].slice(0,150);save()},
 };
}
