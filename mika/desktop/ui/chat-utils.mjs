/** Local-only model selection. Never send embedding model IDs to Ollama chat. */
export const isChatModel=name=>typeof name==='string' && name.length>0 && !/(embed|embedding|rerank|nomic)/i.test(name);
export function selectChatModel(models,preferred='qwen3.5:4b'){
 const eligible=(models||[]).filter(isChatModel);
 if(!eligible.length)return null;
 return eligible.includes(preferred)?preferred:eligible.find(x=>/^qwen3[.\-]/i.test(x))||eligible[0];
}
export const modelAvailability=models=>selectChatModel(models)?'READY':'NO_CHAT_MODELS';
export function pruneConversation(rows){return (Array.isArray(rows)?rows:[]).filter(r=>r&&['user','assistant'].includes(r.role) && typeof r.content==='string'&&r.content.trim()).slice(-8).map(r=>({role:r.role,content:r.content.slice(0,600)}));}
