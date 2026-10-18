import {finite} from './domain.mjs';
/** Compares like-for-like observations, no price forecast. */
export function compareSnapshots(a,b){
 if(!a||!b || a.token_key!==b.token_key || (a.pool||null)!==(b.pool||null) || a.provider!==b.provider)return [];
 const previous=finite(a.observed_at),current=finite(b.observed_at);
 if(previous===null||current===null||current<=previous)return [];
 const events=[];
 for(const metric of ['volume_5m','liquidity']){
  const x=finite(a[metric]),y=finite(b[metric]);if(x===null||y===null||x<=0)continue;
  const change=(y-x)/x;
  const kind=metric==='volume_5m' ? change>=.25?'ACTIVITY_INCREASING':change<=-.25?'ACTIVITY_WEAKENING':null : change<=-.25?'LIQUIDITY_CHANGE':null;
  if(!kind)continue;
  events.push({kind,event_id:`${a.token_key}:${a.pool||'-'}:${a.provider}:${metric}:${previous}:${current}`,token_key:a.token_key,provider:a.provider,pool:a.pool||null,
     previous_at:previous,current_at:current,previous_value:x,current_value:y,change_pct:Number((change*100).toFixed(1)),metric});
 }
 return events;
}
export function uniqueEvents(events){return [...new Map((events||[]).map(x=>[x.event_id,x])).values()]}
