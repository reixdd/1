import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeTrenches,normalizeGeckoNewPools,normalizeDexQuotes,mergeLiveRows,pumpProof} from '../ui/live-feed.mjs';

const A='2qs8375HmKb9eLknpAVp9jR56qYi5vU6svJmrA5pump';
const B='So11111111111111111111111111111111111111112';
test('reads documented GMGN new_creation / pump / completed sections',()=>{
 const out=normalizeTrenches({data:{new_creation:[{address:A,symbol:'ROLL',launchpad_platform:'Pump.fun',market_cap:2300}],pump:[{address:B,symbol:'NOPE',launchpad_platform:'LetsBonk'}],completed:[]}});
 assert.equal(out.length,1);assert.equal(out[0].contract,A);assert.equal(out[0].source,'GMGN');
});
test('GMGN empty return means no evidence; does not admit unrelated launchpads',()=>{
 assert.equal(normalizeTrenches({data:{new_creation:[{address:B,symbol:'X'}]}}).length,0);
});
test('GeckoTerminal only admits confirmed Pump.fun DEX relationships',()=>{
 const body={data:[{id:'solana_poolA',attributes:{address:'poolA',launchpad_platform:'Pump.fun',name:'ROLL / SOL',reserve_in_usd:'4000',pool_created_at:'2026-10-18T20:00:00Z',transactions:{m5:{buys:2,sells:1}},volume_usd:{m5:'850'}},relationships:{base_token:{data:{id:'solana_'+A}},dex:{data:{id:'solana_pump-fun'}}}},{id:'solana_poolB',attributes:{},relationships:{base_token:{data:{id:'solana_'+B}},dex:{data:{id:'raydium'}}}}],included:[{id:'solana_'+A,attributes:{name:'Rollage',symbol:'ROLL'}}]};
 const out=normalizeGeckoNewPools(body);assert.equal(out.length,1);assert.equal(out[0].contract,A);assert.equal(out[0].liquidity,4000);assert.equal(out[0].buys_5m,2);
});
test('dex quotes choose base mint and reject mismatched pair token',()=>{
 const x=normalizeDexQuotes([{chainId:'solana',dexId:'pumpfun',pairAddress:'pool',baseToken:{address:A,symbol:'ROLL',name:'Rollage'},marketCap:2500,liquidity:{usd:800},volume:{m5:200},txns:{m5:{buys:5,sells:2}}}], [A]);
 assert.equal(x.length,1);assert.equal(x[0].market_cap,2500);assert.equal(x[0].contract,A);
 assert.equal(normalizeDexQuotes([{chainId:'solana',dexId:'raydium',baseToken:{address:B}}], [A]).length,0);
});
test('merge keeps sources distinct and falls back without duplicating mint',()=>{
 const initial={contract:A,symbol:'ROLL',source:'GMGN',observed_at:10};
 const other={contract:A,symbol:'ROLL',source:'GeckoTerminal',observed_at:20,market_cap:null};
 const out=mergeLiveRows([[initial],[other]]);assert.equal(out.length,1);assert.equal(out[0].source,'GeckoTerminal');assert.deepEqual(out[0].providers,['GMGN','GeckoTerminal']);
});
test('pump proof must be source-specific rather than blindly checking ticker',()=>{
 assert.equal(pumpProof({dexId:'raydium',symbol:'PUMP'}),false);
 assert.equal(pumpProof({dexId:'pumpfun'}),true);
});

test('nested GMGN CLI response is parsed',()=>{ const body={ok:true,data:{data:{new_creation:[{address:A,symbol:'ROLL',launchpad_platform:'Pump.fun'}]}}};assert.equal(normalizeTrenches(body).length,1)});
