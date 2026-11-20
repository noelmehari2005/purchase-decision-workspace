/** Cron-only caller: no database/provider credentials and no public run endpoint. */
export async function triggerMaintenance(env,{fetchImpl=(url,options)=>globalThis.fetch(url,options),clock=()=>Date.now(),nonce=()=>crypto.randomUUID().replaceAll('-','')}={}) {
  if(env.PDW_SCHEDULE_ENABLED!=='1')return {status:'disabled'}
  let origin
  try {
    origin=new URL(env.PDW_API_ORIGIN)
    if(origin.protocol!=='https:' || origin.origin!==env.PDW_API_ORIGIN || origin.port || origin.username || origin.password ||
        !/^[a-z0-9-]+\.onrender\.com$/.test(origin.hostname))throw new Error()
  } catch {throw new Error('Invalid maintenance API origin.')}
  if(!/^[0-9a-f]{64}$/.test(env.PDW_MAINTENANCE_SECRET||''))throw new Error('Missing maintenance signing secret.')
  let phase='health',httpStatus='unavailable'
  try {
    // Wake Render before signing, so a cold start does not age the signature.
    const health=await fetchImpl(origin.origin+'/api/v1/health',{
      method:'GET',redirect:'manual',signal:AbortSignal.timeout(75_000)})
    httpStatus=String(health.status)
    if(!health.ok)throw new Error()
    phase='signing';httpStatus='unavailable'
    const stamp=String(Math.floor(clock()/1000)),value=nonce(),path='/api/v1/maintenance/run'
    if(!/^[0-9a-f]{32}$/.test(value))throw new Error()
    const encoder=new TextEncoder()
    const key=await crypto.subtle.importKey('raw',encoder.encode(env.PDW_MAINTENANCE_SECRET),
      {name:'HMAC',hash:'SHA-256'},false,['sign'])
    const bytes=await crypto.subtle.sign('HMAC',key,encoder.encode(`POST\n${path}\n${stamp}\n${value}`))
    const signature=Array.from(new Uint8Array(bytes),value=>value.toString(16).padStart(2,'0')).join('')
    phase='trigger'
    const response=await fetchImpl(origin.origin+path,{method:'POST',redirect:'manual',signal:AbortSignal.timeout(110_000),
      headers:{'X-PDW-Timestamp':stamp,'X-PDW-Nonce':value,'X-PDW-Signature':signature}})
    httpStatus=String(response.status)
    if(!response.ok)throw new Error()
    const result=await response.json()
    if(!['ok','busy'].includes(result.status))throw new Error()
    return {status:result.status,mode:result.mode,
      ...(result.mode==='email-test'&&['accepted','already_attempted'].includes(result.delivery)?{delivery:result.delivery}:{})}
  } catch(error) {
    // Fetch errors can include destinations/headers. Only a fixed error reaches logs.
    const cause=String(error?.message||'').includes('Illegal invocation')?'binding':
      error?.name==='TimeoutError'||error?.name==='AbortError'?'timeout':'request'
    throw new Error(`Maintenance did not complete successfully (phase=${phase}, HTTP=${httpStatus}, cause=${cause}); inspect the private API diagnostics.`)
  }
}

/** Independent liveness signal; never forward API responses or credentials. */
export async function reportHeartbeat(env,result,{fetchImpl=(url,options)=>globalThis.fetch(url,options)}={}) {
  if(!env.PDW_MONITOR_PING_URL)return {monitor:'disabled'}
  let destination
  const expected=env.PDW_MONITOR_EXPECTED_MODE||'check'
  try {
    destination=new URL(env.PDW_MONITOR_PING_URL)
    if(destination.protocol!=='https:'||destination.hostname!=='hc-ping.com'||destination.port||
        destination.username||destination.password||destination.search||destination.hash||
        !/^\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(destination.pathname)||
        destination.href!==env.PDW_MONITOR_PING_URL||!['check','notify','cleanup'].includes(expected))throw new Error()
  } catch {throw new Error('Invalid independent monitor configuration.')}
  // Busy, paused, email-test and unexpected modes cannot mask a stopped job.
  if(result.status!=='ok'||result.mode!==expected)return {monitor:'not_reported'}
  try {
    const response=await fetchImpl(destination.href,{method:'POST',redirect:'manual',signal:AbortSignal.timeout(10_000)})
    if(!response.ok)throw new Error()
  } catch {throw new Error('Independent maintenance heartbeat was not accepted.')}
  return {monitor:'accepted'}
}

export default {
  async scheduled(_controller,env,context) {
    context.waitUntil(triggerMaintenance(env).then(async result=>{
      const monitor=await reportHeartbeat(env,result)
      console.log(JSON.stringify({event:'pdw-maintenance',...result,...monitor}))
    }))
  },
  fetch() {return new Response('Not found',{status:404})},
}
