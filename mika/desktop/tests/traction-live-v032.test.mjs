import test from 'node:test';
import assert from 'node:assert/strict';
import {safeImageUrl, normalizeSocials} from '../ui/token-media.mjs';
import {normalizeDexQuotes,normalizeTrenches} from '../ui/live-feed.mjs';
import {extractGMGNEvidence} from '../ui/risk.mjs';
import {tractionSignal,buySellMix} from '../ui/traction.mjs';
const mint='So11111111111111111111111111111111111111112';
test('DIT-compatible provider HTTPS token art is shown, but private and unsafe image links are rejected',()=>{
 assert.equal(safeImageUrl('https://image.example-cdn.net/artwork.png'),'https://image.example-cdn.net/artwork.png');
 for(const bad of ['javascript:alert(1)','http://image.example.com/file.png','https://localhost/admin','https://127.0.0.1:8768/token','https://192.168.1.15/x','https://foo.internal/a','https://user:pass@valid.com/a'])assert.equal(safeImageUrl(bad),null);
});
test('provider-supplied social platform/handle is accepted as a verified source field, never guessed',()=>{
 const out=normalizeSocials([{platform:'twitter',handle:'confirmed_h'},{type:'twitter',url:'https://x.com/official'}]);
 assert.equal(out[0].url,'https://x.com/confirmed_h');
 assert.equal(out.length,1);
 assert.deepEqual(normalizeSocials([{platform:'twitter',handle:'@hello/bad?param'}]),[]);
});
test('DEX five-minute price change and txns are preserved without fabricated history',()=>{
 const [row]=normalizeDexQuotes([{chainId:'solana',dexId:'pumpswap',baseToken:{address:mint,symbol:'M',name:'M'},priceChange:{m5:-12.4},txns:{m5:{buys:4,sells:16}},marketCap:20000}], [mint]);
 assert.equal(row.price_change_5m_pct,-12.4);assert.equal(row.buys_5m,4);assert.equal(row.sells_5m,16);
});
test('buy/sell activity bar uses immediate 5m counts without two snapshots',()=>{
 assert.deepEqual(buySellMix({buys_5m:1,sells_5m:3}),{buys:1,sells:3,buyShare:25,total:4,label:'SELL-HEAVY'});
 assert.equal(buySellMix({buys_5m:null,sells_5m:0}),null);
 assert.equal(buySellMix({buys_5m:0,sells_5m:0}),null);
 assert.equal(buySellMix({buys_5m:10,sells_5m:2}).label,'BUY-HEAVY');
});
test('negative DEX price movement can be visualized immediately, absent value stays unverified',()=>{
 assert.deepEqual(tractionSignal({price_change_5m_pct:-5.2}),{direction:'down',label:'5m price −5.2%',source:'provider price change'});
 assert.equal(tractionSignal({price_change_5m_pct:null}),null);
});
test('GMGN trenches bundler percentage is provider evidence, not proof or safe flag',()=>{
 const [row]=normalizeTrenches({data:{new_creation:[{address:mint,dexId:'pumpfun',symbol:'BUND',bundler_trader_amount_rate:0.46,top_10_holder_rate:0.89}]}});
 assert.equal(row.bundler_rate,0.46);
 assert.equal(row.holder_concentration_rate,0.89);
 const risk=extractGMGNEvidence({security:{data:{bundler_trader_amount_rate:0.46,top_10_holder_rate:0.89}}});
 assert.equal(risk.find(f=>f.field==='bundler_rate')?.severity,'MEDIUM');
 assert.equal(risk.find(f=>f.field==='holder_concentration')?.severity,'HIGH');
 assert.ok(risk.every(f=>f.status==='PROVIDER_REPORTED'));
});
import {readFileSync} from 'node:fs';
test('traction view has a clickable flow-versus-cap toggle and source-labelled signal',()=>{
 const app=readFileSync(new URL('../ui/app.mjs',import.meta.url),'utf8');
 assert.match(app,/buySellMix\(/);
 assert.match(app,/tractionMode/);
 assert.match(app,/5m BUY\/SELL FLOW/);
 assert.match(app,/Market cap scale/);
 assert.match(app,/tractionSignal\(/);
});
test('scan cards include explicit GMGN bundler and concentration evidence without safety guarantees',()=>{
 const app=readFileSync(new URL('../ui/app.mjs',import.meta.url),'utf8');
 assert.match(app,/bundler_rate/);
 assert.match(app,/holder_concentration_rate/);
 assert.match(app,/provider-reported/i);
});
test('image host errors do not repeatedly restart failing downloads every 1 second',()=>{
 const app=readFileSync(new URL('../ui/app.mjs',import.meta.url),'utf8');
 assert.match(app,/brokenArtwork/);
 assert.match(app,/now-\(brokenArtwork\.get/);
});
test('metadata lookup uses a small bounded batch rather than waiting minutes for first 30 cards',()=>{
 const app=readFileSync(new URL('../ui/app.mjs',import.meta.url),'utf8');
 assert.match(app,/\.slice\(0,2\)/);
 assert.match(app,/Promise\.allSettled/);
});
test('unverified bundled-token screening is explicitly labeled, not silently treated as safe',()=>{
 const app=readFileSync(new URL('../ui/app.mjs',import.meta.url),'utf8');
 assert.match(app,/Bundler: unverified/);
 assert.match(app,/Top 10: unverified/);
});
