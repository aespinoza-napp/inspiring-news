"""
Reader accounts (docs/goals.md, N5): register, sign in and out, change
the password, export everything held, delete it all.

Not behind STORAGE_API_KEY: a reader has no key. The session cookie is
the capability, and these routes give nothing without one but the chance
to make an account or sign in, both limited per client
(src/services/accounts/service.py).

CSRF, two ways:

- Signed in: every state-changing request carries the session's own
  token in X-CSRF-Token, which only a page that read /account/me (same
  origin) knows.
- Not yet signed in (register, login): X-Requested-With must be set. A
  cross-site form cannot set a header, and the backend allows no CORS,
  so a request that has one came from our own pages. That stops a forged
  sign-in into an attacker's account.

Every answer is Cache-Control: no-store.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field

from src.api.map_routes import client_of
from src.config.settings import settings
from src.container import get_account_service
from src.services.accounts.service import (
    MAX_PASSWORD,
    SESSION_IDLE_DAYS,
    AccountError,
    Session,
)
from src.services.rate_limit import RateLimited

COOKIE = "in_session"

REQUESTED_WITH = "inspiring-news"


class NoStoreRoute(APIRoute):
    """
    Cache-Control: no-store on every answer, the errors raised from a
    dependency included: those are new responses, which a dependency
    setting the header on the injected one never reaches.
    """

    def get_route_handler(self):

        handle = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                response = await handle(request)
            except HTTPException as error:
                error.headers = {**(error.headers or {}), "Cache-Control": "no-store"}
                raise
            response.headers["Cache-Control"] = "no-store"
            return response

        return handler


router = APIRouter(prefix="/account", route_class=NoStoreRoute)


class Credentials(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=MAX_PASSWORD)


class Registration(Credentials):
    email: str | None = Field(default=None, max_length=254)


class PasswordChange(BaseModel):
    current: str = Field(max_length=MAX_PASSWORD)
    new: str = Field(max_length=MAX_PASSWORD)


class Confirmation(BaseModel):
    password: str = Field(max_length=MAX_PASSWORD)


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE,
        token,
        max_age=SESSION_IDLE_DAYS * 86400,
        httponly=True,
        secure=settings.ACCOUNT_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/", httponly=True, secure=settings.ACCOUNT_COOKIE_SECURE, samesite="lax")


def _view(session: Session) -> dict:
    return {
        "user": {"username": session.username, "email": session.email, "createdAt": session.created_at},
        "csrf": session.csrf,
    }


def _limited(error: RateLimited) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail="Too many attempts from here; try again later.",
        headers={"Retry-After": str(int(error.retry_after + 0.999))},
    )


def _from_our_pages(x_requested_with: str | None) -> None:
    if x_requested_with != REQUESTED_WITH:
        raise HTTPException(status_code=403, detail="This request must come from the site's own pages.")


def current_session(request: Request) -> Session:
    """The signed-in reader, or 401."""

    session = get_account_service().session(request.cookies.get(COOKIE))

    if session is None:
        raise HTTPException(status_code=401, detail="Not signed in.")

    return session


def checked_session(request: Request, x_csrf_token: str | None = Header(default=None)) -> Session:
    """The signed-in reader of a state-changing request: their session's CSRF token, or 403."""

    session = current_session(request)

    if not x_csrf_token or not hmac.compare_digest(x_csrf_token, session.csrf):
        raise HTTPException(status_code=403, detail="Missing or wrong CSRF token: reload the page.")

    return session


@router.post("/register", status_code=201)
def register(body: Registration, request: Request, x_requested_with: str | None = Header(default=None)):

    _from_our_pages(x_requested_with)

    try:
        token, session = get_account_service().register(body.username, body.password, body.email, client_of(request))
    except RateLimited as error:
        raise _limited(error)
    except AccountError as error:
        raise HTTPException(status_code=422, detail=str(error))

    response = JSONResponse(_view(session), status_code=201)
    _set_cookie(response, token)
    return response


@router.post("/login")
def login(body: Credentials, request: Request, x_requested_with: str | None = Header(default=None)):

    _from_our_pages(x_requested_with)

    try:
        token, session = get_account_service().login(body.username, body.password, client_of(request))
    except RateLimited as error:
        raise _limited(error)
    except AccountError as error:
        raise HTTPException(status_code=401, detail=str(error))

    response = JSONResponse(_view(session))
    _set_cookie(response, token)
    return response


@router.get("/me")
def me(session: Session = Depends(current_session)):
    """Who is signed in, and the CSRF token their page sends back."""

    return _view(session)


@router.post("/logout", status_code=204)
def logout(request: Request, session: Session = Depends(checked_session)):

    get_account_service().logout(request.cookies.get(COOKIE, ""))

    response = Response(status_code=204)
    _clear_cookie(response)
    return response


@router.post("/password", status_code=204)
def change_password(body: PasswordChange, request: Request, session: Session = Depends(checked_session)):

    try:
        get_account_service().change_password(session, request.cookies.get(COOKIE, ""), body.current, body.new)
    except AccountError as error:
        raise HTTPException(status_code=422, detail=str(error))

    return Response(status_code=204)


@router.get("/export")
def export(session: Session = Depends(current_session)):
    """Everything held about the reader, as a JSON file."""

    return JSONResponse(
        get_account_service().export(session),
        headers={
            "Content-Disposition": f'attachment; filename="inspiring-news-{session.username}.json"',
        },
    )


@router.post("/delete", status_code=204)
def delete(body: Confirmation, session: Session = Depends(checked_session)):

    try:
        get_account_service().delete(session, body.password)
    except AccountError as error:
        raise HTTPException(status_code=422, detail=str(error))

    response = Response(status_code=204)
    _clear_cookie(response)
    return response
