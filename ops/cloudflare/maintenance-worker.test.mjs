import test from 'node:test'
import assert from 'node:assert/strict'
import {createHmac} from 'node:crypto'
import worker,{triggerMaintenance} from './maintenance-worker.mjs'

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
  assert.equal(sent.options.method,'POST');assert.equal(sent.options.redirect,'error')
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
