import {Auth0Provider,useAuth0} from '@auth0/auth0-react'
import {useEffect,useRef,useState} from 'react'
import AuthShell from './AuthShell'
import {apiUrl,deployment,setBearer,storedBearer} from './deployment'

export default function HostedAuth() {
  const config=deployment()
  return <Auth0Provider domain={config.domain} clientId={config.clientId} cacheLocation="memory"
    authorizationParams={{redirect_uri:config.returnTo,audience:config.audience,scope:'openid email profile',
      connection:'Username-Password-Authentication',prompt:'login',max_age:0}}
    onRedirectCallback={()=>window.history.replaceState(null,'',config.returnTo)}>
      <SessionBridge/>
    </Auth0Provider>
}

function SessionBridge() {
  const auth=useAuth0()
  const [resumeToken]=useState(storedBearer)
  const [ready,setReady]=useState(false),[error,setError]=useState(''),[attempt,setAttempt]=useState(0)
  // Share the promise across StrictMode's effect replay, without minting two sessions.
  const pending=useRef<Promise<string>|null>(null)
  useEffect(()=>{
    if(resumeToken) {
      // AuthShell checks /auth/session before rendering any private workspace.
      // Reusing this credential does not create a session or reset its clocks.
      setBearer(resumeToken);setReady(true)
    }
  },[resumeToken])
  useEffect(()=>{
    if(resumeToken || auth.isLoading)return
    let active=true
    if(!auth.isAuthenticated) {setReady(true);return}
    setReady(false)
    pending.current ||= (async()=>{
      const access=await auth.getAccessTokenSilently()
      const identity=await auth.getIdTokenClaims()
      if(!access || !identity?.__raw)throw new Error('Sign in again to continue.')
      const response=await fetch(apiUrl('/auth/spa-session'),{method:'POST',credentials:'omit',
        signal:AbortSignal.timeout(90_000),headers:{Authorization:'Bearer '+access,'Content-Type':'application/json'},
        body:JSON.stringify({id_token:identity.__raw})})
      if(!response.ok)throw new Error('Sign-in could not be completed. Check that this verified account is approved for the test deployment, then sign in again.')
      const body=await response.json()
      if(typeof body.session_token!=='string')throw new Error('Invalid sign-in response.')
      return body.session_token as string
    })()
    void pending.current.then(token=>{if(active){setBearer(token);setReady(true);setError('')}}).catch(()=>{
      if(active)setError('Sign-in could not be completed. The test server may be waking up, or your account may need approval. Try signing in again.')
    })
    return ()=>{active=false}
  },[resumeToken,auth.isLoading,auth.isAuthenticated,auth.getAccessTokenSilently,auth.getIdTokenClaims,attempt])
  const login=(signup=false)=>{
    setBearer(null);pending.current=null
    void auth.loginWithRedirect({authorizationParams:{prompt:'login',max_age:0,...(signup?{screen_hint:'signup'}:{})}})
      .catch(()=>setError('Unable to open sign-in. Please try again.'))
  }
  if((!resumeToken && auth.error) || error)return <section className="account-panel"><p role="alert">{error || 'The sign-in provider could not complete this request.'}</p>
    <button onClick={()=>login()}>Sign in again</button><button onClick={()=>{pending.current=null;setError('');setAttempt(value=>value+1)}}>Retry connection</button></section>
  if(!ready)return <p role="status">Connecting to the test workspace… A sleeping test server can take about a minute to start.</p>
  return <><p className="notice" role="note">Controlled test deployment. Use fictional laptop plans and sample financial information only. Unsaved changes stay in this tab.</p>
    <AuthShell hosted={{login,logout:()=>{setBearer(null);void auth.logout({logoutParams:{returnTo:deployment().returnTo}})}}}/></>
}
