import test from 'node:test';import assert from 'node:assert/strict';
import worker,{MikaQueue} from '../worker.mjs';
function fakeEnvironment(){const db=new Map(),state={storage:{get:async k=>db.get(k),put:async(k,v)=>db.set(k,v)},blockConcurrencyWhile:async fn=>fn()};const obj=new MikaQueue(state,{});return {PUBLIC_ORIGIN:'https://mika.example',SESSION_HMAC_SECRET:'strong-test-only-session-key-for-hmac',LOCAL_CONNECTOR_SECRET:'strong-test-only-device-password',TURNSTILE_SECRET:'test-only-secret',MIKA_QUEUE:{idFromName:()=>123,get:()=>({fetch:(r,opts)=>obj.fetch(typeof r==='string'?new Request(r,opts):r)})}}}
const address='https://mika.example';
function post(path,body={},opts={}){return new Request(address+path,{method:'POST',headers:{Origin:address,'Content-Type':'application/json',...opts.headers},body:JSON.stringify(body)})}
test('public chat is never accessible without verified Turnstile and signed cookie',async()=>{
 const env=fakeEnvironment(),original=globalThis.fetch;globalThis.fetch=async()=>new Response(JSON.stringify({success:false}),{status:200});
 try{const invalid=await worker.fetch(post('/api/chat/session',{challenge:'captcha-token-with-adequate-length'}),env);assert.equal(invalid.status,403);
 assert.equal((await worker.fetch(post('/api/chat/jobs',{text:'hi'}),env)).status,401);
 const forged=await worker.fetch(post('/api/chat/jobs',{text:'hi'},{headers:{Cookie:'mika_chat=anything'}}),env);assert.equal(forged.status,401);
 const origin=await worker.fetch(post('/api/chat/session',{challenge:'captcha-token-with-adequate-length'},{headers:{Origin:'https://mika.example.evil.test'}}),env);assert.equal(origin.status,403);
 }finally{globalThis.fetch=original}
});
test('authenticated visitor job proceeds by device-only claim and response',async()=>{
 const env=fakeEnvironment(),original=globalThis.fetch;globalThis.fetch=async()=>new Response(JSON.stringify({success:true,hostname:'mika.example'}),{status:200});
 try{
 const r=await worker.fetch(post('/api/chat/session',{challenge:'captcha-token-with-adequate-length'}),env);
 assert.equal(r.status,200);const cookie=r.headers.get('Set-Cookie').split(';')[0];assert.match(cookie,/mika_chat=/);
 const jobRequest=post('/api/chat/jobs',{text:'Hello MIKA'},{headers:{Cookie:cookie}}),response=await worker.fetch(jobRequest,env);assert.equal(response.status,200);const job=await response.json();assert.ok(job.id);
 const unauth=await worker.fetch(post('/api/device/claim',{}),env);assert.equal(unauth.status,401);
 const headers={Authorization:'Bearer '+env.LOCAL_CONNECTOR_SECRET};
 const claimed=await worker.fetch(post('/api/device/claim',{},{headers}),env);assert.equal(claimed.status,200);const claim=(await claimed.json()).job;assert.equal(claim.id,job.id);
 const finished=await worker.fetch(post('/api/device/complete',{id:job.id,lease:claim.lease,answer:'Hello from local MIKA'},{headers}),env);assert.equal(finished.status,200);
 const read=await worker.fetch(new Request(address+'/api/chat/jobs/'+job.id,{headers:{Cookie:cookie}}),env);assert.equal((await read.json()).answer,'Hello from local MIKA');
 const replay=await worker.fetch(post('/api/device/complete',{id:job.id,lease:claim.lease,answer:'rewrite'},{headers}),env);assert.equal(replay.status,403);
 }finally{globalThis.fetch=original}
});
