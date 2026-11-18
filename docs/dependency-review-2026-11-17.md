# Frontend dependency review — November 17, 2026

Installing `@auth0/auth0-react` 2.30.0 succeeded. The owner then supplied an npm audit report containing five high-severity findings. All five trace to one advisory: [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf), a regular-expression denial of service in picomatch through 4.0.7. The advisory currently lists no patched version.

The installed affected chain is Vite 8.3.5 → tinyglobby 0.2.17 / fdir 6.5.0 → picomatch 4.0.7; Vite also depends directly on picomatch. The React Vite plugin inherits the finding through Vite. The supplied audit does not identify Auth0 as an affected package.

Do not apply npm's suggested forced downgrade to Vite 6.2.7 automatically. That would change the build-tool major version without establishing that the resulting dependency tree is secure and supported. No dependencies were downgraded or locally patched during this review, and the advisory remains unresolved.

The project binds its development server to loopback. Application source does not import picomatch, tinyglobby or fdir, or supply user-entered glob patterns to the build tooling. These observations limit the apparent exposure in this project; they do not constitute a proof that every transitive build-tool call is unreachable. Continue local development using trusted source/configuration and keep the Vite development server private. Hosted frontend delivery must use static build output, rather than exposing Vite's development server.

After the SDK installation, all 27 frontend tests and the production build passed. Passing tests do not resolve the security advisory. Recheck the advisory and audit the lockfile before the hosted release, assess any compatible upstream fix, and retain this finding in release review until resolved or explicitly assessed for the actual deployment. The restricted coding session cannot reach npm's advisory registry; the audit results above came from the owner's terminal.
