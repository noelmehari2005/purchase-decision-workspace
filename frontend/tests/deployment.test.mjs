import test from 'node:test'
import assert from 'node:assert/strict'
import {parseDeployment,setBearer,transport} from '../src/deployment.ts'

const env={VITE_PDW_RUNTIME:'staging',VITE_PDW_API_ORIGIN:'https://api.onrender.com',VITE_PDW_AUTH0_DOMAIN:'test.auth0.com',
  VITE_PDW_AUTH0_CLIENT_ID:'spa',VITE_PDW_AUTH0_AUDIENCE:'https://pdw-api'}
test('Pages keeps the repository return path separate from the API origin',()=>{
  const result=parseDeployment(env,'https://owner.github.io','/purchase-decision-workspace/')
  assert.equal(result.returnTo,'https://owner.github.io/purchase-decision-workspace/')
  assert.equal(result.apiOrigin,'https://api.onrender.com')
  for(const patch of [{VITE_PDW_RUNTIME:'wrong'},{VITE_PDW_API_ORIGIN:'http://api.example.com'},
      {VITE_PDW_API_ORIGIN:'https://api.example.com/path'},{VITE_PDW_AUTH0_DOMAIN:'attacker.example.com'},
      {VITE_PDW_AUTH0_CLIENT_ID:''}])assert.throws(()=>parseDeployment({...env,...patch},'https://owner.github.io','/repo/'))
  assert.throws(()=>parseDeployment(env,'http://owner.github.io','/repo/'))
})
test('local transport remains relative; explicit session tokens can be cleared',()=>{
  assert.equal(parseDeployment({},'http://127.0.0.1:5173','/').apiOrigin,'')
  try {
    setBearer('session');assert.deepEqual(transport().headers,{Authorization:'Bearer session'})
    setBearer(null);assert.deepEqual(transport().headers,{})
  } finally {setBearer(null)}
})
