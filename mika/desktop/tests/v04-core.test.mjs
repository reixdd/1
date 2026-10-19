import test from 'node:test';
import assert from 'node:assert/strict';
import {projectLaunchEvidence,projectTokenEvidence,mergeEvidence,formatRatio} from '../ui/security-evidence.mjs';
import {classifyCandidate,partitionCandidates,sortCandidates} from '../ui/research-filter.mjs';
import {gmgnTokenUrl,sourceXUrl,buildTokenLinks} from '../ui/token-links.mjs';
import {summarizeTokenEvidence} from '../ui/research-summary.mjs';
import {normalizeCreatorClaim,normalizeCreatorEvent,summarizeCreatorHistory} from '../ui/creator-evidence.mjs';
import {createCreatorCache} from '../ui/creator-cache.mjs';
import {normalizeAccent,migratePreferences} from '../ui/theme.mjs';
const mint='So11111111111111111111111111111111111111112';
const second='A'.repeat(43);
test('GMGN explicit zero preserved with source and timestamps',()=>{
 const v=projectLaunchEvidence({bundler_trader_amount_rate:0,top_10_holder_rate:0.2},{source:'GMGN Trenches',observedAt:123});
 assert.equal(v.metrics.bundler_ratio,0);assert.equal(v.metrics.top10_holder_ratio,.2);
 assert.equal(v.provenance.bundler_ratio.observed_at,123);assert.equal(formatRatio(0),'0%');assert.equal(formatRatio(null),'Unknown');
});
test('nested security and ambiguous percentages stay unknown without unstated conversions',()=>{
 const detail=projectTokenEvidence({security:{ok:true,data:{data:{bundler_trader_amount_rate:.28,top_10_holder_rate:40}}}},{observedAt:456});
 assert.equal(detail.metrics.bundler_ratio,.28);assert.equal(detail.metrics.top10_holder_ratio,null);
 assert.equal(detail.unknowns.top10_holder_ratio,'ambiguous_value');
 assert.equal(projectTokenEvidence({security:{ok:false}},{observedAt:9}).metrics.bundler_ratio,null);
 const a=projectLaunchEvidence({bundler_trader_amount_rate:.12},{source:'GMGN',observedAt:1});
 assert.equal(mergeEvidence(a,detail).metrics.bundler_ratio,.28);
});
test('30k and 30 percent strict user filters do not silently pass unknown metrics',()=>{
 const config={maxMarketCap:30000,maxBundlerRatio:.30,enableCap:true,enableBundler:true};
 const mk=(market_cap,bundler_rate)=>({contract:mint,market_cap,bundler_rate});
 assert.equal(classifyCandidate(mk(29999,.29),config),'WITHIN');
 assert.equal(classifyCandidate(mk(30000,.29),config),'OUTSIDE');
 assert.equal(classifyCandidate(mk(20000,.30),config),'OUTSIDE');
 assert.equal(classifyCandidate(mk(20000,null),config),'UNVERIFIED');
 assert.equal(classifyCandidate(mk(null,.2),config),'UNVERIFIED');
 assert.equal(classifyCandidate(mk(50000,null),config),'OUTSIDE');
 assert.deepEqual(Object.keys(partitionCandidates([mk(1,.1),mk(2,null),mk(90000,.2)],config)),['within','outside','unverified']);
 assert.deepEqual(sortCandidates([{contract:mint,volume_5m:4},{contract:second,volume_5m:5}],'volume5m').map(x=>x.contract),[second,mint]);
});
test('GMGN url preserves exact mint and X source rejects fake hosts',()=>{
 assert.equal(gmgnTokenUrl(mint),`https://gmgn.ai/sol/token/${mint}`);
 assert.equal(gmgnTokenUrl('invalid'),null);
 assert.equal(sourceXUrl({twitter:'https://x.com.evil.xyz/foo'}),null);
 assert.equal(sourceXUrl({twitter_username:'_real_handle'}),'https://x.com/_real_handle');
 assert.equal(sourceXUrl({symbol:'LOOKS_OFFICIAL'}),null);
 assert.equal(buildTokenLinks({contract:mint,socials:[{kind:'x',url:'https://x.com/realtoken'}]}).x,'https://x.com/realtoken');
});
test('synopsis explains observed facts and unknowns without endorsing purchase',()=>{
 const result=summarizeTokenEvidence({market_cap:9000,volume_5m:2200,buys_5m:5,sells_5m:17},{metrics:{bundler_ratio:0.25,top10_holder_ratio:null},provenance:{bundler_ratio:{source:'GMGN',observed_at:100}}});
 assert.match(result.headline,/GMGN|bundler/i);assert.match(result.detail,/unknown|unverified/i);
 assert.doesNotMatch(result.headline+' '+result.detail,/buy now|safe coin|guaranteed/i);
});
test('creator roles require evidence; transfers not sales; ticker never establishes creator identity',()=>{
 const claim=normalizeCreatorClaim({creator:second,role:'creator',signature:'abcd',slot:123,decoder:'pump-v1'},{mint,source:'SOLANA_RPC',observedAt:44});
 assert.equal(claim.evidence_level,'ONCHAIN_VERIFIED');
 assert.equal(normalizeCreatorClaim({creator:second,role:'funder'},{mint,source:'GMGN',observedAt:44}).role,'FUNDER');
 assert.equal(normalizeCreatorEvent({mint,actor_pubkey:second,event_type:'TOKEN_TRANSFER',signature:'abc'}).event_type,'TOKEN_TRANSFER');
 assert.equal(summarizeCreatorHistory([{mint,creator_pubkey:second,evidence_level:'ONCHAIN_VERIFIED'},{mint:second,creator_pubkey:second,evidence_level:'ONCHAIN_VERIFIED'}],[],second).verified_launch_count,2);
 assert.equal(summarizeCreatorHistory([],[],second).coverage,'UNKNOWN');
});
test('creator memory deduplicates and persists without erasing watchlist',()=>{
 const mem=new Map([['mika-preferences-v1',JSON.stringify({watched:[`sol:${mint}`]})]]);
 const storage={getItem:k=>mem.get(k)||null,setItem:(k,v)=>mem.set(k,v)};
 const cache=createCreatorCache(storage,{now:()=>10000,ttlMs:86400000});
 const e=normalizeCreatorClaim({creator:second,role:'creator',signature:'sig',slot:1,decoder:'pump-v1'},{mint,source:'SOLANA_RPC',observedAt:1});
 cache.saveEvidence(e);cache.saveEvidence(e);
 assert.equal(cache.launchesFor(second).length,1);
 const reload=createCreatorCache(storage,{now:()=>10000});assert.equal(reload.launchesFor(second).length,1);
 assert.deepEqual(JSON.parse(mem.get('mika-preferences-v1')).watched,[`sol:${mint}`]);
});
test('theme validates custom colors and protects watchlist migration',()=>{
 assert.equal(normalizeAccent('#A78BFA').hex,'#A78BFA');assert.equal(normalizeAccent('rose').name,'rose');
 assert.equal(normalizeAccent('url(javascript:x)'),null);
 assert.equal(migratePreferences({watched:['sol:x'],accent:'violet'}).watched[0],'sol:x');
});
