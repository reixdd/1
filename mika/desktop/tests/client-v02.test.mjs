import test from 'node:test';import assert from 'node:assert/strict';
import {createClient} from '../ui/data.mjs';
const A='2qs8375HmKb9eLknpAVp9jR56qYi5vU6svJmrA5pump';
test('live feed merges GMGN and Gecko only when launchpad proof exists',async()=>{
 const c=createClient(async p=>p.includes('/radar')?{items:[]}:p.includes('/trenches')?{ok:true,data:{new_creation:[{address:A,symbol:'A',launchpad_platform:'Pump.fun'}]}}:{},async command=>command==='market_gecko'?{data:[]}:[]);
 const r=await c.liveFeed();assert.equal(r.rows.length,1);assert.equal(r.rows[0].contract,A);assert.equal(r.sources.GMGN,'OK');
});
test('provider outage is source-local, no fake success',async()=>{
 const c=createClient(async()=>{throw Error('offline')},async command=>command==='market_gecko'?{data:[]}:[]);
 const r=await c.liveFeed();assert.equal(r.rows.length,0);assert.equal(r.sources.GMGN,'ERROR');assert.equal(r.sources.GeckoTerminal,'EMPTY');
});
test('quote responses normalize and preserve request identity',async()=>{
 const c=createClient(async()=>({}),async (command,args)=>{if(command==='market_dex'){assert.equal(args.mints[0],A);return [{chainId:'solana',dexId:'pumpfun',baseToken:{address:A},marketCap:3000}]}throw Error('unknown command')});
 const r=await c.quotes([A]);assert.equal(r.length,1);assert.equal(r[0].market_cap,3000);
});
test('chat passes chosen model and bounded context, supports casual messages',async()=>{
 const c=createClient(async()=>({}),async (command,args)=>{
  assert.equal(command,'ollama_chat');assert.equal(args.model,'qwen3.5:4b');assert.equal(args.history.at(-1).content,'How are you?');return 'Doing well!';
 });
 assert.equal(await c.chat('qwen3.5:4b',[{role:'user',content:'How are you?'}],{}),'Doing well!');
});
