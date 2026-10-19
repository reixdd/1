import test from 'node:test';import assert from 'node:assert/strict';
import {validateReport} from '../report-validation.mjs';
import {submitReport,moderateReport,publicCreatorSummary,withdrawReport} from '../moderation.mjs';
const mint='So11111111111111111111111111111111111111112';
test('community submissions require mint and checkable source',()=>{
 assert.equal(validateReport({mint,statement:'Observed a transfer',evidenceLinks:[]}).ok,false);
 const report=validateReport({mint,category:'OTHER',statement:'Transaction requires review',evidenceLinks:['https://solscan.io/tx/abc']});
 assert.equal(report.ok,true);assert.equal(report.value.mint,mint);
 assert.equal(validateReport({mint,statement:'x'.repeat(700),evidenceLinks:['https://solscan.io/tx/abc']}).ok,false);
 assert.equal(validateReport({mint,statement:'Something happened',evidenceLinks:['http://localhost/secret']}).ok,false);
});
test('submission is owned by authenticated user and stays pending',()=>{
 assert.throws(()=>submitReport(null,{mint,statement:'Observation',evidenceLinks:['https://solscan.io/tx/abc']}),/AUTH_REQUIRED/);
 const saved=submitReport('user-123',{mint,statement:'Observation',evidenceLinks:['https://solscan.io/tx/abc'],reporter_user_id:'attacker',status:'APPROVED'});
 assert.equal(saved.reporter_user_id,'user-123');assert.equal(saved.status,'PENDING');
 assert.deepEqual(publicCreatorSummary(mint,[saved]),{mint,approved_count:0,evidence_links:[]});
});
test('only verified server-side moderator may approve; withdrawn reports disappear',()=>{
 const a=submitReport('user-123',{mint,statement:'Review this record',evidenceLinks:['https://solscan.io/tx/abc']});
 assert.throws(()=>moderateReport({role:'moderator'},a,'APPROVED'),/MODERATOR_REQUIRED/);
 const accepted=moderateReport({role:'moderator',verified:true},a,'APPROVED');
 assert.equal(publicCreatorSummary(mint,[accepted]).approved_count,1);
 const withdrawn=withdrawReport({user_id:'user-123',verified:true},accepted);
 assert.equal(publicCreatorSummary(mint,[withdrawn]).approved_count,0);
 assert.equal(JSON.stringify(publicCreatorSummary(mint,[accepted])).includes('user-123'),false);
});
