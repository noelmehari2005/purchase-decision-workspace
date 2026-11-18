/** Public build settings only. Credentials must never be VITE_* variables. */
import {readHostedSession,writeHostedSession} from './hostedSession.ts'
export type Deployment={hosted:boolean;apiOrigin:string;domain:string;clientId:string;audience:string;returnTo:string}
export function parseDeployment(env:Record<string,string>,origin:string,base:string):Deployment {
  if (!env.VITE_PDW_RUNTIME || env.VITE_PDW_RUNTIME==='local')
    return {hosted:false,apiOrigin:'',domain:'',clientId:'',audience:'',returnTo:''}
  if (env.VITE_PDW_RUNTIME!=='staging') throw new Error('Unknown deployment mode.')
  const api=new URL(env.VITE_PDW_API_ORIGIN)
  if (api.protocol!=='https:' || api.origin!==env.VITE_PDW_API_ORIGIN || api.port || api.username || api.password ||
      ['localhost','127.0.0.1','[::1]'].includes(api.hostname) || !origin.startsWith('https://'))
    throw new Error('Staging requires HTTPS app and API origins.')
  if (!/^[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.auth0\.com$/.test(env.VITE_PDW_AUTH0_DOMAIN || '') ||
      !env.VITE_PDW_AUTH0_CLIENT_ID || !env.VITE_PDW_AUTH0_AUDIENCE || !/^\/(?:[a-zA-Z0-9_-]+\/)*$/.test(base))
    throw new Error('Complete the staging sign-in settings and base path.')
  return {hosted:true,apiOrigin:api.origin,domain:env.VITE_PDW_AUTH0_DOMAIN,clientId:env.VITE_PDW_AUTH0_CLIENT_ID,
    audience:env.VITE_PDW_AUTH0_AUDIENCE,returnTo:origin+base}
}
export function deployment():Deployment {
  const env=(import.meta as ImportMeta & {env?:Record<string,string>}).env || {}
  return parseDeployment(env,typeof window==='undefined'?'':window.location?.origin || '',env.BASE_URL || '/')
}
let bearer:string|null=null
const tabStorage=()=>typeof window==='undefined'?null:window.sessionStorage
export function storedBearer():string|null {
  return readHostedSession(deployment(),tabStorage,typeof window==='undefined'?'':window.location.search)
}
export function setBearer(value:string|null) {
  bearer=value
  writeHostedSession(deployment(),tabStorage,value)
}
export function apiUrl(path:string) {return deployment().apiOrigin+'/api/v1'+path}
export function transport():{credentials:RequestCredentials;headers:Record<string,string>} {
  return {credentials:deployment().hosted?'omit':'same-origin',headers:bearer?{Authorization:'Bearer '+bearer}:{}}
}
