import test from 'node:test';
import assert from 'node:assert/strict';
import { createClient } from '../ui/data.mjs';
const addr='So11111111111111111111111111111111111111112';
test('dossier 404 invokes read-only GMGN fallback without inventing market history',async()=>{
 const visited=[]; const client=createClient(async path=>{ visited.push(path); if(path.startsWith('/api/operator/dossier'))throw Error('404'); if(path.startsWith('/api/operator/gmgn/token'))return JSON.stringify({info:{ok:true,data:{symbol:'SOL'}}, security:{ok:false}}); return '{}'; });
 const result=await client.token('sol',addr); assert.equal(result.found,true); assert.equal(result.canonical,false); assert.equal(result.gmgn.info.data.symbol,'SOL'); assert.equal(result.market,null); assert.equal(result.observations.length,0); assert.equal(visited.length,2);
});
test('invalid JSON is reported, never rewritten as a live token',async()=>{
 const client=createClient(async()=>'{broken'); await assert.rejects(client.radar(),/invalid JSON/i);
});
test('offline status remains OFFLINE without a fake feed',async()=>{
 const client=createClient(async()=>{throw Error('ECONNREFUSED')}); const state=await client.status(); assert.equal(state.connection,'OFFLINE');
});
test('GMGN fetch failure is explicitly unavailable',async()=>{
 const client=createClient(async path=>{if(path.startsWith('/api/operator/dossier'))throw Error('404');throw Error('rate limited 429')});
 const result=await client.token('sol',addr);assert.equal(result.found,false);assert.equal(result.gmgn,null);assert.match(result.error,/429/);
});
test('empty core response cannot claim connected',async()=>{const c=createClient(async()=>JSON.stringify({}));assert.equal((await c.status()).connection,'OFFLINE')});
