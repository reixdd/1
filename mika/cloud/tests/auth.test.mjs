import test from 'node:test';import assert from 'node:assert/strict';
import {signSession,verifySession,isSameOrigin,verifyDeviceKey,validJobPath} from '../security.mjs';
const secret='a-sturdy-test-secret-that-is-not-deployed';
test('session cookie is tamper-evident and expires',async()=>{
 const token=await signSession('abc123',100000,secret);assert.equal(await verifySession(token,50000,secret),'abc123');
 assert.equal(await verifySession(token+'.',50000,secret),null);assert.equal(await verifySession(token,101000,secret),null);
});
test('POST requires exact configured Origin, no prefix spoof',()=>{assert.equal(isSameOrigin('https://mika.example','https://mika.example'),true);assert.equal(isSameOrigin('https://mika.example.evil.test','https://mika.example'),false);assert.equal(isSameOrigin(null,'https://mika.example'),false);});
test('device secret is never accepted missing or mismatched',async()=>{assert.equal(await verifyDeviceKey('Bearer alpha','alpha'),true);assert.equal(await verifyDeviceKey('Bearer alphaevil','alpha'),false);assert.equal(await verifyDeviceKey('','alpha'),false);});
test('job paths only accept fixed UUID format',()=>{assert.equal(validJobPath('/api/chat/jobs/01234567-1234-4123-a123-012345678901'),true);assert.equal(validJobPath('/api/chat/jobs/../../api/admin'),false);});
