import test from 'node:test';
import assert from 'node:assert/strict';
import { tokenKey, normalizeRadarRow, groupMarkets, freshness } from '../ui/domain.mjs';
const addr='So11111111111111111111111111111111111111112';
test('Solana mint case is preserved; unrelated pool addresses stay distinct',()=>{
 assert.equal(tokenKey('sol', addr),`sol:${addr}`);
 const rows=groupMarkets([{chain:'sol',contract:addr,pool:'poolA',liquidity:100},{chain:'sol',contract:addr,pool:'poolB',liquidity:200}]);
 assert.equal(rows.length,1); assert.equal(rows[0].markets.length,2);
});
test('Missing numeric fields stay null instead of zero',()=>{
 const row=normalizeRadarRow({chain:'sol',contract:addr,symbol:'TST',provider_count:1,observed_at:1});
 assert.equal(row.market_cap,null); assert.equal(row.volume_5m,null); assert.equal(row.buys_5m,null);
});
test('freshness respects exact 45 and 180 second boundaries',()=>{
 assert.equal(freshness(955,1000),'FRESH'); assert.equal(freshness(954,1000),'DELAYED');
 assert.equal(freshness(820,1000),'DELAYED'); assert.equal(freshness(819,1000),'UNAVAILABLE');
 assert.equal(freshness(null,1000),'UNAVAILABLE');
});
