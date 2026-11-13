export interface SessionStatus {
  mode:'local'|'auth0'; configured:boolean; authenticated:boolean; verified?:boolean;
  user?:{id:string;email:string}; csrf?:string; idle_until?:number; absolute_until?:number;
}
export function privateAccess(status:SessionStatus|null):boolean {
  return status?.authenticated===true && status.verified===true && !!status.user?.id && !!status.csrf
}
export function sessionDeadline(status:SessionStatus):number {
  const values=[status.idle_until,status.absolute_until]
  if (values.some(value=>typeof value!=='number' || !Number.isFinite(value))) return 0
  return Math.min(status.idle_until!,status.absolute_until!)*1000
}
export function workspaceIdentity(status:SessionStatus):string {
  if (status.mode==='local') return 'local'
  return privateAccess(status) ? `${status.user!.id}:${status.csrf}` : 'demo'
}
