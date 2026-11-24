"""The web server: a JSON API over the engine, and the browser client's files.

``tft serve`` starts it. It is standard library only: a threading HTTP server
whose handler passes every request to :class:`Api`, a plain object that maps
a method, a path and a body to a :class:`Response` and can be tested without a
socket. Matches live in memory in a :class:`Lobby`.

The server only answers with data it produced itself. Numbers and booleans in
a request are converted before use, action names are matched against the
engine's own list, and nothing a client sends is echoed back. A refusal by the
rules is reported with the reason the engine wrote for players; any other
failure is reported as ``internal error`` and nothing more.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import secrets
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import cast

from tft import __version__
from tft.environment import PHASE_PLANNING, Game, RoundReport
from tft.errors import Refusal
from tft.lessons import RoundSummary, summarize
from tft.market import MarketPack, load_builtin
from tft.name import GAME_NAME
from tft.replay import ACTIONS, Action, Replay, apply_action
from tft.rules import DEFAULT_RULES, Rules
from tft.view import Json, catalog, match_state, report_view, summary_view

SEAT = "you"
"""The name of the human seat in a match."""

BOT_NAMES = ("ana", "bo", "cy", "di", "ed", "fay", "gus", "hal")
MAX_BODY = 64 * 1024
MAX_MATCHES = 32
MAX_ARGS = 4
MAX_SEED = 2**31 - 1
JSON_TYPE = "application/json"
TEXT_TYPE = "text/plain; charset=utf-8"
SOCKET_TIMEOUT = 15
"""Seconds a connection may stay silent before it is dropped."""

LOOPBACK_NAMES = frozenset({"127.0.0.1", "localhost", "[::1]"})
"""The names a server that listens on this machine only is reached by."""

LOG = logging.getLogger(__name__)

STATIC: Mapping[str, tuple[str, str]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/logic.js": ("logic.js", "text/javascript; charset=utf-8"),
    "/art.js": ("art.js", "text/javascript; charset=utf-8"),
    "/dom.js": ("dom.js", "text/javascript; charset=utf-8"),
    "/figures.js": ("figures.js", "text/javascript; charset=utf-8"),
    "/models.js": ("models.js", "text/javascript; charset=utf-8"),
    "/studio.js": ("studio.js", "text/javascript; charset=utf-8"),
    "/pieces.js": ("pieces.js", "text/javascript; charset=utf-8"),
    "/scene.js": ("scene.js", "text/javascript; charset=utf-8"),
    "/arena.js": ("arena.js", "text/javascript; charset=utf-8"),
    "/battle.js": ("battle.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}
"""The client's files by URL path: the packaged file name and its content type."""

SECURITY_HEADERS: tuple[tuple[str, str], ...] = (
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Cache-Control", "no-store"),
    (
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: blob:; object-src 'none'; base-uri 'none'",
    ),
)
"""Headers sent with every response, also with the errors the standard library raises."""

MATCH_ROUTES = frozenset({"actions", "ready", "step", "preview", "spectate", "replay"})


class ApiError(Exception):
    """A request the API rejects, with the HTTP status and a fixed message for the client."""

    def __init__(self, status: int, message: str) -> None:
        """Keep the status and the message."""
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class Response:
    """An HTTP answer: status, body and content type."""

    status: int
    body: bytes
    content_type: str


def json_response(status: int, payload: Json) -> Response:
    """Return ``payload`` as a JSON response."""
    return Response(status, json.dumps(payload).encode("utf-8"), JSON_TYPE)


