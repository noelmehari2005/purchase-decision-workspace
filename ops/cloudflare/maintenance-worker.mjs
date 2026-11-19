/** Cron-only caller: no database/provider credentials and no public run endpoint. */
export async function triggerMaintenance(env,{fetchImpl=(...args)=>globalThis.fetch(...args),clock=()=>Date.now(),nonce=()=>crypto.randomUUID().replaceAll('-','')}={}) {
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

export default {
  async scheduled(_controller,env,context) {
    context.waitUntil(triggerMaintenance(env).then(result=>{
      console.log(JSON.stringify({event:'pdw-maintenance',...result}))
    }))
  },
  fetch() {return new Response('Not found',{status:404})},
}
