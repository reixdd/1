import test from 'node:test';import assert from 'node:assert/strict';
import {normalizeTrenches} from '../ui/live-feed.mjs';
import {summarizeCreatorHistory} from '../ui/creator-evidence.mjs';
const mint='So11111111111111111111111111111111111111112';
const dev='A'.repeat(43);
test('top-level provider X link survives even when socials array is empty',()=>{
 const row=normalizeTrenches({data:{new_creation:[{address:mint,dexId:'pumpfun',socials:[],twitter:'https://x.com/providerprofile'}]}})[0];
 assert.equal(row.socials[0].url,'https://x.com/providerprofile');
});
test('creator history distinguishes provider-reported from on-chain verified relationships',()=>{
 assert.equal(summarizeCreatorHistory([{mint,creator_pubkey:dev,evidence_level:'PROVIDER_REPORTED'}],[],dev).verified_launch_count,0);
 assert.equal(summarizeCreatorHistory([{mint,creator_pubkey:dev,evidence_level:'ONCHAIN_VERIFIED'}],[],dev).verified_launch_count,1);
});