@dataclass
class Match:
    """A game on the server: the engine state, the human seat if any, its replay and last round."""

    id: str
    game: Game
    seat: str | None
    replay: Replay | None
    stamp: int
    lock: threading.Lock = field(default_factory=threading.Lock)
    report: RoundReport | None = None
    summary: RoundSummary | None = None

    def require_planning(self) -> tuple[Game, str, Replay]:
        """Return the game, the seat and the replay of a match that is waiting for its player.

        Raises:
            ApiError: If the match has no player seat or is not in a planning phase.
        """
        if self.seat is None or self.replay is None:
            raise ApiError(HTTPStatus.CONFLICT, "this match has no player seat")
        if self.game.finished or self.game.phase != PHASE_PLANNING:
            raise ApiError(HTTPStatus.CONFLICT, "the match is not waiting for actions")
        return self.game, self.seat, self.replay

    def act(self, action: Action) -> str:
        """Apply a planning action for the seat, record it, and return the engine's message."""
        game, seat, replay = self.require_planning()
        message = apply_action(game, game.player(seat), action)
        replay.rounds[-1].append(action)
        return message

    def ready(self) -> None:
        """Fight the open round, summarise it, and open the next one or finish the match."""
        game, seat, replay = self.require_planning()
        self.report = game.finish_round()
        self.summary = summarize(game, seat, self.report)
        if game.finished or not game.player(seat).alive:
            replay.result = game.run()
            return
        _ = game.start_round()
        replay.rounds.append([])

    def step(self) -> None:
        """Play one whole round of a bots-only match.

        Raises:
            ApiError: If the match has a player seat or is finished.
        """
        if self.seat is not None:
            raise ApiError(HTTPStatus.CONFLICT, "only bot matches can be stepped")
        if self.game.finished:
            raise ApiError(HTTPStatus.CONFLICT, "the match is finished")
        self.report = self.game.step()

    def view(self, *, spectator: bool) -> Json:
        """Return the match as its player sees it, or as a spectator does."""
        seat = None if spectator else self.seat
        state = match_state(self.game, seat)
        own_summary = self.summary is not None and seat is not None
        state["id"] = self.id
        state["spectator"] = seat is None
        state["has_seat"] = self.seat is not None
        state["last"] = {
            "report": report_view(self.report) if self.report is not None else None,
            "summary": summary_view(self.summary) if self.summary and own_summary else None,
        }
        return state

    def card(self) -> Json:
        """Return the match as the lobby lists it."""
        game = self.game
        return {
            "id": self.id,
            "round": game.current.label if game.current is not None else None,
            "rounds_played": game.round_index,
            "finished": game.finished,
            "has_seat": self.seat is not None,
            "mode": "market" if game.pack is not None else "power",
            "seats": [
                {"name": player.name, "health": player.health, "alive": player.alive}
                for player in game.players
            ],
        }


class Lobby:
    """The matches a server holds, at most ``max_matches`` of them."""

    def __init__(
        self,
        rules: Rules = DEFAULT_RULES,
        pack: MarketPack | None = None,
        max_matches: int = MAX_MATCHES,
    ) -> None:
        """Start an empty lobby that plays under ``rules`` on ``pack``, by default the starter pack.

        Raises:
            ValueError: If ``max_matches`` is not positive, the pack is too short
                for one slice, or the rules leave no room for a bot.
        """
        if max_matches <= 0:
            msg = "max_matches must be positive"
            raise ValueError(msg)
        self.rules = rules
        self.pack = pack if pack is not None else load_builtin()
        if len(self.pack.dates) < rules.slice_bars:
            dates = len(self.pack.dates)
            msg = f"a slice of {rules.slice_bars} bars does not fit the pack's {dates} dates"
            raise ValueError(msg)
        fewest, most = self.bots_range()
        if fewest > most:
            msg = f"the rules need {rules.min_players} players, the server seats at most {most + 1}"
            raise ValueError(msg)
        self.max_matches = max_matches
        self.matches: dict[str, Match] = {}
        self.lock = threading.Lock()
        self.clock = 0

    def tick(self) -> int:
        """Return the next access stamp; the caller holds the lock."""
        self.clock += 1
        return self.clock

    def bots_range(self) -> tuple[int, int]:
        """Return the fewest and the most bots a match can have under the lobby's rules."""
        most = min(self.rules.lobby_size, len(BOT_NAMES)) - 1
        return max(1, self.rules.min_players - 1), most

    def create(self, seed: int, bots: int, *, market: bool, spectate: bool) -> Match:
        """Create a match against ``bots`` bots, or a bots-only match to watch.

        Raises:
            Refusal: If the number of bots does not fit the rules.
        """
        fewest, most = self.bots_range()
        if not fewest <= bots <= most:
            msg = f"bots must be {fewest} to {most}"
            raise Refusal(msg)
        seat = None if spectate else SEAT
        names = list(BOT_NAMES[: bots + 1]) if spectate else [SEAT, *BOT_NAMES[:bots]]
        pack = self.pack if market else None
        policies = {SEAT: None} if seat is not None else None
        game = Game(names, seed=seed, rules=self.rules, policies=policies, pack=pack)
        replay = None
        if seat is not None:
            pack_name = pack.name if pack is not None else None
            replay = Replay(seed, names, seat, self.rules.digest(), pack_name, [[]])
            _ = game.start_round()
        with self.lock:
            self.make_room()
            match = Match(secrets.token_urlsafe(9), game, seat, replay, self.tick())
            self.matches[match.id] = match
        return match

    def make_room(self) -> None:
        """Drop the least recently used match when the lobby is full, finished ones first."""
        if len(self.matches) < self.max_matches:
            return
        oldest = min(self.matches.values(), key=lambda m: (not m.game.finished, m.stamp))
        del self.matches[oldest.id]

    def get(self, match_id: str) -> Match:
        """Return the match with ``match_id`` and mark it as used.

        Raises:
            ApiError: If there is no such match.
        """
        with self.lock:
            match = self.matches.get(match_id)
            if match is None:
                raise ApiError(HTTPStatus.NOT_FOUND, "no such match")
            match.stamp = self.tick()
            return match

    def remove(self, match_id: str) -> None:
        """Forget the match with ``match_id``; unknown ids are ignored."""
        with self.lock:
            _ = self.matches.pop(match_id, None)

    def cards(self) -> list[Json]:
        """Return the lobby listing, most recently used first."""
        with self.lock:
            matches = sorted(self.matches.values(), key=lambda match: -match.stamp)
        return [match.card() for match in matches]


