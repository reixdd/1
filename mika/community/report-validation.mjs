/** Offline validation for a future server-only, authenticated submission endpoint. */
const VALID_MINT=/^[1-9A-HJ-NP-Za-km-z]{32,44}$/;
const HOSTS=new Set(['solscan.io','explorer.solana.com','solana.fm','gmgn.ai','dexscreener.com']);
export function validateReport(input){
 if(!input||!VALID_MINT.test(input.mint||''))return {ok:false,error:'INVALID_MINT'};
 const statement=String(input.statement||'').trim();if(statement.length<5||statement.length>600)return {ok:false,error:'INVALID_STATEMENT'};
 const links=input.evidenceLinks;if(!Array.isArray(links)||links.length<1||links.length>3)return {ok:false,error:'EVIDENCE_REQUIRED'};
 const safe=[];for(const raw of links){try{const u=new URL(raw);if(u.protocol!=='https:'||u.port||u.username||u.password||!HOSTS.has(u.hostname.toLowerCase())||u.pathname==='/'||u.pathname.length<4)return {ok:false,error:'INVALID_EVIDENCE'};safe.push(u.href)}catch{return {ok:false,error:'INVALID_EVIDENCE'}}}
 const category=['OTHER','CREATOR_ACTIVITY','TOKEN_TRANSFER','LIQUIDITY','COORDINATED_ACTIVITY'].includes(input.category)?input.category:'OTHER';
 return {ok:true,value:{mint:input.mint,statement,category,evidenceLinks:safe}};
}
