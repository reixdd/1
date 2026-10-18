import test from 'node:test';import assert from 'node:assert/strict';
import {admit,claim,complete,lookup,prune,emptyState} from '../queue-state.mjs';
const t=Date.UTC(2026,9,18,17,0,0);
test('queue admits a bounded job and exposes results only to matching session',()=>{
 const s=emptyState();const a=admit(s,{session:'A',text:'Hi MIKA',now:t,id:'01234567-1234-4123-a123-012345678901'});assert.equal(a.ok,true);
 assert.equal(lookup(s,a.id,'B',t).ok,false);assert.equal(lookup(s,a.id,'A',t).status,'queued');
 const c=claim(s,{lease:'lease123',now:t+1000});assert.equal(c.id,a.id);assert.equal(complete(s,{id:a.id,lease:'bad',answer:'hi',now:t+2000}).ok,false);
 assert.equal(complete(s,{id:a.id,lease:'lease123',answer:'hi',now:t+2000}).ok,true);
 assert.equal(complete(s,{id:a.id,lease:'lease123',answer:'hi',now:t+3000}).ok,false);
 assert.equal(lookup(s,a.id,'A',t+2000).answer,'hi');
});
test('session burst and queue quota return explicit 429 instead of overflowing',()=>{
 const s=emptyState();let good=0;for(let i=0;i<5;i++){const r=admit(s,{session:'A',text:'hello',now:t,id:`${i}`});if(r.ok)good++;}assert.equal(good,3);assert.equal(s.queue.length,3);
});
test('global capacity enforces one active and eight pending and daily cap',()=>{
 const s=emptyState();assert.equal(admit(s,{session:'S0',text:'hi',now:t,id:'0'}).ok,true);
 const active=claim(s,{now:t+100,lease:'lease_1'});assert.ok(active);
 for(let i=1;i<=8;i++){const r=admit(s,{session:`S${i}`,text:'hi',now:t,id:`${i}`});assert.equal(r.ok,true)}
 assert.equal(admit(s,{session:'10',text:'hi',now:t,id:'last'}).ok,false);
 assert.equal(claim(s,{now:t+200,lease:'lease_2'}),null);
});
test('stale jobs eventually expire without leaking content',()=>{const s=emptyState();const a=admit(s,{session:'A',text:'hi',id:'1',now:t});prune(s,t+61*60*1000);assert.equal(lookup(s,a.id,'A',t+61*60*1000).ok,false)});
test('invalid model commands and oversized messages cannot enter queue',()=>{const s=emptyState();assert.equal(admit(s,{session:'A',text:'x'.repeat(601),now:t,id:'bad'}).ok,false);assert.equal(admit(s,{session:'A',text:'hi',model:'http://127.0.0.1:11434',now:t,id:'bad2'}).ok,false)});
