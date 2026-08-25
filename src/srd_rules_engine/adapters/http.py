"""An HTTP adapter over the turn loop (R34, #133).

The third and last transport R34 names. Like `adapters.mcp` and `adapters.cli` it binds to
`adapters.Session` and nothing deeper, so "the adapters are built over the same contract" is
a fact about the import graph rather than a description of intent (R34, guarded by
`tests/test_layer_boundaries.py`).

## One server, one session — the question this did not need a record for

`0016` left open how an HTTP server would hold a suspended turn, and it looked like a design
question because every other HTTP service answers it with a session registry keyed by a
caller-supplied identifier.

This one does not, and the reason is upstream of the transport. `AGENTS.md` declines
multiplayer, shared sessions, and any multi-user surface as a **non-goal** — "No concurrency,
turn arbitration, or shared-session state is assumed anywhere in the design." The MCP adapter
already answered it the same way, holding a single `Session` rather than a registry. A
server that keyed sessions by identifier would be building the multi-user surface the product
declined, in the one layer where nobody would notice it had been added.

So: one process, one session, one player character. A second concurrent turn is refused by
`Session` itself, which is where that rule already lives.

## Reads are GET, and that is a rules claim rather than a convention

R19: read-surface calls are idempotent, never mutate state, and never append to the ledger.
`look` and `report` are GET; everything that can move the engine is POST. The method is
therefore checkable evidence of the same property the core enforces, and a `look` that had to
become POST would be a sign the read surface had stopped being one.

## No route reaches an outcome, and none waives an obligation

`adapters.surface.FORBIDDEN_COMMAND_NAMES` names what must never appear on any adapter, and
one test asserts it across all three at once. There is no `/adjudicate`, for the reason
`AGENTS.md` gives: a consumer calling adjudication directly gets outcome authority without
skip prevention, so exposing it would ship the failure this engine removes as a feature.

`advanced_turn`'s `waive_obligations` is likewise absent, the same answer the other two
adapters give. A supported way to skip a compulsory save does not belong in front of the
caller the challenge mechanism exists to constrain.

## `handle` is the adapter; the server is a thin binding over it

`handle(method, path, body)` takes plain values and returns a status and a payload, so every
route is testable without a socket. `serve()` binds it to `http.server.ThreadingHTTPServer`,
which is the whole of this module's transport.

That split is deliberate. The stdlib server is adequate for what this is — a localhost
endpoint for a single-player solo game — and using it means this adapter takes **no
dependency at all**, so unlike `mcp` it needs no extra and `[project].dependencies` stays
empty (R33). A consumer wanting a production server binds `handle` to their own framework;
nothing here has to change for them to do it.

It binds to loopback by default. A rules engine holding a live campaign is not a thing to
expose on a network interface by accident, and the default is the one that cannot.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import Any

from srd_rules_engine.adapters.session import (
    AwaitingDeclaration,
    Session,
    SessionError,
)
from srd_rules_engine.adapters.surface import render_pending, situation_payload
from srd_rules_engine.core import Declaration, Intent, session_report
from srd_rules_engine.core import render as render_report

#: Routes, in one place so the server and its tests cannot disagree about them.
LOOK = "/look"
BEGIN = "/begin"
DECLARE = "/declare"
NARRATE = "/narrate"
END_TURN = "/end_turn"
FACTS = "/facts"
REPORT = "/report"

#: R19. These mutate nothing and record nothing, including that they happened.
READ_ROUTES: tuple[str, ...] = (LOOK, REPORT)
WRITE_ROUTES: tuple[str, ...] = (BEGIN, DECLARE, NARRATE, END_TURN, FACTS)
ROUTES: tuple[str, ...] = READ_ROUTES + WRITE_ROUTES

#: Loopback. A live campaign is not a thing to expose by accident.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


@dataclass(frozen=True)
class Response:
    """What a route produced: a status and a JSON-serialisable body."""

    status: int
    body: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.status < HTTPStatus.BAD_REQUEST


@dataclass
class HttpAdapter:
    """Binds routes to one session. Transport-free, so every route is testable
    without a socket — the same split `adapters.mcp.Adapter` makes."""

    session: Session
    ledger: Path
    #: Set by `serve`; a caller constructing this directly never needs it.
    host: str = field(default=DEFAULT_HOST)

    def handle(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> Response:
        """Route one request. Unknown paths and wrong methods are refused, not guessed at."""
        route = path.split("?")[0].rstrip("/") or "/"
        payload = body or {}

        if route not in ROUTES:
            return Response(
                HTTPStatus.NOT_FOUND,
                {"error": f"no such route: {route}", "routes": list(ROUTES)},
            )

        expected = "GET" if route in READ_ROUTES else "POST"
        if method.upper() != expected:
            # R19 is why this is worth refusing rather than accepting either way: the method
            # is checkable evidence that a read cannot mutate.
            return Response(
                HTTPStatus.METHOD_NOT_ALLOWED,
                {"error": f"{route} is {expected}, not {method.upper()}"},
            )

        try:
            return self._dispatch(route, payload)
        except SessionError as refused:
            # A well-formed request arriving when the engine is waiting for something else.
            # 409, not 400: the request is not malformed, the conversation is out of step.
            return Response(HTTPStatus.CONFLICT, {"error": str(refused)})
        except (KeyError, ValueError) as malformed:
            return Response(HTTPStatus.BAD_REQUEST, {"error": str(malformed)})

    def _dispatch(self, route: str, payload: Mapping[str, Any]) -> Response:
        if route == LOOK:
            result = self.session.look(str(payload["actor_id"]))
            return Response(
                HTTPStatus.OK,
                {
                    "actor_id": result.actor_id,
                    "offered": [
                        {"key": a.key, "label": a.label, "detail": dict(a.detail)}
                        for a in result.actions
                    ],
                    "read_token": result.token,
                    "situation": situation_payload(result.situation),
                },
            )
        if route == REPORT:
            return Response(HTTPStatus.OK, {"report": render_report(session_report(self.ledger))})
        if route == BEGIN:
            situation = payload.get("situation")
            return self._pending(
                self.session.begin(
                    str(payload["actor_id"]),
                    situation=dict(situation) if isinstance(situation, Mapping) else None,
                )
            )
        if route == DECLARE:
            return self._pending(self.session.declare(self._declaration(payload)))
        if route == NARRATE:
            text = payload.get("text")
            return self._pending(self.session.narrate(None if text is None else str(text)))
        if route == END_TURN:
            return self._pending(self.session.end_turn(str(payload["actor_id"])))
        if route == FACTS:
            values = payload.get("values")
            if not isinstance(values, Mapping):
                raise ValueError("facts takes a 'values' object of name to value")
            reference = payload.get("reference")
            return self._pending(
                self.session.supply_values(
                    dict(values), reference=str(reference) if reference is not None else None
                )
            )
        raise KeyError(f"no such route: {route!r}")

    def _pending(self, pending: Any) -> Response:
        return Response(HTTPStatus.OK, render_pending(pending, next_step=END_TURN))

    def _declaration(self, payload: Mapping[str, Any]) -> Declaration:
        """Shape a Declaration from a JSON body. The engine validates it; this does not.

        The read token and alternatives come from the open request where the caller did not
        supply them, so 0007's verdict is `verified-fresh` for the ordinary case rather than
        `unread` because a client retyped what it was just handed.
        """
        awaiting = self.session.pending
        offered = awaiting.offered if isinstance(awaiting, AwaitingDeclaration) else None

        action_key = payload.get("action_key")
        label = payload.get("improvised_label")
        if not action_key and not label:
            raise ValueError("declare needs action_key or improvised_label")

        token = payload.get("read_token") or (offered.token if offered else None)
        return Declaration(
            actor_id=str(payload.get("actor_id") or (awaiting.actor_id if awaiting else "")),
            intent=(
                Intent(action_key=str(action_key))
                if action_key
                else Intent(improvised=True, label=str(label))
            ),
            rule_id=str(payload["rule_id"]) if payload.get("rule_id") else None,
            no_test_reason=(
                str(payload["no_test_reason"]) if payload.get("no_test_reason") else None
            ),
            alternatives=offered.actions if offered else (),
            read_token=str(token) if token else None,
        )


def serve(
    adapter: HttpAdapter, *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT
) -> Any:  # pragma: no cover - the socket half, exercised by hand rather than in CI
    """Bind `handle` to a threading HTTP server on loopback.

    Imported inside the function so that importing this module never starts a server and
    never costs a socket. Returns the server; the caller runs it, because a function that
    both builds and blocks cannot be tested.
    """
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def _run(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError as bad:
                response = Response(HTTPStatus.BAD_REQUEST, {"error": f"invalid JSON: {bad}"})
            else:
                response = adapter.handle(method, self.path, body)
            encoded = json.dumps(response.body).encode()
            self.send_response(response.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:
            self._run("GET")

        def do_POST(self) -> None:
            self._run("POST")

        def log_message(self, format: str, *args: Any) -> None:
            """Silent by default. A rules engine's transport log is not its ledger, and the
            ledger is the record that matters."""

    return ThreadingHTTPServer((host, port), Handler)
