const KEY='mika-preferences-v1';
const defaults={accent:'violet',mode:'half',mood:'focused',animation:'subtle',alwaysOnTop:true,watched:[],snapshots:{},events:[]};
export function createPreferencesStore(storage){
 let state;
 try{state={...defaults,...JSON.parse(storage.getItem(KEY)||'{}')}}catch{state={...defaults}}
 const save=()=>{try{storage.setItem(KEY,JSON.stringify(state))}catch{ /* blocked local storage: usable session fallback */}};
 return {
  preferences:()=>({...state,watched:[...state.watched]}),
  watched:()=>[...state.watched],
  setWatched:(key,on)=>{const set=new Set(state.watched);on?set.add(key):set.delete(key);state.watched=[...set].slice(-250);save()},
  setPreference:(key,value)=>{if(['accent','mode','mood','animation','alwaysOnTop'].includes(key)){state[key]=value;save()}},
  recentSnapshot:key=>state.snapshots?.[key]||null,
  saveSnapshot:(key,snapshot)=>{state.snapshots={...state.snapshots,[key]:snapshot};const keys=Object.keys(state.snapshots);if(keys.length>250)delete state.snapshots[keys[0]];save()},
  events:()=>[...state.events],
  saveEvents:items=>{state.events=[...new Map([...items,...state.events].map(x=>[x.event_id,x])).values()].slice(0,150);save()},
 };
}
