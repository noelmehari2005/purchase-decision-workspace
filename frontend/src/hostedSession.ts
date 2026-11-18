/** Only the opaque app credential is retained. Never pass provider tokens here. */
export type SessionStorageAccess=()=>Pick<Storage,'getItem'|'setItem'|'removeItem'>|null
export type SessionScope={hosted:boolean;apiOrigin:string;domain:string;clientId:string;audience:string;returnTo:string}

function key(scope:SessionScope):string|null {
  return scope.hosted ? 'pdw:app-session:v1:'+JSON.stringify([
    scope.apiOrigin,scope.domain,scope.clientId,scope.audience,scope.returnTo,
  ]) : null
}
function valid(value:unknown):value is string {
  return typeof value==='string' && /^[A-Za-z0-9_-]{43}$/.test(value)
}
export function readHostedSession(scope:SessionScope,storage:SessionStorageAccess,search=''):string|null {
  const name=key(scope)
  if(!name)return null
  try {
    const target=storage(),query=new URLSearchParams(search)
    // A provider callback must establish its own identity, even if a prior
    // session remains in this tab. An unsuccessful callback cannot revive it.
    if(query.has('state') && (query.has('code') || query.has('error'))) {
      target?.removeItem(name);return null
    }
    const value=target?.getItem(name)
    if(valid(value))return value
    target?.removeItem(name)
  } catch { /* Storage restrictions fall back to a memory-only session. */ }
  return null
}
export function writeHostedSession(scope:SessionScope,storage:SessionStorageAccess,value:string|null):void {
  const name=key(scope)
  if(!name)return
  try {
    const target=storage()
    target?.removeItem(name)
    if(valid(value))target?.setItem(name,value)
  } catch { /* Sign-in still works when browser storage is unavailable. */ }
}
