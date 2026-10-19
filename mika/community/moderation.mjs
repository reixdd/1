import {validateReport} from './report-validation.mjs';
/** These are pure policy helpers, not an auth implementation. Authoritative authentication and moderation must run server-side. */
export function submitReport(authenticatedUserId,input){
 if(typeof authenticatedUserId!=='string'||authenticatedUserId.length<3)throw Error('AUTH_REQUIRED');
 const checked=validateReport(input);if(!checked.ok)throw Error(checked.error);
 return {...checked.value,id:crypto.randomUUID(),reporter_user_id:authenticatedUserId,status:'PENDING',submitted_at:Date.now()};
}
export function moderateReport(moderatorClaims,report,decision){
 if(!moderatorClaims?.verified||moderatorClaims?.role!=='moderator')throw Error('MODERATOR_REQUIRED');
 if(!['APPROVED','REJECTED'].includes(decision))throw Error('INVALID_DECISION');
 if(!report||!['PENDING','APPROVED'].includes(report.status))throw Error('INVALID_STATE');
 return {...report,status:decision,reviewed_at:Date.now()};
}
export function withdrawReport(userClaims,report){
 if(!userClaims?.verified||userClaims.user_id!==report?.reporter_user_id)throw Error('NOT_REPORT_OWNER');
 return {...report,status:'WITHDRAWN',reviewed_at:Date.now()};
}
export function publicCreatorSummary(mint,reports=[]){
 const included=(reports||[]).filter(r=>r?.mint===mint&&r.status==='APPROVED');
 return {mint,approved_count:included.length,evidence_links:[...new Set(included.flatMap(r=>r.evidenceLinks||[]))].slice(0,20)};
}
