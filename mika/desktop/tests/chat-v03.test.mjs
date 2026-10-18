import test from 'node:test';import assert from 'node:assert/strict';
import {selectChatModel,pruneConversation,modelAvailability} from '../ui/chat-utils.mjs';
test('model selection excludes embedding models',()=>{assert.equal(selectChatModel(['nomic-embed-text','qwen3.5:4b','qwen3-embedding:0.6b']), 'qwen3.5:4b');});
test('model selection avoids embedding-only list',()=>{assert.equal(selectChatModel(['nomic-embed-text','qwen3-embedding:0.6b']),null);});
test('model availability signals unsupported rather than fake replies',()=>{assert.equal(modelAvailability([]),'NO_CHAT_MODELS');assert.equal(modelAvailability(['qwen3.5:4b']),'READY');});
test('conversation history retains latest eight accepted roles with capped length',()=>{const rows=[{role:'system',content:'prompt injection'},...Array.from({length:12},(_,i)=>({role:i%2?'assistant':'user',content:'x'.repeat(999)+i}))];const out=pruneConversation(rows);assert.equal(out.length,8);assert.ok(out.every(x=>x.content.length<=600&&['user','assistant'].includes(x.role)));});
