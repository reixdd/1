import {safeExternalUrl,normalizeSocials} from './token-media.mjs';
export const validSolMint=x=>typeof x==='string'&&/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(x);
export function gmgnTokenUrl(mint){return validSolMint(mint)?`https://gmgn.ai/sol/token/${mint}`:null;}
export function sourceXUrl(row){
 const existing=normalizeSocials(row?.socials)?.find(x=>x.kind==='x')?.url;if(existing)return existing;
 const value=row?.twitter??row?.twitter_url??row?.twitter_username;
 if(typeof value!=='string'||!value.trim())return null;
 const candidate=/^@?[a-zA-Z0-9_]{1,15}$/.test(value)?`https://x.com/${value.replace(/^@/,'')}`:value;
 const url=safeExternalUrl(candidate);if(!url)return null;
 const host=new URL(url).hostname.toLowerCase();
 return ['x.com','www.x.com','twitter.com','www.twitter.com'].includes(host)&&new URL(url).pathname.length>1?url:null;
}
export function buildTokenLinks(row){return {gmgn:gmgnTokenUrl(row?.contract||row?.mint),x:sourceXUrl(row),chart:safeExternalUrl(row?.source_url)};}
