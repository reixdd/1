import {finite} from './domain.mjs';
/** Deterministic observed 5-minute volume order, never a price prediction. */
export function rankTractionRows(rows,quotes=new Map(),limit=24){
 const volume=row=>finite(quotes.get(row.contract)?.volume_5m??row.volume_5m);
 return [...(rows||[])].filter(row=>row?.contract)
 .sort((a,b)=>(volume(b)??-1)-(volume(a)??-1))
 .slice(0,limit);
}
/** Most recently observed market activity event by Solana mint. */
export function latestActivityByMint(events){
 const map=new Map();
 for(const event of events||[]){
  if(typeof event?.token_key!=='string'||!event.token_key.startsWith('sol:'))continue;
  const mint=event.token_key.slice(4),previous=map.get(mint);
  if(!previous||(finite(event.current_at)??0)>(finite(previous.current_at)??0))map.set(mint,event);
 }
 return map;
}

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

/** Actual five-minute transaction mix, available from a single provider snapshot. */
export function buySellMix(row){
 const buys=finite(row?.buys_5m),sells=finite(row?.sells_5m);
 if(buys===null||sells===null||buys<0||sells<0||buys+sells<=0)return null;
 const buyShare=Math.round(buys/(buys+sells)*1000)/10;
 return {buys,sells,buyShare,total:buys+sells,label:buyShare>60?'BUY-HEAVY':buyShare<40?'SELL-HEAVY':'BALANCED'};
}
/** Five-minute price movement (provider field, not predicted volume growth). */
export function tractionSignal(row){
 const value=finite(row?.price_change_5m_pct);if(value===null)return null;
 return {direction:value>0?'up':value<0?'down':'flat',label:'5m price '+(value>0?'+':value<0?'−':'')+Math.abs(value).toFixed(1)+'%',source:'provider price change'};
}
