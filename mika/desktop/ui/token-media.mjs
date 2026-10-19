/** Only source-attributed HTTPS links, never inferred identities. */
export function safeExternalUrl(value) {
 if (typeof value!=='string' || value.length>1024) return null;
 try {const u=new URL(value);return u.protocol==='https:' && !u.username && !u.password && !u.port && !/\s/.test(value) ? u.href : null;}catch{return null;}
}
/** DIT-compatible artwork: any source-provided public HTTPS image; no arbitrary
 * fetch by the native bridge, and private/intranet destinations are rejected. */
export function safeImageUrl(value){
 let candidate=value;
 if(typeof candidate==='string' && candidate.startsWith('ipfs://'))candidate='https://ipfs.io/ipfs/'+candidate.slice(7).replace(/^ipfs\//,'');
 if(typeof candidate==='string' && candidate.startsWith('ar://'))candidate='https://arweave.net/'+candidate.slice(5);
 const safe=safeExternalUrl(candidate);if(!safe)return null;
 const host=new URL(safe).hostname.toLowerCase().replace(/\.$/,'');
 if(!host.includes('.') || host==='localhost'||host.endsWith('.localhost')||host.endsWith('.local')||host.endsWith('.internal')||host.endsWith('.test')||host.endsWith('.example')||host.endsWith('.invalid'))return null;
 if(/^\d+(\.\d+){3}$/.test(host)||host.includes(':')||host.endsWith('.onion'))return null;
 return safe;
}
export function normalizeSocials(input){
 const entries=Array.isArray(input)?input:[],result=[];
 for(const entry of entries){
  const raw=entry&&typeof entry==='object'?entry:{};
  const type=String(raw.type||raw.kind||raw.platform||'').toLowerCase();
  let kind=['twitter','x'].includes(type)?'x':
           ['telegram','tg'].includes(type)?'telegram':
           ['website','web','site'].includes(type)?'website':null;
  if(!kind)continue;
  const handle=typeof raw.handle==='string'?raw.handle.replace(/^@/,''):'';
  const account=kind==='x'&&/^[a-zA-Z0-9_]{1,15}$/.test(handle)?'https://x.com/'+handle:
                kind==='telegram'&&/^[a-zA-Z0-9_]{5,32}$/.test(handle)?'https://t.me/'+handle:null;
  let candidate=raw.url||raw.link||account;
  if(kind==='x'&&typeof candidate==='string'){
   const bare=candidate.replace(/^@/,'');
   if(/^[a-zA-Z0-9_]{1,15}$/.test(bare))candidate='https://x.com/'+bare;
   else if(/^(?:www\.)?(?:x\.com|twitter\.com)\/[a-zA-Z0-9_]{1,15}\/?$/i.test(candidate))candidate='https://'+candidate;
  }
  const url=safeExternalUrl(candidate);if(!url)continue;
  const host=new URL(url).hostname.toLowerCase(),path=new URL(url).pathname;
  if(kind==='x'&&!['x.com','www.x.com','twitter.com','www.twitter.com'].includes(host))continue;
  if(kind==='telegram'&&!['t.me','www.t.me','telegram.me','www.telegram.me'].includes(host))continue;
  if(kind==='website'){
    if(['localhost','127.0.0.1','0.0.0.0'].includes(host)||host.endsWith('.local')||host.endsWith('.internal')||/^(?:10|127|192|169|172)\.\d+\.\d+\.\d+$/.test(host))continue;
  }
  if(kind!=='website'&&path.length<=1)continue;
  if(!result.some(x=>x.kind===kind))result.push({kind,url});
 }
 return result;
}
export function marketCapRelative(cap,max){
 const valid=v=>typeof v==='number' && Number.isFinite(v) && v>=0;
 if(!valid(cap)||!valid(max)||max<=0)return null;
 return Math.min(100,Math.max(0,(cap/max)*100));
}
