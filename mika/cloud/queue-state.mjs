/** Pure, deterministic admission state used by Durable Object. No service credentials or model routes. */
export function emptyState(){return {jobs:{},queue:[],activeId:null,sessions:{},daily:{},global:{day:'',count:0},lastHeartbeat:0};}
const dayKey=now=>new Date(now).toISOString().slice(0,10);
const err=(code,http=429)=>({ok:false,error:code,http});
export function prune(s,now=Date.now()){
 for(const [id,job] of Object.entries(s.jobs)){
  if(now-job.created>60*60*1000){delete s.jobs[id];if(s.activeId===id)s.activeId=null;}
  else if(job.status==='running' && now>job.leaseUntil){job.status='error';job.error='LOCAL_MODEL_TIMEOUT';job.answer=null;delete job.lease;s.activeId=null;}
 }
 s.queue=s.queue.filter(id=>s.jobs[id]?.status==='queued');
 for(const [key,r] of Object.entries(s.sessions)){if(now-r.updated>24*60*60*1000)delete s.sessions[key]}
}
export function admit(s,{session,text,selectedMint=null,now=Date.now(),id,...other}){
 prune(s,now);
 if(Object.keys(other).length || (selectedMint!==null && (typeof selectedMint!=='string' || !/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(selectedMint))) || typeof text!=='string' || [...text].length>600 || !text.trim() || typeof session!=='string' || !session || !/^[a-zA-Z0-9_.-]{1,128}$/.test(session) || typeof id!=='string'|| !id || id.length>64)return err('INVALID_CHAT_REQUEST',400);
 if(s.queue.length>=8)return err('CHAT_QUEUE_FULL');
 const day=dayKey(now),global=s.global.day===day?s.global:{day,count:0};
 if(global.count>=100)return err('GLOBAL_DAILY_LIMIT');
 const rec=s.sessions[session]||{day,dayCount:0,recent:[],updated:now};
 if(rec.day!==day){rec.day=day;rec.dayCount=0;}
 rec.recent=rec.recent.filter(ms=>now-ms<60000);
 if(rec.recent.length>=3)return err('SESSION_RATE_LIMIT');
 if(rec.dayCount>=15)return err('SESSION_DAILY_LIMIT');
 if(s.jobs[id])return err('DUPLICATE_JOB',409);
 rec.updated=now;rec.recent.push(now);rec.dayCount++;s.sessions[session]=rec;
 s.global={day,count:global.count+1};s.jobs[id]={id,session,text:text.trim(),selectedMint,created:now,status:'queued'};s.queue.push(id);
 return {ok:true,id,status:'queued'};
}
export function claim(s,{now=Date.now(),lease}){
 prune(s,now);if(s.activeId||typeof lease!=='string'||lease.length<3)return null;
 const id=s.queue.shift();if(!id)return null;const job=s.jobs[id];if(!job)return null;
 job.status='running';job.lease=lease;job.leaseUntil=now+120000;s.activeId=id;
 return {id,lease,created:job.created,text:job.text,selectedMint:job.selectedMint};
}
export function complete(s,{id,lease,answer,now=Date.now(),error=null}){
 prune(s,now);const job=s.jobs[id];if(!job || job.status!=='running'||!lease||job.lease!==lease||s.activeId!==id)return err('INVALID_LEASE',403);
 if(error){job.status='error';job.error=String(error).slice(0,100);}
 else {if(typeof answer!=='string'||answer.length>4096)return err('INVALID_ANSWER',400);job.status='complete';job.answer=answer;}
 delete job.lease;delete job.leaseUntil;delete job.text;s.activeId=null;
 return {ok:true};
}
export function lookup(s,id,session,now=Date.now()){
 prune(s,now);const job=s.jobs[id];if(!job||job.session!==session)return err('JOB_NOT_FOUND',404);
 return {ok:true,id,status:job.status,answer:job.status==='complete'?job.answer:undefined,error:job.error||undefined};
}
