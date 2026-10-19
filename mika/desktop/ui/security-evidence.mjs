/** Pure projections of provider evidence, never independently verified fraud claims. */
const unwrap=x=>x?.data?.data??x?.data??x;
const ratios={bundler_ratio:['bundler_trader_amount_rate','bundler_rate'],top10_holder_ratio:['top_10_holder_rate','holder_concentration_rate'],insider_ratio:['suspected_insider_hold_rate'],rug_ratio:['rug_ratio'],dev_team_hold_ratio:['dev_team_hold_rate','dev_hold_rate']};
const srcFields=x=>Object.fromEntries(Object.entries(ratios).map(([key,names])=>[key,names.find(name=>Object.hasOwn(x,name)&&x[name]!=null)]));
const ratio=x=>x!==null&&x!==undefined&&x!==''&&!['boolean','object'].includes(typeof x)&&Number.isFinite(Number(x))&&Number(x)>=0&&Number(x)<=1?Number(x):null;
function project(source,{name,observedAt}){
 const metrics={},provenance={},unknowns={};
 const fields=srcFields(source||{});
 for(const key of Object.keys(ratios)){
  const rawField=fields[key],raw=rawField?source[rawField]:null,v=ratio(raw);
  metrics[key]=v;
  if(v===null)unknowns[key]=rawField?'ambiguous_value':'not_reported';
  if(rawField)provenance[key]={source:name,observed_at:observedAt??null,raw_field:rawField,raw_value:raw,classification:v===null?'UNKNOWN':'PROVIDER_REPORTED'};
 }
 return {metrics,provenance,unknowns};
}
export function projectLaunchEvidence(raw,{source='GMGN Trenches',observedAt=null}={}){return project(raw,{name:source,observedAt});}
export function projectTokenEvidence(bundle,{observedAt=null}={}){
 const security=bundle?.security??bundle;
 const raw=security?.ok===false?{}:unwrap(security)||{};
 return project(raw,{name:'GMGN Token Security',observedAt});
}
export function mergeEvidence(launchEvidence,tokenEvidence){
 const metrics={},provenance={},unknowns={},conflicts=[];
 for(const key of Object.keys(ratios)){
  const a=launchEvidence?.metrics?.[key],b=tokenEvidence?.metrics?.[key];
  const chosen=b!==null&&b!==undefined?tokenEvidence:launchEvidence;
  metrics[key]=chosen?.metrics?.[key]??null;
  provenance[key]=chosen?.provenance?.[key]??null;
  if(a!=null&&b!=null&&Math.abs(a-b)>.05)conflicts.push({field:key,launch:a,security:b,sources:[launchEvidence.provenance?.[key],tokenEvidence.provenance?.[key]]});
  if(metrics[key]===null)unknowns[key]=chosen?.unknowns?.[key]||'not_reported';
 }
 return {metrics,provenance,conflicts,unknowns};
}
export function formatRatio(r){return typeof r==='number'&&Number.isFinite(r)&&r>=0&&r<=1?`${(100*r).toFixed(r===0?0:1).replace(/\.0$/,'')}%`:'Unknown';}
