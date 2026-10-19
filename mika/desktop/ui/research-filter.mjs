import {finite} from './domain.mjs';
const getCap=r=>finite(r?.market_cap??r?.market_cap_usd);
const getBundle=r=>finite(r?.bundler_rate??r?.gmgn?.bundler_ratio??r?.evidence?.metrics?.bundler_ratio);
export function classifyCandidate(row,{maxMarketCap=30000,maxBundlerRatio=.3,enableCap=true,enableBundler=true}={}){
 const cap=getCap(row),bundle=getBundle(row);
 if(enableCap&&cap!==null&&cap>=maxMarketCap)return 'OUTSIDE';
 if(enableBundler&&bundle!==null&&bundle>=maxBundlerRatio)return 'OUTSIDE';
 if((enableCap&&cap===null)||(enableBundler&&(bundle===null||bundle<0||bundle>1)))return 'UNVERIFIED';
 return 'WITHIN';
}
export function partitionCandidates(rows,filters){const p={within:[],outside:[],unverified:[]};for(const row of rows||[]){p[classifyCandidate(row,filters).toLowerCase()].push(row)}return p;}
export function sortCandidates(rows,sort='volume5m'){
 const keys={recent:'observed_at',volume5m:'volume_5m',marketCap:'market_cap'};
 const metric=r=>sort==='buySellImbalance'?((finite(r.buys_5m)??0)-(finite(r.sells_5m)??0)):finite(r[keys[sort]||'volume_5m'])??-Infinity;
 return [...(rows||[])].sort((a,b)=>metric(b)-metric(a)||String(a.contract||'').localeCompare(String(b.contract||'')));
}
