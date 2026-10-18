/** Only source-attributed HTTPS links, never inferred identities. */
export function safeExternalUrl(value) {
 if (typeof value!=='string' || value.length>1024) return null;
 try {const u=new URL(value);return u.protocol==='https:' && !u.username && !u.password && !u.port && !/\s/.test(value) ? u.href : null;}catch{return null;}
}
const IMAGE_HOSTS=new Set(['cdn.dexscreener.com','dd.dexscreener.com','coin-images.coingecko.com','assets.coingecko.com','coin-images.geckoterminal.com','images.geckoterminal.com','ipfs.io','gateway.pinata.cloud','cf-ipfs.com','arweave.net','pump.mypinata.cloud']);
export function safeImageUrl(url){const safe=safeExternalUrl(url);return safe&&IMAGE_HOSTS.has(new URL(safe).hostname.toLowerCase())?safe:null;}
export function normalizeSocials(input){
 const items=Array.isArray(input)?input:[];const result=[];
 for(const entry of items){
  const raw=typeof entry==='object' && entry?entry:{};
  const url=safeExternalUrl(raw.url||raw.link);
  if(!url)continue;
  const u=new URL(url),host=u.hostname.toLowerCase();
  const kind=String(raw.type||raw.kind||'').toLowerCase();
  if((kind==='twitter'||kind==='x') && ['x.com','twitter.com','www.x.com','www.twitter.com'].includes(host) && u.pathname.length>1){
   if(!result.some(x=>x.kind==='x'))result.push({kind:'x',url});
  }
 }
 return result;
}
export function marketCapRelative(cap,max){
 const valid=v=>typeof v==='number' && Number.isFinite(v) && v>=0;
 if(!valid(cap)||!valid(max)||max<=0)return null;
 return Math.min(100,Math.max(0,(cap/max)*100));
}
