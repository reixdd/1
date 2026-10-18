/** Risk evidence is never established by the language model. */
const unwrap=val=>val?.data?.data??val?.data??val;
const present=(obj,key)=>Object.hasOwn(obj,key) && obj[key]!==null && obj[key]!==undefined;
export function extractGMGNEvidence(bundle){
 if(bundle?.security?.ok===false)return [];
 const src=unwrap(bundle?.security);if(!src||typeof src!=='object'||Array.isArray(src))return [];
 const fields=[
  ['renounced_mint','mint_authority',value=>value===false?'HIGH':'NONE'],
  ['renounced_freeze_account','freeze_authority',value=>value===false?'HIGH':'NONE'],
  ['top_10_holder_rate','holder_concentration',value=>Number(value)>1?'UNKNOWN':Number(value)>=0.8?'HIGH':Number(value)>=0.5?'MEDIUM':'NONE'],
  ['bundler_trader_amount_rate','bundler_rate',value=>Number(value)>1?'UNKNOWN':Number(value)>0.5?'HIGH':Number(value)>0.15?'MEDIUM':'NONE'],
  ['suspected_insider_hold_rate','insider_holdings',value=>Number(value)>1?'UNKNOWN':Number(value)>0.4?'HIGH':Number(value)>0.1?'MEDIUM':'NONE'],
  ['is_wash_trading','wash_trading',value=>value===true?'HIGH':'NONE'],
  ['rug_ratio','rug_ratio',value=>Number(value)>=0.6?'HIGH':'NONE']
 ];
 const out=[];for(const [sourceField,field,getSeverity] of fields){if(!present(src,sourceField))continue;
   const value=src[sourceField];if(typeof value!=='boolean' && (!Number.isFinite(Number(value))||value===''))continue;
   out.push({field,value,status:'PROVIDER_REPORTED',severity:getSeverity(value),provider:'GMGN',source_field:sourceField,observed_at:Date.now()/1000});}
 return out;
}
export function classifyRisk(findings=[]){
 const good=Array.isArray(findings)?findings.filter(f=>f&&typeof f==='object'):[];
 const unknowns=['mint_authority','freeze_authority','holder_concentration'].filter(field=>!good.some(f=>f.field===field && f.status!=='UNKNOWN'));
 const conflicts=good.filter(f=>f.status==='CONFLICTED');
 const severe=good.filter(f=>f.severity==='HIGH'||f.severity==='MEDIUM');
 const verifiedHigh=severe.some(f=>f.severity==='HIGH' && f.status==='ONCHAIN_VERIFIED');
 const serious=verifiedHigh?'HIGH_RISK':severe.length||conflicts.length?'NEEDS_REVIEW':unknowns.length?'UNVERIFIED':'NO_MAJOR_FLAGS_DETECTED';
 return {verdict:serious,findings:good,unknowns,reasons:[...severe,...conflicts].map(f=>({field:f.field,classification:f.status,value:f.value??null,source:f.provider||null,severity:f.severity}))};
}
