import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {rankTractionRows, latestActivityByMint} from '../ui/traction.mjs';
import {normalizeTrenches, normalizeDexQuotes, metadataFromTokenDossier} from '../ui/live-feed.mjs';
import {createPreferencesStore} from '../ui/storage.mjs';
const styles=readFileSync(new URL('../ui/styles.css',import.meta.url),'utf8');
const app=readFileSync(new URL('../ui/app.mjs',import.meta.url),'utf8');
const ca='So11111111111111111111111111111111111111112';
test('scan entries cannot shrink into unreadable horizontal stripes',()=>{
 assert.match(styles,/\.token-card\s*\{[^}]*flex-shrink\s*:\s*0\s*;/s);
});
test('quote refresh retains keyed card and image nodes and scroll',()=>{
 assert.match(app,/const previous=new Map\(\[\.\.\.root\.querySelectorAll/);
 assert.match(app,/root\.replaceChildren\(fragment\);root\.scrollTop=oldScroll/);
});
test('traction orders observed five-minute activity as token rows, not raw event IDs',()=>{
 const rows=[{contract:ca,volume_5m:100,symbol:'A',market_cap:5000},{contract:'Ab11111111111111111111111111111111111111112',volume_5m:550,symbol:'B',market_cap:10000}];
 assert.deepEqual(rankTractionRows(rows).map(x=>x.symbol),['B','A']);
 assert.equal(latestActivityByMint([{token_key:`sol:${ca}`,kind:'ACTIVITY_INCREASING',change_pct:30,current_at:4},{token_key:`sol:${ca}`,kind:'ACTIVITY_WEAKENING',change_pct:-10,current_at:3}]).get(ca)?.change_pct,30);
});
test('GMGN and DEX artwork alternative fields are preserved',()=>{
 const t=normalizeTrenches({data:{new_creation:[{address:ca,dexId:'pumpfun',symbol:'ART',logoURI:'https://ipfs.io/ipfs/abc123'}]}});
 assert.equal(t[0].image_url,'https://ipfs.io/ipfs/abc123');
 const [q]=normalizeDexQuotes([{chainId:'solana',dexId:'pumpswap',baseToken:{address:ca,symbol:'ART',name:'Art'},image:{url:'https://cdn.dexscreener.com/art.png'}}],[ca]);
 assert.equal(q.image_url,'https://cdn.dexscreener.com/art.png');
});
test('saved metadata survives token leaving latest feed',()=>{
 const memory=new Map(),storage={getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v)};
 const first=createPreferencesStore(storage);first.saveTokenMeta(ca,{symbol:'ART',image_url:'https://cdn.dexscreener.com/a.png',socials:[{kind:'x',url:'https://x.com/ART'}]});
 const again=createPreferencesStore(storage);
 assert.equal(again.tokenMeta(ca).image_url,'https://cdn.dexscreener.com/a.png');
 again.saveTokenMeta(ca,{symbol:'ART',image_url:null,socials:[]});
 assert.equal(again.tokenMeta(ca).image_url,'https://cdn.dexscreener.com/a.png');
});
test('direct GMGN token dossier enriches image and X metadata',()=>{
 const r=metadataFromTokenDossier({info:{data:{data:{symbol:'FULL',logo:'https://ipfs.io/ipfs/test',socials:[{type:'twitter',url:'https://x.com/FullToken'}]}}}},ca);
 assert.equal(r.image_url,'https://ipfs.io/ipfs/test');
 assert.equal(r.socials[0].url,'https://x.com/FullToken');
});