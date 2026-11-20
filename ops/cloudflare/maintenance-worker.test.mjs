import test from 'node:test'
import assert from 'node:assert/strict'
import {createHmac} from 'node:crypto'
import worker,{triggerMaintenance,reportHeartbeat} from './maintenance-worker.mjs'

const env={PDW_SCHEDULE_ENABLED:'1',PDW_API_ORIGIN:'https://fixture.onrender.com',PDW_MAINTENANCE_SECRET:'a'.repeat(64)}
test('disabled scheduler and public requests cannot invoke maintenance',async()=>{
  await triggerMaintenance({...env,PDW_SCHEDULE_ENABLED:'0'},{fetchImpl:()=>assert.fail('no fetch when disabled')})
  assert.equal(worker.fetch().status,404)
})
test('signs after waking Render and sends no secret, user data or body',async()=>{
  const requests=[]
  const result=await triggerMaintenance(env,{clock:()=>1795040000000,nonce:()=>'b'.repeat(32),fetchImpl:async(url,options)=>{
    requests.push({url,options})
    return Response.json(requests.length===1?{status:'ok'}:{status:'ok',mode:'check'})
  }})
  assert.deepEqual(result,{status:'ok',mode:'check'})
  assert.equal(requests[0].url,env.PDW_API_ORIGIN+'/api/v1/health')
  assert.equal(requests[0].options.headers,undefined)
  const sent=requests[1]
  assert.equal(sent.options.method,'POST');assert.equal(sent.options.redirect,'manual')
  assert.equal(sent.options.body,undefined)
  assert.equal(sent.options.headers['X-PDW-Signature'],createHmac('sha256',env.PDW_MAINTENANCE_SECRET)
    .update(`POST\n/api/v1/maintenance/run\n1795040000\n${'b'.repeat(32)}`).digest('hex'))
  assert.ok(!JSON.stringify(requests).includes(env.PDW_MAINTENANCE_SECRET))
})
test('misconfigured destinations cannot receive even a signature',async()=>{
  for(const origin of ['http://fixture.onrender.com','https://attacker.example','https://fixture.onrender.com/path',
      'https://user:pass@fixture.onrender.com','https://fixture.onrender.com:443'])
    await assert.rejects(triggerMaintenance({...env,PDW_API_ORIGIN:origin},{fetchImpl:()=>assert.fail('invalid destination')}),/Invalid maintenance API origin/)
})
test('failures and retries are surfaced without logging raw API/provider responses',async()=>{
  for(const mode of ['http','retry','partial','network']) {
    let count=0
    await assert.rejects(triggerMaintenance(env,{fetchImpl:async()=>{
      count++
      if(count===1)return Response.json({status:'ok'})
      if(mode==='network')throw new Error('PRIVATE headers and response')
      return Response.json({status:mode==='partial'?'partial':'retry_pending',secret:'PRIVATE'}, {status:mode==='http'?503:200})
    }}),error=>error.message.includes('Maintenance did not complete')&&!error.message.includes('PRIVATE'))
  }
})
test('health failures expose only the phase and HTTP status',async()=>{
  await assert.rejects(triggerMaintenance(env,{fetchImpl:async()=>new Response('PRIVATE',{status:403})}),
    error=>error.message.includes('phase=health, HTTP=403')&&!error.message.includes('PRIVATE'))
})
test('default fetch retains its global receiver',async()=>{
  const original=globalThis.fetch
  globalThis.fetch=async function(){assert.equal(this,globalThis);return Response.json({status:'ok',mode:'check'})}
  try {assert.deepEqual(await triggerMaintenance(env),{status:'ok',mode:'check'})}
  finally {globalThis.fetch=original}
})

