import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {pumpProof,normalizeTrenches,normalizeGeckoNewPools,normalizePumpMetadata,mergeLiveRows} from '../ui/live-feed.mjs';
import {normalizeSocials} from '../ui/token-media.mjs';
import {partitionCandidates,sortCandidates,eligibleSocial} from '../ui/research-filter.mjs';
import {createPreferencesStore} from '../ui/storage.mjs';
const mint='So11111111111111111111111111111111111111112';
const source=[{type:'twitter',url:'https://x.com/genuine_test'}];
test('Mayhem, Mayhem agents, and mixed PumpSwap-Mayhem records never pass Pump.fun discovery',()=>{
 for(const platform of ['pump_mayhem','pump_mayhem_agent','Pump Mayhem','pump_agent']){
  assert.equal(pumpProof({launchpad_platform:platform,dexId:'pumpswap'}),false,platform);
 }
 assert.equal(pumpProof({is_mayhem:true,dexId:'pumpfun'}),false);
 assert.equal(pumpProof({launchpad_platform:'Pump.fun',dexId:'pumpswap'}),true);
 assert.equal(normalizeTrenches({data:{new_creation:[
  {address:mint,launchpad_platform:'pump_mayhem',dexId:'pumpswap'},
  {address:mint,launchpad_platform:'Pump.fun',dexId:'pumpfun',symbol:'YES',twitter:'https://x.com/yes'}
 ]}}).length,1);
});
test('Gecko pool without verified launch origin cannot bypass Mayhem exclusion merely by trading on PumpSwap',()=>{
 const feed={data:[{attributes:{address:mint},relationships:{dex:{data:{id:'pumpswap'}},base_token:{data:{id:'solana_'+mint}}}}],included:[]};
 assert.deepEqual(normalizeGeckoNewPools(feed),[]);
});
test('Provider-supplied X, Telegram and website are normalized safely and never fabricated from ticker',()=>{
 const socials=normalizeSocials([{platform:'twitter',handle:'genuine_test'},{type:'telegram',url:'https://t.me/genuine_channel'},{type:'website',url:'https://example.org'}]);
 assert.deepEqual(socials.map(x=>x.kind),['x','telegram','website']);
 assert.equal(socials[0].url,'https://x.com/genuine_test');
 assert.deepEqual(normalizeSocials([{type:'telegram',url:'https://t.me.badhost.com/scam'},{type:'twitter',url:'javascript:alert(1)'}]),[]);
 assert.equal(eligibleSocial({symbol:'HI',socials:[]}),false);
 assert.equal(eligibleSocial({socials:source}),true);
 assert.equal(eligibleSocial({socials:[{kind:'telegram',url:'https://t.me/test'}]}),true);
 assert.equal(eligibleSocial({socials:[{kind:'website',url:'https://example.org'}]}),false);
});
test('Original Pump metadata carries telegram and top-level X account even with empty socials array',()=>{
 const item=normalizePumpMetadata({mint,symbol:'T',twitter:'https://x.com/real',telegram:'https://t.me/real',website:'https://real.example.org'},mint);
 assert.deepEqual(item.socials.map(x=>x.kind),['x','telegram','website']);
});
test('Traction only includes social-backed coins; unverified bundling never passes within limits',()=>{
 const rows=[
  {contract:mint,market_cap:8000,bundler_rate:.10,volume_5m:55,socials:source},
  {contract:'A'.repeat(43),market_cap:9000,bundler_rate:null,volume_5m:100,socials:source},
  {contract:'B'.repeat(43),market_cap:3000,bundler_rate:.05,volume_5m:5000,socials:[]},
  {contract:'C'.repeat(43),market_cap:34000,bundler_rate:.05,volume_5m:100,socials:source},
 ];
 const parts=partitionCandidates(rows,{maxMarketCap:30000,maxBundlerRatio:.30});
 assert.deepEqual(parts.within.map(x=>x.contract),[mint]);
 assert.equal(parts.unverified.length,1);assert.equal(parts.outside.length,1);
});
test('First-sighting market cap baseline persists and only same-source later observations produce a comparison',()=>{
 const memory=new Map(), io={getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v)};
 const store=createPreferencesStore(io);
 const first={token_key:'sol:'+mint,market_key:'sol:'+mint+':pool',provider:'GMGN',pool:'pool',market_cap:4000,observed_at:1000};
 const current={...first,market_cap:9000,observed_at:1200};
 store.saveSnapshot(first.market_key,first);
 assert.equal(store.firstSeenSnapshot(first.market_key)?.market_cap,4000);
 store.saveSnapshot(current.market_key,current);
 assert.equal(store.firstSeenSnapshot(first.market_key)?.market_cap,4000);
 assert.equal(createPreferencesStore(io).firstSeenSnapshot(first.market_key)?.market_cap,4000);
 const sorted=sortCandidates([{contract:'A',growth_since_seen_pct:25},{contract:'B',growth_since_seen_pct:130}], 'growth');
 assert.equal(sorted[0].contract,'B');
});
test('UI exposes mandatory social filter and readable settings drawer',()=>{
 const html=readFileSync(new URL('../ui/index.html',import.meta.url),'utf8');
 const app=readFileSync(new URL('../ui/app.mjs',import.meta.url),'utf8');
 const css=readFileSync(new URL('../ui/styles.css',import.meta.url),'utf8');
 assert.match(html,/Socials required/);
 assert.match(html,/value="growth"/);
 assert.match(css,/\.settings-content:not\(\[hidden\]\)\s*\{[^}]*position:\s*fixed/s);
 assert.match(app,/settingsContent[\s\S]*aria-expanded/);
});

