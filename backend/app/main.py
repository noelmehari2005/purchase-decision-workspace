"""Local evaluation API with opt-in development persistence. No accounts or live imports."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .domain import Requirements, evaluate
from .schemas import EvaluationInput, EvaluationOutput

app = FastAPI(title='Purchase Decision Workspace', version='0.2.0')
from .storage_api import install_storage
install_storage(app)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', 'testserver'])


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, error: RequestValidationError):
    # Do not echo entire request bodies/financial inputs in an error response.
    return JSONResponse(status_code=422, content={
        'code': 'invalid_input', 'message': 'Review the highlighted inputs.',
        'field_errors': [{'path': '.'.join(map(str, item['loc'][1:])), 'message': item['msg']}
                         for item in error.errors()],
    })


@app.get('/api/v1/health')
def health():
    return {'status': 'ok', 'mode': 'local-stateless'}


@app.post('/api/v1/evaluations', response_model=EvaluationOutput)
def evaluate_decision(payload: EvaluationInput):
    try:
        return evaluate([item.to_domain() for item in payload.candidates],
                        Requirements(**payload.requirements.model_dump()),
                        payload.plan.to_domain(), payload.preferences.model_dump())
    except ValueError as error:
        return JSONResponse(status_code=422, content={
            'code': 'invalid_plan', 'message': str(error), 'field_errors': [],
        })