def parse_body(body: bytes, content_type: str) -> Json:
    """Parse a request body as a JSON object; an empty body is an empty object.

    The content type is required even without a body: a page on another site
    cannot send it without asking the server first, which the server refuses.

    Raises:
        ApiError: If the content type is not JSON or the body is not a JSON object.
    """
    if content_type.split(";", maxsplit=1)[0].strip().lower() != JSON_TYPE:
        raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "send the body as application/json")
    if not body:
        return {}
    try:
        data = json.loads(body)
    except (ValueError, RecursionError):
        data = None
    if not isinstance(data, dict):
        raise ApiError(HTTPStatus.BAD_REQUEST, "the request body must be a JSON object")
    return data


def whole_number(raw: object, low: int, high: int, what: str) -> int:
    """Return ``raw`` as an ``int`` between ``low`` and ``high``.

    Raises:
        ApiError: If ``raw`` is not a whole number in that range.
    """
    if isinstance(raw, bool) or not isinstance(raw, int) or not low <= raw <= high:
        raise ApiError(HTTPStatus.BAD_REQUEST, f"{what} must be a whole number, {low} to {high}")
    return int(raw)


def flag(raw: object, what: str) -> bool:
    """Return ``raw`` as a ``bool``.

    Raises:
        ApiError: If ``raw`` is not ``true`` or ``false``.
    """
    if not isinstance(raw, bool):
        raise ApiError(HTTPStatus.BAD_REQUEST, f"{what} must be true or false")
    return bool(raw)


def parse_action(data: Json) -> Action:
    """Read ``{"kind": ..., "args": [...]}`` into an engine action.

    The kind is matched against the engine's own action names and the arguments
    are converted to whole numbers, so nothing of the request survives as is.

    Raises:
        ApiError: If the kind is unknown or the arguments are not a short list of whole numbers.
    """
    raw_kind = data.get("kind")
    kind = next((known for known in ACTIONS if known == raw_kind), None)
    if kind is None:
        raise ApiError(HTTPStatus.BAD_REQUEST, "unknown action")
    raw_args = data.get("args", [])
    if not isinstance(raw_args, list) or len(raw_args) > MAX_ARGS:
        raise ApiError(HTTPStatus.BAD_REQUEST, "args must be a short list of whole numbers")
    args = tuple(whole_number(raw, 0, MAX_SEED, "an argument") for raw in raw_args)
    return Action(kind, args)


