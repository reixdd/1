import test from 'node:test';import assert from 'node:assert/strict';
import {createWebTransport} from '../transport.mjs';
test('same-origin API feed and quote calls use no native bridge',async()=>{
 const requests=[];const client=createWebTransport(async (url,options)=>{requests.push({url,options});return {ok:true,json:async()=>({rows:[],status:'OK'})}});
 assert.deepEqual(await client.feed(),{rows:[],status:'OK'});
 await client.quotes(['So11111111111111111111111111111111111111112']);assert.deepEqual(requests.map(r=>r.url),['/api/market/feed','/api/market/quotes?mint=So11111111111111111111111111111111111111112']);
});
test('web chat rejects arbitrary API paths and invalid Solana token inputs',async()=>{
 const client=createWebTransport(async()=>({ok:true,json:async()=>({})}));await assert.rejects(()=>client.quotes(['https://evil.test/foo']),/Invalid Solana/);
 assert.equal(typeof client.coreGet,'undefined');
});
test('web transport returns server error status instead of fake response',async()=>{
 const client=createWebTransport(async()=>({ok:false,status:429,json:async()=>({error:'QUOTA_REACHED'})}));await assert.rejects(()=>client.submitChat('hi'),/QUOTA_REACHED/);
});
