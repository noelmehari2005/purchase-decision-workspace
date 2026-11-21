/** Separate daily caller; credentials/data stay in Render, no public trigger. */
const path='/api/v1/backups/run'

function monitorUrl(value) {
  try {
    const url=new URL(value)
    if(url.protocol!=='https:'||url.hostname!=='hc-ping.com'||url.port||url.username||url.password||url.search||url.hash||
      !/^\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(url.pathname)||url.href!==value)throw new Error()
    return url.href
  } catch {throw new Error('Invalid backup monitor configuration.')}
}

export async function triggerBackup(env,{fetchImpl=(url,options)=>globalThis.fetch(url,options),clock=()=>Date.now(),nonce=()=>crypto.randomUUID().replaceAll('-','')}={}) {
  if(env.PDW_BACKUP_SCHEDULE_ENABLED!=='1')return {status:'disabled',mode:'backup',uploaded:false}
  let origin
  try {
    origin=new URL(env.PDW_API_ORIGIN)
    if(origin.protocol!=='https:'||origin.origin!==env.PDW_API_ORIGIN||origin.port||origin.username||origin.password||
      !/^[a-z0-9-]+\.onrender\.com$/.test(origin.hostname))throw new Error()
  } catch {throw new Error('Invalid backup API origin.')}
  monitorUrl(env.PDW_BACKUP_MONITOR_PING_URL) // Fail before upload if independent monitoring is missing/unsafe.
  if(!/^[0-9a-f]{64}$/.test(env.PDW_BACKUP_SIGNING_SECRET||''))throw new Error('Missing backup signing secret.')
  let phase='health',httpStatus='unavailable'
  try {
    const health=await fetchImpl(origin.origin+'/api/v1/health',{method:'GET',redirect:'manual',signal:AbortSignal.timeout(75_000)})
    httpStatus=String(health.status);if(!health.ok)throw new Error()
    phase='signing';httpStatus='unavailable'
    const stamp=String(Math.floor(clock()/1000)),value=nonce(),encoder=new TextEncoder()
    if(!/^[0-9a-f]{32}$/.test(value))throw new Error()
    const key=await crypto.subtle.importKey('raw',encoder.encode(env.PDW_BACKUP_SIGNING_SECRET),{name:'HMAC',hash:'SHA-256'},false,['sign'])
    const raw=await crypto.subtle.sign('HMAC',key,encoder.encode(`POST\n${path}\n${stamp}\n${value}`))
    const signature=Array.from(new Uint8Array(raw),n=>n.toString(16).padStart(2,'0')).join('')
    phase='trigger'
    const response=await fetchImpl(origin.origin+path,{method:'POST',redirect:'manual',signal:AbortSignal.timeout(150_000),
      headers:{'X-PDW-Timestamp':stamp,'X-PDW-Nonce':value,'X-PDW-Signature':signature}})
    httpStatus=String(response.status);if(!response.ok)throw new Error()
    const result=await response.json()
    if(result.mode!=='backup'||!['ok','attention','busy','already_attempted'].includes(result.status)||
      typeof result.uploaded!=='boolean'||(result.status==='ok'&&(result.uploaded!==true||result.writer_rotation_due!==false)))throw new Error()
    return {status:result.status,mode:'backup',uploaded:result.uploaded,writer_rotation_due:result.writer_rotation_due===true}
  } catch {
    throw new Error(`Backup was not confirmed (phase=${phase}, HTTP=${httpStatus}); inspect private operator status.`)
  }
}

export async function reportBackup(env,result,{fetchImpl=(url,options)=>globalThis.fetch(url,options)}={}) {
  if(result.status!=='ok'||result.mode!=='backup'||result.uploaded!==true||result.writer_rotation_due!==false)return {monitor:'not_reported'}
  const destination=monitorUrl(env.PDW_BACKUP_MONITOR_PING_URL)
  try {
    const response=await fetchImpl(destination,{method:'POST',redirect:'manual',signal:AbortSignal.timeout(10_000)})
    if(!response.ok)throw new Error()
    return {monitor:'accepted'}
  } catch {throw new Error('Independent backup heartbeat was not accepted.')}
}

export default {
  async scheduled(_controller,env,context) {
    context.waitUntil(triggerBackup(env).then(async result=>{
      const monitor=await reportBackup(env,result)
      console.log(JSON.stringify({event:'pdw-backup',...result,...monitor}))
    }))
  },
  fetch() {return new Response('Not found',{status:404})},
}
