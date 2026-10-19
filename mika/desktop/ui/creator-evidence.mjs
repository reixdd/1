import {validSolMint} from './token-links.mjs';
export function classifyCreatorRole(raw){const role=String(raw?.role||'').toUpperCase().replace(/[- ]/g,'_');return ['CREATOR','FEE_RECIPIENT','SIGNER','FUNDER','AUTHORITY'].includes(role)?role:'UNKNOWN';}
export function normalizeCreatorClaim(raw,{mint,source='UNKNOWN',observedAt=null}={}){
 if(!validSolMint(mint))return null;
 const creator=raw?.creator_pubkey||raw?.creator||raw?.address;
 if(!validSolMint(creator))return null;
 const role=classifyCreatorRole(raw),proof=raw.signature&&Number.isSafeInteger(Number(raw.slot))&&Number(raw.slot)>=0&&raw.decoder&&role==='CREATOR'&&source==='SOLANA_RPC';
 return {mint,creator_pubkey:creator,role,source,signature:raw.signature||null,slot:raw.slot??null,decoder:raw.decoder||null,evidence_level:proof?'ONCHAIN_VERIFIED':'PROVIDER_REPORTED',observed_at:observedAt};
}
export function normalizeCreatorEvent(raw){
 if(!validSolMint(raw?.mint)||!validSolMint(raw?.actor_pubkey))return null;
 const kind=['TOKEN_TRANSFER','TOKEN_SALE','LIQUIDITY_CHANGE','CREATOR_BALANCE'].includes(raw?.event_type)?raw.event_type:null;
 if(!kind)return null;
 const isSale=kind==='TOKEN_SALE';if(isSale&&!(raw.signature&&raw.decoder&&raw.trade_verified===true))return null;
 return {mint:raw.mint,actor_pubkey:raw.actor_pubkey,event_type:kind,signature:raw.signature||null,source:raw.source||'UNKNOWN',observed_at:raw.observed_at??null};
}
export function summarizeCreatorHistory(launches=[],events=[],creator){
 const matching=[...new Map((launches||[]).filter(l=>l.creator_pubkey===creator&&validSolMint(l.mint)).map(l=>[l.mint,l])).values()];
 const verified=matching.filter(l=>l.evidence_level==='ONCHAIN_VERIFIED');
 return {creator_pubkey:creator,verified_launch_count:verified.length,coverage:matching.length?'PARTIAL':'UNKNOWN',known_launches:verified,events:(events||[]).filter(e=>e.actor_pubkey===creator)};
}
