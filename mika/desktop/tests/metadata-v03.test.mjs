import test from 'node:test';
import assert from 'node:assert/strict';
import {safeImageUrl,normalizeSocials,marketCapRelative,safeExternalUrl} from '../ui/token-media.mjs';
import {normalizeDexQuotes,mergeLiveRows} from '../ui/live-feed.mjs';

const mint='So11111111111111111111111111111111111111112';
test('source-verified DexScreener images and X socials are preserved',()=>{
 const [p]=normalizeDexQuotes([{chainId:'solana',dexId:'pumpswap',pairAddress:mint,baseToken:{address:mint,name:'Sample',symbol:'SMPL'},marketCap:3500,info:{imageUrl:'https://cdn.dexscreener.com/image.png',socials:[{type:'twitter',url:'https://x.com/SampleToken'}],websites:[{url:'https://sample.org'}]}}],[mint]);
 assert.equal(p.image_url,'https://cdn.dexscreener.com/image.png');
 assert.equal(p.socials.find(x=>x.kind==='x').url,'https://x.com/SampleToken');
});
test('unsafe image URLs and X lookalike hosts are rejected',()=>{
 assert.equal(safeImageUrl('javascript:alert(1)'),null);
 assert.equal(safeImageUrl('http://example.com/a.png'),null);
 assert.equal(safeImageUrl('https://evil.example/path'),null); // untrusted image hosts remain placeholders/proxy
 assert.deepEqual(normalizeSocials([{type:'twitter',url:'https://x.com.evil.test/u'},{type:'twitter',url:'javascript:alert(1)'}]),[]);
 assert.equal(safeExternalUrl('data:text/html,a'),null);
});
test('metadata survives dedupe and empty strings do not overwrite artwork',()=>{
 const a={contract:mint,observed_at:11,image_url:'https://cdn.dexscreener.com/cover.png',socials:[{kind:'x',url:'https://x.com/smpl'}],source:'GMGN',market_cap:100};
 const b={contract:mint,observed_at:12,image_url:null,socials:[],source:'GeckoTerminal',market_cap:120};
 const [v]=mergeLiveRows([[a],[b]]);assert.equal(v.image_url,a.image_url);assert.deepEqual(v.socials,a.socials);
});
test('relative market cap bars retain missing values and zero ceiling',()=>{
 assert.equal(marketCapRelative(null,500),null);assert.equal(marketCapRelative(200,1000),20);assert.equal(marketCapRelative(5,0),null);assert.equal(marketCapRelative(1000,1000),100);
});
