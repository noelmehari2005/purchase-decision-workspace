import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import AuthShell from './AuthShell'
import './styles.css'
import HostedAuth from './HostedAuth'
import {deployment} from './deployment'

const root=createRoot(document.getElementById('root')!)
try {root.render(<StrictMode>{deployment().hosted?<HostedAuth/>:<AuthShell/>}</StrictMode>)}
catch {root.render(<p role="alert">The test deployment configuration is incomplete. Contact the app owner.</p>)}
