import {emptyState,admit,claim,complete,lookup,prune} from './queue-state.mjs';
const send=(obj,status=200)=>new Response(JSON.stringify(obj),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
/** One global Durable Object serializes all admissions and job transitions. */
export class MikaQueue {
 constructor(state,env){this.state=state;this.env=env;}
 async fetch(request){
  return this.state.blockConcurrencyWhile(async()=>{
   const now=Date.now(),state=await this.state.storage.get('mika')||emptyState();prune(state,now);
   const url=new URL(request.url),path=url.pathname;
   let body={};if(request.method==='POST'){try{body=await request.json()}catch{return send({error:'BAD_JSON'},400)}}
   let result=null;
   if(path==='/queue/admit'&&request.method==='POST')result=admit(state,{session:body.session,text:body.text,selectedMint:body.selectedMint??null,id:body.id,now});
   else if(path==='/queue/claim'&&request.method==='POST')result={ok:true,job:claim(state,{lease:body.lease,now})};
   else if(path==='/queue/complete'&&request.method==='POST')result=complete(state,{id:body.id,lease:body.lease,answer:body.answer,error:body.error,now});
   else if(path==='/queue/job'&&request.method==='POST')result=lookup(state,body.id,body.session,now);
   else if(path==='/queue/heartbeat'&&request.method==='POST'){state.lastHeartbeat=now;result={ok:true};}
   else if(path==='/queue/status'&&request.method==='GET')result={ok:true,online:now-state.lastHeartbeat<30000,queued:state.queue.length,busy:!!state.activeId};
   else return send({error:'NOT_FOUND'},404);
   await this.state.storage.put('mika',state);
   return send(result,result?.http||200);
  });
 }
}
