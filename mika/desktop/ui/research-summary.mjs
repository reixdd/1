import {formatRatio} from './security-evidence.mjs';
import {finite} from './domain.mjs';
export function summarizeTokenEvidence(record={},evidence={}){
 const cap=finite(record.market_cap),buys=finite(record.buys_5m),sells=finite(record.sells_5m);
 const bundle=evidence?.metrics?.bundler_ratio;
 const provenance=evidence?.provenance?.bundler_ratio;
 const headline=bundle!=null?`GMGN-reported bundling ${formatRatio(bundle)}${provenance?.source?` (${provenance.source})`:''}.`:'Bundler exposure unverified.';
 const volume=finite(record.volume_5m);
 const detail=`${cap===null?'Market cap unverified':`Market cap $${Math.round(cap).toLocaleString()}`}; ${buys===null||sells===null?'5m buy/sell counts unknown':`${buys} buys and ${sells} sells in 5m`}${volume===null?'':`, $${Math.round(volume)} reported 5m volume`}. ${evidence?.metrics?.top10_holder_ratio==null?'Top-holder concentration unknown.':''}`.trim();
 return {headline,detail,unknowns:Object.keys(evidence.unknowns||{}),observedAt:provenance?.observed_at??null};
}
