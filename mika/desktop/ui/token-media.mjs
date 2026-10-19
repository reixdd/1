/** Only source-attributed HTTPS links, never inferred identities. */
export function safeExternalUrl(value) {
 if (typeof value!=='string' || value.length>1024) return null;
 try {const u=new URL(value);return u.protocol==='https:' && !u.username && !u.password && !u.port && !/\s/.test(value) ? u.href : null;}catch{return null;}
}
/** DIT-compatible: render source-attributed public HTTPS token artwork. */
export function safeImageUrl(value){
 let candidate=value;
 if(typeof candidate==='string' && candidate.startsWith('ipfs://'))candidate='https://ipfs.io/ipfs/'+candidate.slice(7).replace(/^ipfs\//,'');
 if(typeof candidate==='string' && candidate.startsWith('ar://'))candidate='https://arweave.net/'+candidate.slice(5);
 const safe=safeExternalUrl(candidate);if(!safe)return null;
 const host=new URL(safe).hostname.toLowerCase().replace(/\.$/,'');
 if(!host.includes('.')||host==='localhost'||host.endsWith('.localhost')||host.endsWith('.local')||host.endsWith('.internal')||host.endsWith('.test')||host.endsWith('.example')||host.endsWith('.invalid'))return null;
 if(/^\d+(\.\d+){3}$/.test(host)||host.includes(':')||host.endsWith('.onion'))return null;
 return safe;
}
export function normalizeSocials(input){
 const entries=Array.isArray(input)?input:[],result=[];
 for(const entry of entries){
  const raw=entry && typeof entry==='object'?entry:{};
  const kind=String(raw.type||raw.kind||raw.platform||'').toLowerCase();
  if(!['twitter','x'].includes(kind))continue;
  const handle=typeof raw.handle==='string'?raw.handle.replace(/^@/,''):'';
  const candidate=raw.url||raw.link||(/^[a-zA-Z0-9_]{1,15}$/.test(handle)?'https://x.com/'+handle:null);
  const url=safeExternalUrl(candidate);if(!url)continue;
  const host=new URL(url).hostname.toLowerCase();
  if(['x.com','twitter.com','www.x.com','www.twitter.com'].includes(host)&&new URL(url).pathname.length>1&&!result.some(x=>x.kind==='x'))result.push({kind:'x',url});
 }
 return result;
}
export function marketCapRelative(cap,max){
 const valid=v=>typeof v==='number' && Number.isFinite(v) && v>=0;
 if(!valid(cap)||!valid(max)||max<=0)return null;
 return Math.min(100,Math.max(0,(cap/max)*100));
}
