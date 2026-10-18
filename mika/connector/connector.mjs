import {validateConfig,buildOllamaMessages,sanitizeMarketContext,isMint} from './lib.mjs';
const config=validateConfig(process.env);
const relayPath=path=>new URL(path,config.origin).href;
const secretHeaders={'Authorization':`Bearer ${config.deviceToken}`,'Content-Type':'application/json'};
let running=true;process.on('SIGINT',()=>running=false);process.on('SIGTERM',()=>running=false);
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function relay(path,body){const r=await fetch(relayPath(path),{method:'POST',headers:secretHeaders,body:JSON.stringify(body),signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error(`Relay HTTP ${r.status}`);return r.json()}
async function research(mint){if(!isMint(mint))return null;try{
 const r=await fetch(`http://127.0.0.1:8768/api/operator/dossier?chain=sol&contract=${mint}&gmgn=true`,{signal:AbortSignal.timeout(7000)});
 if(!r.ok)return null;return sanitizeMarketContext(await r.json(),mint);
 }catch{return null;}}
async function runJob(job){const market=job.selectedMint?await research(job.selectedMint):null;
 const r=await fetch('http://127.0.0.1:11434/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:config.model,stream:false,messages:buildOllamaMessages(job,market),options:{temperature:0.6,num_predict:256}}),signal:AbortSignal.timeout(110000)});
 if(!r.ok)throw Error('Local AI model failed');
 const reply=await r.json();const answer=reply?.message?.content;
 if(typeof answer!=='string'||!answer.trim())throw Error('Local AI returned no text');return answer.slice(0,4096);
}
console.log(`MIKA public AI connector starting · model ${config.model} · outbound-only · public serving enabled`);
const heartbeatTimer=setInterval(()=>relay('/api/device/heartbeat',{}).catch(()=>{}),12000);
let heartbeat=0,delay=1000;
while(running){try{
 if(Date.now()-heartbeat>15000){await relay('/api/device/heartbeat',{});heartbeat=Date.now();}
 const result=await relay('/api/device/claim',{});
 if(!result.job){await wait(2000);continue;}
 const job=result.job;let answer=null,error=null;
 try{answer=await runJob(job)}catch(e){error=String(e?.message||'Model error').slice(0,100);}
 await relay('/api/device/complete',{id:job.id,lease:job.lease,answer,error});delay=1000;
 }catch(e){console.error('MIKA relay unavailable:',String(e?.message||e).slice(0,120));await wait(delay);delay=Math.min(30000,delay*2);}
}
clearInterval(heartbeatTimer);console.log('MIKA public connector stopped');