@dataclass(frozen=True)
class Request:
    """A routed API request: the match it names, if any, and its JSON body."""

    match_id: str
    data: Json


Handler = Callable[["Api", Request], Response]


class Api:
    """The JSON API and the static files, independent of any socket."""

    def __init__(self, lobby: Lobby | None = None) -> None:
        """Serve ``lobby``, or a new one on the default rules and the starter pack."""
        self.lobby = lobby if lobby is not None else Lobby()
        fewest, most = self.lobby.bots_range()
        content = {"ok": True, **catalog(self.lobby.rules), "bots": {"min": fewest, "max": most}}
        self.catalog = json_response(HTTPStatus.OK, content)

    def handle(self, method: str, path: str, body: bytes = b"", content_type: str = "") -> Response:
        """Answer one request; rule refusals and bad requests become JSON errors."""
        plain_path = path.split("?", 1)[0]
        try:
            if not plain_path.startswith("/api/"):
                return self.static(method, plain_path)
            return self.route(method, plain_path, body, content_type)
        except ApiError as error:
            return json_response(error.status, {"ok": False, "error": error.message})
        except Refusal as refusal:
            return json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": refusal.reason})

    def static(self, method: str, path: str) -> Response:
        """Serve one of the client's packaged files.

        Raises:
            ApiError: If the method is not GET or the path is not a client file.
        """
        entry = STATIC.get(path)
        if entry is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "not found")
        if method != "GET":
            raise ApiError(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed")
        name, content_type = entry
        return Response(
            HTTPStatus.OK, files("tft").joinpath("web", name).read_bytes(), content_type
        )

    def route(self, method: str, path: str, body: bytes, content_type: str) -> Response:
        """Find the handler for an API path and call it.

        Raises:
            ApiError: If no route matches the path or the method.
        """
        parts = [part for part in path.split("/") if part][1:]
        key, match_id = route_key(parts)
        handlers = ROUTES.get(key)
        if handlers is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "not found")
        handler = handlers.get(method)
        if handler is None:
            raise ApiError(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed")
        data = parse_body(body, content_type) if method == "POST" else {}
        return handler(self, Request(match_id, data))

    def health(self, _request: Request) -> Response:
        """Report that the server is up, and its version."""
        payload = {"ok": True, "status": "ok", "name": GAME_NAME, "version": __version__}
        return json_response(HTTPStatus.OK, payload)

    def get_catalog(self, _request: Request) -> Response:
        """Return the static content: champions, traits, items, augments."""
        return self.catalog

    def list_matches(self, _request: Request) -> Response:
        """Return the lobby listing."""
        return json_response(HTTPStatus.OK, {"ok": True, "matches": self.lobby.cards()})

    def bots_of(self, data: Json) -> int:
        """Return the number of bots a request asks for; by default as many as the rules seat.

        Raises:
            ApiError: If the number does not fit the rules.
        """
        fewest, most = self.lobby.bots_range()
        return whole_number(data.get("bots", most), fewest, most, "bots")

    def create_match(self, request: Request) -> Response:
        """Create a match from ``seed``, ``bots``, ``market`` and ``spectate``."""
        data = request.data
        seed = data.get("seed")
        number = (
            secrets.randbelow(MAX_SEED) if seed is None else whole_number(seed, 0, MAX_SEED, "seed")
        )
        bots = self.bots_of(data)
        market = flag(data.get("market", True), "market")
        spectate = flag(data.get("spectate", False), "spectate")
        match = self.lobby.create(number, bots, market=market, spectate=spectate)
        state = match.view(spectator=spectate)
        return json_response(HTTPStatus.CREATED, {"ok": True, "state": state})

    def get_match(self, request: Request) -> Response:
        """Return the match as its player sees it."""
        match = self.lobby.get(request.match_id)
        with match.lock:
            return json_response(HTTPStatus.OK, {"ok": True, "state": match.view(spectator=False)})

    def get_spectate(self, request: Request) -> Response:
        """Return the match as a spectator sees it."""
        match = self.lobby.get(request.match_id)
        with match.lock:
            return json_response(HTTPStatus.OK, {"ok": True, "state": match.view(spectator=True)})

    def delete_match(self, request: Request) -> Response:
        """Forget a match."""
        self.lobby.remove(request.match_id)
        return json_response(HTTPStatus.OK, {"ok": True})

    def post_action(self, request: Request) -> Response:
        """Apply one planning action for the seat."""
        action = parse_action(request.data)
        match = self.lobby.get(request.match_id)
        with match.lock:
            message = match.act(action)
            state = match.view(spectator=False)
        return json_response(HTTPStatus.OK, {"ok": True, "message": message, "state": state})

    def post_ready(self, request: Request) -> Response:
        """End the seat's planning: fight, summarise, and open the next round."""
        match = self.lobby.get(request.match_id)
        with match.lock:
            match.ready()
            state = match.view(spectator=False)
        return json_response(HTTPStatus.OK, {"ok": True, "state": state})

    def post_step(self, request: Request) -> Response:
        """Play one round of a bots-only match."""
        match = self.lobby.get(request.match_id)
        with match.lock:
            match.step()
            state = match.view(spectator=True)
        return json_response(HTTPStatus.OK, {"ok": True, "state": state})

    def get_preview(self, request: Request) -> Response:
        """Return the seat's odds against every other board on replayed market slices."""
        match = self.lobby.get(request.match_id)
        with match.lock:
            game, seat, _ = match.require_planning()
            odds = game.preview_odds(seat)
        listing = [{"name": name, "probability": probability} for name, probability in odds]
        return json_response(HTTPStatus.OK, {"ok": True, "odds": listing})

    def get_replay(self, request: Request) -> Response:
        """Return the match's replay.

        Raises:
            ApiError: If the match has no player seat, and so no replay.
        """
        match = self.lobby.get(request.match_id)
        with match.lock:
            if match.replay is None:
                raise ApiError(HTTPStatus.CONFLICT, "this match has no player seat")
            return json_response(HTTPStatus.OK, {"ok": True, "replay": match.replay.to_json()})


def host_name(host: str) -> str:
    """Return the name in a Host header: lower case, without the port."""
    name = host.strip().lower()
    if name.startswith("["):
        return name.split("]", maxsplit=1)[0] + "]"
    return name.split(":", maxsplit=1)[0]


def check_source(method: str, host: str, origin: str | None, *, loopback: bool) -> None:
    """Refuse a request that another site sent through the player's browser.

    A server that listens on this machine only answers to a loopback name,
    which stops a page that points its own domain at ``127.0.0.1``. A request
    that changes something must not carry the origin of another site.

    Raises:
        ApiError: With status 403 for such a request.
    """
    if loopback and host_name(host) not in LOOPBACK_NAMES:
        raise ApiError(HTTPStatus.FORBIDDEN, "this server only answers to its own address")
    own = (f"http://{host}", f"https://{host}")
    if method != "GET" and origin is not None and origin not in own:
        raise ApiError(HTTPStatus.FORBIDDEN, "requests from another site are refused")


def route_key(parts: list[str]) -> tuple[str, str]:
    """Return the route name and the match id for the path parts after ``/api``."""
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[0] == "matches":  # noqa: PLR2004
        return "match", parts[1]
    if len(parts) == 3 and parts[0] == "matches" and parts[2] in MATCH_ROUTES:  # noqa: PLR2004
        return parts[2], parts[1]
    return "", ""


ROUTES: Mapping[str, Mapping[str, Handler]] = {
    "health": {"GET": Api.health},
    "catalog": {"GET": Api.get_catalog},
    "matches": {"GET": Api.list_matches, "POST": Api.create_match},
    "match": {"GET": Api.get_match, "DELETE": Api.delete_match},
    "actions": {"POST": Api.post_action},
    "ready": {"POST": Api.post_ready},
    "step": {"POST": Api.post_step},
    "preview": {"GET": Api.get_preview},
    "spectate": {"GET": Api.get_spectate},
    "replay": {"GET": Api.get_replay},
}
"""The API: route name, then method, to handler."""


class GameServer(ThreadingHTTPServer):
    """The HTTP server; it owns the :class:`Api` its handlers call."""

    daemon_threads = True

    def __init__(self, address: tuple[str, int], api: Api, *, verbose: bool = False) -> None:
        """Bind to ``address`` and serve ``api``."""
        super().__init__(address, RequestHandler)
        self.api = api
        self.verbose = verbose
        self.loopback = ipaddress.ip_address(str(self.server_address[0])).is_loopback

    @property
    def url(self) -> str:
        """Return the address the server listens on as a URL."""
        host, port = self.server_address[0], self.server_address[1]
        return f"http://{host!s}:{port}/"


class RequestHandler(BaseHTTPRequestHandler):
    """Reads a request, hands it to the :class:`Api`, and writes the answer."""

    server_version = "tft"
    timeout = SOCKET_TIMEOUT

    def version_string(self) -> str:
        """Name the server in the Server header, without the interpreter's version."""
        return self.server_version

    def do_GET(self) -> None:
        """Answer a GET request."""
        self.answer("GET")

    def do_HEAD(self) -> None:
        """Answer a HEAD request: what GET would answer, without the body."""
        self.answer("GET", head=True)

    def do_POST(self) -> None:
        """Answer a POST request."""
        self.answer("POST")

    def do_DELETE(self) -> None:
        """Answer a DELETE request."""
        self.answer("DELETE")

    def body_length(self) -> int:
        """Return the request's body length.

        Raises:
            ApiError: If the body has no Content-Length, the header is not a
                number, or the body is too large.
        """
        if "Transfer-Encoding" in self.headers and "Content-Length" not in self.headers:
            raise ApiError(HTTPStatus.LENGTH_REQUIRED, "send the body with a Content-Length")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, "bad Content-Length")
        if length > MAX_BODY:
            raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "the request body is too large")
        return length

    def respond(self, method: str) -> Response:
        """Check where the request comes from, read its body and ask the API.

        Raises:
            ApiError: If the request is refused before it reaches the API.
            OSError: If the client stops sending.
        """
        game_server = cast("GameServer", self.server)
        host = self.headers.get("Host", "")
        check_source(method, host, self.headers.get("Origin"), loopback=game_server.loopback)
        body = self.rfile.read(self.body_length())
        content_type = self.headers.get("Content-Type", "")
        return game_server.api.handle(method, self.path, body, content_type)

    def answer(self, method: str, *, head: bool = False) -> None:
        """Send the API's response to the request; ``head`` leaves the body out."""
        try:
            response = self.respond(method)
        except ApiError as error:
            response = json_response(error.status, {"ok": False, "error": error.message})
        except OSError:  # the client stopped sending or went away
            self.close_connection = True
            return
        except Exception:  # the last line of defence: log it here, never leak details
            LOG.exception("unhandled error while answering a %s request", method)
            response = json_response(
                HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "internal error"}
            )
        self.send(response, head=head)

    def write_head(self, response: Response) -> None:
        """Write the status line and the headers of ``response``, the security headers included."""
        self.send_response(response.status)
        for name, value in SECURITY_HEADERS:
            self.send_header(name, value)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))
        self.end_headers()

    def send(self, response: Response, *, head: bool = False) -> None:
        """Write ``response``; ``head`` leaves the body out. A client that has left is no error."""
        try:
            self.write_head(response)
            if not head:
                _ = self.wfile.write(response.body)
        except ConnectionError:
            self.close_connection = True

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        """Answer what the standard library rejects in the API's own shape.

        Its page would repeat the request and carry none of the security
        headers; this answer names the status and nothing else.
        """
        del message, explain  # they can hold parts of the request
        self.close_connection = True
        error = HTTPStatus(code).phrase.lower()
        self.send(json_response(code, {"ok": False, "error": error}), head=self.command == "HEAD")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - standard library name
        """Log requests only when the server is verbose."""
        if cast("GameServer", self.server).verbose:
            super().log_message(format, *args)


def create_server(
    host: str = "127.0.0.1", port: int = 8000, *, lobby: Lobby | None = None, verbose: bool = False
) -> GameServer:
    """Create a server on ``host`` and ``port``; port 0 picks a free one."""
    return GameServer((host, port), Api(lobby), verbose=verbose)
