import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {safeImageUrl,normalizeSocials} from '../ui/token-media.mjs';
import {normalizeDexQuotes,normalizeTrenches} from '../ui/live-feed.mjs';
import {extractGMGNEvidence} from '../ui/risk.mjs';
import {buySellMix,tractionSignal} from '../ui/traction.mjs';
const mint='So11111111111111111111111111111111111111112';
test('public HTTPS image URLs match the DIT acceptance pattern; local and unsafe URLs reject',()=>{
 assert.equal(safeImageUrl('https://media.communitycdn.net/coin.png'),'https://media.communitycdn.net/coin.png');
 assert.equal(safeImageUrl('ipfs://bafytest'),'https://ipfs.io/ipfs/bafytest');
 for(const v of ['javascript:alert(1)','http://valid.site/photo','https://127.0.0.1/x','https://localhost/x','https://192.168.1.1/','https://example.invalid/img'])assert.equal(safeImageUrl(v),null);
});
test('DEX platform/handle X social is never inferred without provider metadata',()=>{
 assert.equal(normalizeSocials([{platform:'twitter',handle:'official_tag'}])[0]?.url,'https://x.com/official_tag');
 assert.deepEqual(normalizeSocials([{platform:'twitter',handle:'bad/injection'}]),[]);
});
test('DEX transaction flow and five minute price change can be shown without historical snapshots',()=>{
 const [quote]=normalizeDexQuotes([{chainId:'solana',dexId:'pumpswap',baseToken:{address:mint,name:'Test',symbol:'T'},txns:{m5:{buys:4,sells:16}},priceChange:{m5:-5.2}}],[mint]);
 assert.equal(quote.buys_5m,4);assert.equal(quote.sells_5m,16);assert.equal(quote.price_change_5m_pct,-5.2);
 assert.deepEqual(buySellMix(quote),{buys:4,sells:16,buyShare:20,total:20,label:'SELL-HEAVY'});
 assert.deepEqual(tractionSignal(quote),{direction:'down',label:'5m price −5.2%',source:'provider price change'});
 assert.equal(buySellMix({buys_5m:null,sells_5m:0}),null);
 assert.equal(tractionSignal({price_change_5m_pct:null}),null);
});
test('GMGN bundled holding evidence remains source-labelled and ambiguous units remain unknown',()=>{
 const [row]=normalizeTrenches({data:{new_creation:[{address:mint,dexId:'pumpfun',bundler_trader_amount_rate:0.45,top_10_holder_rate:0.89}]}});
 assert.equal(row.bundler_rate,0.45);assert.equal(row.holder_concentration_rate,0.89);
 const findings=extractGMGNEvidence({security:{data:{bundler_trader_amount_rate:0.45,top_10_holder_rate:0.89}}});
 assert.equal(findings.find(x=>x.field==='bundler_rate').severity,'MEDIUM');
 assert.equal(findings.find(x=>x.field==='holder_concentration').severity,'HIGH');
 assert.ok(findings.every(x=>x.status==='PROVIDER_REPORTED'));
 assert.equal(extractGMGNEvidence({security:{data:{bundler_trader_amount_rate:45}}})[0].severity,'UNKNOWN');
});
test('screen shows interactive flow versus market cap and unverified screening state',()=>{
 const app=readFileSync(new URL('../ui/app.mjs',import.meta.url),'utf8');
 const css=readFileSync(new URL('../ui/styles.css',import.meta.url),'utf8');
 for(const pattern of [/buySellMix\(/,/tractionSignal\(/,/5m BUY\/SELL FLOW/,/Market cap scale/,/Bundler\/holder checks unavailable/,/brokenArtwork/,/Promise\.allSettled/,/slice\(0,2\)/]) assert.match(app,pattern);
 assert.match(css,/\.flow-meter\{/);assert.match(css,/\.risk-note\.unknown\{/);
});