test('redirect responses stop without following or sending a signature elsewhere',async()=>{
  for(const redirectPhase of ['health','trigger']) {
    let count=0
    await assert.rejects(triggerMaintenance(env,{fetchImpl:async(url,options)=>{
      count++;assert.equal(options.redirect,'manual')
      if(redirectPhase==='health'||count===2)return new Response(null,{status:302,headers:{Location:'https://attacker.example'}})
      return Response.json({status:'ok'})
    }}),/HTTP=302/)
    assert.equal(count,redirectPhase==='health'?1:2)
  }
})
test('email test logs only the allowed delivery summary',async()=>{
  let count=0
  const result=await triggerMaintenance(env,{fetchImpl:async()=>Response.json(++count===1?{status:'ok'}:
    {status:'ok',mode:'email-test',delivery:'accepted',recipient:'PRIVATE',password:'PRIVATE'})})
  assert.deepEqual(result,{status:'ok',mode:'email-test',delivery:'accepted'})
  assert.ok(!JSON.stringify(result).includes('PRIVATE'))
})
const pingUrl='https://hc-ping.com/11111111-2222-3333-4444-555555555555'
test('monitor sends only an empty success signal to the configured check',async()=>{
  const calls=[]
  assert.deepEqual(await reportHeartbeat({PDW_MONITOR_PING_URL:pingUrl},{status:'ok',mode:'check'},
    {fetchImpl:async(url,options)=>{calls.push({url,options});return new Response('OK')}}),{monitor:'accepted'})
  assert.equal(calls.length,1);assert.equal(calls[0].url,pingUrl)
  assert.equal(calls[0].options.method,'POST');assert.equal(calls[0].options.redirect,'manual')
  assert.equal(calls[0].options.body,undefined);assert.equal(calls[0].options.headers,undefined)
})
test('missing monitor and non-success or wrong-mode results never ping',async()=>{
  const noFetch={fetchImpl:()=>assert.fail('no misleading heartbeat')}
  assert.deepEqual(await reportHeartbeat({}, {status:'ok',mode:'check'},noFetch),{monitor:'disabled'})
  for(const result of [{status:'busy',mode:'check'},{status:'disabled'}, {status:'partial',mode:'check'},
      {status:'ok',mode:'email-test'},{status:'ok',mode:'notify'}])
    assert.deepEqual(await reportHeartbeat({PDW_MONITOR_PING_URL:pingUrl},result,noFetch),{monitor:'not_reported'})
})
test('monitor rejects unsafe destinations and never exposes its secret URL',async()=>{
  for(const url of ['http://hc-ping.com/11111111-2222-3333-4444-555555555555',pingUrl+'?key=PRIVATE',
      pingUrl+'/fail',pingUrl.replace('hc-ping.com','attacker.example'),pingUrl.replace('https://','https://user:pass@')])
    await assert.rejects(reportHeartbeat({PDW_MONITOR_PING_URL:url},{status:'ok',mode:'check'},
      {fetchImpl:()=>assert.fail('invalid destination')}),/Invalid independent monitor configuration/)
  for(const response of [()=>new Response(null,{status:302,headers:{Location:'https://attacker.example'}}),
      ()=>{throw new Error('PRIVATE '+pingUrl)}])
    await assert.rejects(reportHeartbeat({PDW_MONITOR_PING_URL:pingUrl},{status:'ok',mode:'check'},
      {fetchImpl:async()=>response()}),error=>!error.message.includes('PRIVATE')&&!error.message.includes(pingUrl))
})
test('scheduled handler reports success only after backend success and never on failure',async()=>{
  const originalFetch=globalThis.fetch,originalLog=console.log
  try {
    for(const state of ['ok','busy','failure']) {
      const urls=[],logs=[];let completion
      globalThis.fetch=async function(url){
        urls.push(url)
        if(url===pingUrl)return new Response('OK')
        if(url.endsWith('/health'))return Response.json({status:'ok'})
        return Response.json({status:state,mode:'check'},{status:state==='failure'?503:200})
      }
      console.log=value=>logs.push(value)
      await worker.scheduled({}, {...env,PDW_MONITOR_PING_URL:pingUrl},{waitUntil:promise=>{completion=promise}})
      if(state==='failure')await assert.rejects(completion,/phase=trigger, HTTP=503/)
      else await completion
      assert.equal(urls.includes(pingUrl),state==='ok')
      assert.ok(!logs.join('').includes(pingUrl))
    }
  } finally {globalThis.fetch=originalFetch;console.log=originalLog}
})