test('X and Telegram links from different verified providers are both retained',()=>{
 const a={contract:mint,observed_at:5,source:'GMGN',socials:[{kind:'telegram',url:'https://t.me/genuine_channel'}]};
 const b={contract:mint,observed_at:6,source:'DEX Screener',socials:[{kind:'x',url:'https://x.com/genuine_test'}]};
 assert.deepEqual(mergeLiveRows([[a],[b]])[0].socials.map(v=>v.kind),['x','telegram']);
});
test('Saved token metadata does not lose an X profile when a newer source supplies Telegram',()=>{
 const memory=new Map(),io={getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v)};
 const s=createPreferencesStore(io);
 s.saveTokenMeta(mint,{symbol:'TEST',socials:[{kind:'x',url:'https://x.com/genuine_test'}]});
 s.saveTokenMeta(mint,{symbol:'TEST',socials:[{kind:'telegram',url:'https://t.me/genuine_channel'}]});
 assert.deepEqual(s.tokenMeta(mint).socials.map(v=>v.kind),['telegram','x']);
});

test('Gecko must know original launch platform, not only a Pump.fun DEX relationship',()=>{
 const data={data:[{attributes:{address:'pool-x'},relationships:{dex:{data:{id:'solana_pump-fun'}},base_token:{data:{id:'solana_'+mint}}}}],included:[]};
 assert.equal(normalizeGeckoNewPools(data).length,0);
});
test('A provider-reported bare X handle or x.com profile becomes a verified-source link',()=>{
 const mk=twitter=>normalizeTrenches({data:{new_creation:[{address:mint,launchpad_platform:'Pump.fun',twitter}]}})[0];
 assert.equal(mk('verified_token').socials.find(x=>x.kind==='x')?.url,'https://x.com/verified_token');
 assert.equal(mk('x.com/verified_token').socials.find(x=>x.kind==='x')?.url,'https://x.com/verified_token');
});

test('first-sighting baselines do not mix GMGN and DEX Screener observations for the same pool',()=>{
 const data=new Map(),io={getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v)},store=createPreferencesStore(io);
 const key='sol:'+mint+':pool';
 store.saveSnapshot(key,{market_key:key,provider:'GMGN',pool:'pool',market_cap:4000,observed_at:1000});
 store.saveSnapshot(key,{market_key:key,provider:'DEX Screener',pool:'pool',market_cap:9000,observed_at:1050});
 assert.equal(store.firstSeenSnapshot(key,'GMGN').market_cap,4000);
 assert.equal(store.firstSeenSnapshot(key,'DEX Screener').market_cap,9000);
});
