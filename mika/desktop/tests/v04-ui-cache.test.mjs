import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
import {createSecurityCache} from '../ui/security-cache.mjs';
const mints=['So11111111111111111111111111111111111111112','A'.repeat(43),'B'.repeat(43)];
test('security cache preserves original age and deduplicates within TTL',async()=>{
 let calls=0,time=1000;const cache=createSecurityCache({clock:()=>time,getToken:async()=>{calls++;return {gmgn:{security:{data:{bundler_trader_amount_rate:0}}}}},ttlMs:60000});
 const a=await cache.get(mints[0]);time+=1000;const b=await cache.get(mints[0]);
 assert.equal(calls,1);assert.equal(a.observedAt,b.observedAt);assert.equal(b.evidence.metrics.bundler_ratio,0);
});
test('security cache limits concurrency to two',async()=>{
 let started=0,release=[];const cache=createSecurityCache({getToken:()=>new Promise(r=>{started++;release.push(r)}),concurrency:2,clock:()=>1000});
 const all=mints.map(m=>cache.get(m));await new Promise(r=>setTimeout(r,15));assert.equal(started,2);
 release.shift()({gmgn:{security:{data:{bundler_trader_amount_rate:.2}}}});await new Promise(r=>setTimeout(r,15));assert.equal(started,3);
 release.forEach(r=>r({gmgn:{security:{data:{}}}}));await Promise.all(all);
});
test('security cache backs off on provider error and never treats empty record as safe',async()=>{
 let calls=0;const c=createSecurityCache({clock:()=>1000,getToken:async()=>{calls++;throw Error('429 rate limit')}});
 assert.equal((await c.get(mints[0])).status,'UNAVAILABLE');assert.equal((await c.get(mints[0])).status,'UNAVAILABLE');assert.equal(calls,1);
});
test('three tabs only, no Ask chat, and research filter controls',()=>{
 const html=readFileSync(new URL('../ui/index.html',import.meta.url),'utf8');
 const app=readFileSync(new URL('../ui/app.mjs',import.meta.url),'utf8');
 assert.deepEqual([...html.matchAll(/class="tab[^\"]*" data-tab="([^\"]+)"/g)].map(m=>m[1]),['scan','traction','watch']);
 assert.doesNotMatch(html,/view-ask|askForm|chatModel/);
 assert.match(html,/maxMarketCap/);assert.match(html,/maxBundlerRatio/);assert.match(html,/customAccent/);
 assert.match(app,/classifyCandidate|partitionCandidates/);assert.match(app,/buildTokenLinks/);
});
