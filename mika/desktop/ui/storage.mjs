import {normalizeSocials} from './token-media.mjs';
const KEY='mika-preferences-v1';
const defaults={accent:'violet',mode:'half',mood:'focused',animation:'subtle',alwaysOnTop:true,watched:[],snapshots:{},firstSeen:{},events:[],tokenMeta:{},researchFilters:{maxMarketCap:30000,maxBundlerRatio:.30,enableCap:true,enableBundler:true,sort:'volume5m',view:'within'},density:'comfortable',customAccent:null};
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
    socials:normalizeSocials([...(Array.isArray(row.socials)?row.socials:[]),...(Array.isArray(old.socials)?old.socials:[])]),
    source_url:row.source_url||old.source_url||null,
   };
   state.tokenMeta={...state.tokenMeta,[mint]:next};
   const keys=Object.keys(state.tokenMeta);
   if(keys.length>250)delete state.tokenMeta[keys[0]];
   save();
  },
  researchFilters:()=>{const f={...defaults.researchFilters,...state.researchFilters};return {...f,view:f.view==='review'?'within':f.view};},
  setResearchFilters:patch=>{state.researchFilters={...defaults.researchFilters,...state.researchFilters,...patch};save()},
  setCustomAccent:hex=>{state.customAccent=hex;save()},
  setDensity:density=>{state.density=density;save()},
  setWatched:(key,on)=>{const set=new Set(state.watched);on?set.add(key):set.delete(key);state.watched=[...set].slice(-250);save()},
  setPreference:(key,value)=>{if(['accent','mode','mood','animation','alwaysOnTop','density'].includes(key)){state[key]=value;save()}},
  recentSnapshot:key=>state.snapshots?.[key]||null,
   firstSeenSnapshot:(key,provider)=>provider?(state.firstSeen?.[key+':'+provider]||
    (state.firstSeen?.[key]?.provider===provider?state.firstSeen[key]:null)||null):
    (state.firstSeen?.[key]||Object.entries(state.firstSeen||{}).find(([name])=>name.startsWith(key+':'))?.[1]||null),
  saveSnapshot:(key,snapshot)=>{
    const firstKey=key+':'+String(snapshot?.provider||'unknown');
    if(snapshot && snapshot.market_cap>0 && !state.firstSeen?.[firstKey]){state.firstSeen={...state.firstSeen,[firstKey]:snapshot};const firstKeys=Object.keys(state.firstSeen);if(firstKeys.length>250)delete state.firstSeen[firstKeys[0]];}
    state.snapshots={...state.snapshots,[key]:snapshot};const keys=Object.keys(state.snapshots);if(keys.length>250)delete state.snapshots[keys[0]];save()},
  events:()=>[...state.events],
  saveEvents:items=>{state.events=[...new Map([...items,...state.events].map(x=>[x.event_id,x])).values()].slice(0,150);save()},
 };
}
