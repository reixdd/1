const isMint=s=>typeof s==='string' && /^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(s);
/** Browser client knows ONLY same-origin public APIs. Native JARVIS/Ollama calls are impossible here. */
export function createWebTransport(fetchImpl=fetch){
 async function call(path,method='GET',body=null){
  if(!path.startsWith('/api/')||path.startsWith('//')||path.includes('..'))throw Error('Unexpected API path');
  const response=await fetchImpl(path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json'},...(body!==null?{body:JSON.stringify(body)}:{})});
  let json;try{json=await response.json()}catch{throw Error('Server returned an invalid response')}
  if(!response.ok)throw Error(json?.error||`API HTTP ${response.status}`);return json;
 }
 return {
  feed:()=>call('/api/market/feed'),
  quotes:async mints=>{const mint=mints?.[0];if(!isMint(mint))throw Error('Invalid Solana mint');return call(`/api/market/quotes?mint=${mint}`);},
  config:()=>call('/api/config'),
  session:challenge=>call('/api/chat/session','POST',{challenge}),
  submitChat:(text,selectedMint=null)=>call('/api/chat/jobs','POST',{text,...(selectedMint?{selected_mint:selectedMint}:{})}),
  chatStatus:id=>{if(!/^[0-9a-f-]{36}$/.test(id))throw Error('Invalid job ID');return call(`/api/chat/jobs/${id}`);},
  deviceStatus:()=>call('/api/chat/status'),
 };
}
