"""Tests for :mod:`tft.server`: the API without a socket, then over real HTTP."""

from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from importlib.resources import files
from typing import Any

import pytest

from tft import __version__
from tft.items import Component
from tft.name import GAME_NAME
from tft.roster import CHAMPIONS, TRAITS
from tft.rules import Rules
from tft.server import (
    MAX_BODY,
    SEAT,
    STATIC,
    Api,
    ApiError,
    GameServer,
    Lobby,
    Response,
    create_server,
    flag,
    json_response,
    parse_action,
    parse_body,
    route_key,
    whole_number,
)

JSON = "application/json"
SHORT = Rules(stages=1)


def call(api: Api, method: str, path: str, payload: Any = None) -> tuple[int, Any]:
    body = json.dumps(payload).encode() if payload is not None else b""
    response = api.handle(method, path, body, JSON)
    data = json.loads(response.body) if response.content_type == JSON else response.body
    return int(response.status), data


def new_match(api: Api, **options: Any) -> dict[str, Any]:
    status, data = call(api, "POST", "/api/matches", {"seed": 7, "bots": 2, **options})
    assert status == 201
    state: dict[str, Any] = data["state"]
    return state


@pytest.fixture
def api() -> Api:
    return Api(Lobby(SHORT))


# Parsing ----------------------------------------------------------------------


def test_parse_body() -> None:
    assert parse_body(b"", "") == {}
    assert parse_body(b'{"a": 1}', "application/json; charset=utf-8") == {"a": 1}
    with pytest.raises(ApiError, match="application/json") as wrong_type:
        parse_body(b"{}", "text/plain")
    assert wrong_type.value.status == 415
    for bad in (b"[1]", b"{", b"\xff\xfe"):
        with pytest.raises(ApiError, match="must be a JSON object") as error:
            parse_body(bad, JSON)
        assert error.value.status == 400


def test_whole_number_and_flag() -> None:
    assert whole_number(3, 0, 5, "x") == 3
    for bad in (True, "3", 3.0, None, -1, 6):
        with pytest.raises(ApiError, match="x must be a whole number, 0 to 5"):
            whole_number(bad, 0, 5, "x")
    assert flag(False, "market") is False
    with pytest.raises(ApiError, match="market must be true or false"):
        flag(1, "market")


def test_parse_action() -> None:
    action = parse_action({"kind": "field", "args": [0, 3, 2]})
    assert (action.kind, action.args) == ("field", (0, 3, 2))
    assert parse_action({"kind": "reroll"}).args == ()
    for bad in ({}, {"kind": "dance"}, {"kind": ["buy"]}):
        with pytest.raises(ApiError, match="unknown action"):
            parse_action(bad)
    for bad_args in ("0", [0, 1, 2, 3, 4], [-1], ["0"], [True]):
        with pytest.raises(ApiError):
            parse_action({"kind": "buy", "args": bad_args})


def test_route_key() -> None:
    assert route_key(["health"]) == ("health", "")
    assert route_key(["matches"]) == ("matches", "")
    assert route_key(["matches", "abc"]) == ("match", "abc")
    assert route_key(["matches", "abc", "ready"]) == ("ready", "abc")
    assert route_key(["matches", "abc", "nope"]) == ("", "")
    assert route_key(["other", "abc"]) == ("", "")
    assert route_key([]) == ("", "")
    assert route_key(["a", "b", "c", "d"]) == ("", "")


# The API ----------------------------------------------------------------------


def test_health_and_catalog(api: Api) -> None:
    assert call(api, "GET", "/api/health") == (
        200,
        {"ok": True, "status": "ok", "name": GAME_NAME, "version": __version__},
    )
    status, data = call(api, "GET", "/api/catalog?x=1")
    assert status == 200
    assert len(data["champions"]) == 25
    assert data["ok"] is True


def test_create_a_match_with_defaults_and_options(api: Api) -> None:
    status, data = call(api, "POST", "/api/matches")
    assert status == 201
    state = data["state"]
    assert (state["phase"], state["mode"], state["spectator"], state["has_seat"]) == (
        "planning",
        "market",
        False,
        True,
    )
    assert state["seat"]["name"] == SEAT
    assert len(state["others"]) == 7
    assert state["round"]["label"] == "1-1"
    assert state["last"] == {"report": None, "summary": None}
    power = new_match(api, market=False)
    assert (power["mode"], power["pack"], len(power["others"])) == ("power", None, 2)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"seed": "7"}, "seed must be a whole number"),
        ({"seed": -1}, "seed must be a whole number"),
        ({"bots": 0}, "bots must be a whole number, 1 to 7"),
        ({"bots": 8}, "bots must be a whole number, 1 to 7"),
        ({"market": "yes"}, "market must be true or false"),
        ({"spectate": 1}, "spectate must be true or false"),
    ],
)
def test_create_rejects_bad_options(api: Api, payload: dict[str, Any], message: str) -> None:
    status, data = call(api, "POST", "/api/matches", payload)
    assert status == 400
    assert data["ok"] is False
    assert message in data["error"]


def test_actions_refusals_and_bad_requests(api: Api) -> None:
    match_id = new_match(api)["id"]
    actions = f"/api/matches/{match_id}/actions"
    status, data = call(api, "POST", actions, {"kind": "buy", "args": [0]})
    assert status == 200
    assert data["message"].startswith("bought shop slot 0")
    assert len(data["state"]["seat"]["bench"]) == 1
    status, data = call(api, "POST", actions, {"kind": "field", "args": [0, 3, 2]})
    assert data["state"]["seat"]["board"][0]["cell"] == [3, 2]
    status, data = call(api, "POST", actions, {"kind": "move", "args": [0, 0, 0]})
    assert data["message"].endswith("row 0, column 0")
    assert call(api, "POST", actions, {"kind": "buy", "args": [99]}) == (
        400,
        {"ok": False, "error": "shop slot 99 does not exist"},
    )
    assert call(api, "POST", actions, {"kind": "dance"}) == (
        400,
        {"ok": False, "error": "unknown action"},
    )
    response = api.handle("POST", actions, b'{"kind": "buy"}', "text/plain")
    assert response.status == 415
    assert call(api, "POST", "/api/matches/nope/actions", {"kind": "reroll"}) == (
        404,
        {"ok": False, "error": "no such match"},
    )


def test_ready_fights_summarises_and_opens_the_next_round(api: Api) -> None:
    match_id = new_match(api)["id"]
    _ = call(api, "POST", f"/api/matches/{match_id}/actions", {"kind": "buy", "args": [0]})
    _ = call(api, "POST", f"/api/matches/{match_id}/actions", {"kind": "field", "args": [0]})
    status, data = call(api, "POST", f"/api/matches/{match_id}/ready")
    assert status == 200
    state = data["state"]
    assert state["round"]["label"] == "1-2"
    report, summary = state["last"]["report"], state["last"]["summary"]
    assert report["round"] == "1-1"
    assert len(report["fights"]) == 3
    assert summary["opponent"] == "The Market"
    assert summary["units"][0]["closes"][0] == 100.0
    status, listing = call(api, "GET", "/api/matches")
    assert listing["matches"][0]["id"] == match_id
    assert listing["matches"][0]["round"] == "1-2"
    seat = listing["matches"][0]["seats"][0]
    assert (seat["name"], seat["alive"]) == ("you", True)
    assert 0 < seat["health"] <= 100


def test_a_match_played_to_the_end_keeps_its_replay(api: Api) -> None:
    match_id = new_match(api)["id"]
    state: dict[str, Any] = {}
    for _ in range(SHORT.max_rounds):
        _, data = call(api, "POST", f"/api/matches/{match_id}/ready")
        state = data["state"]
    assert state["phase"] == "finished"
    assert sorted(state["placements"]) == ["ana", "bo", "you"]
    assert state["round"] is None
    conflict = (409, {"ok": False, "error": "the match is not waiting for actions"})
    assert call(api, "POST", f"/api/matches/{match_id}/ready") == conflict
    assert call(api, "POST", f"/api/matches/{match_id}/actions", {"kind": "reroll"}) == conflict
    assert call(api, "GET", f"/api/matches/{match_id}/preview") == conflict
    status, data = call(api, "GET", f"/api/matches/{match_id}/replay")
    assert status == 200
    replay = data["replay"]
    assert (replay["format"], replay["seat"], replay["pack"]) == (3, "you", "starter")
    assert replay["result"] == state["placements"]
    assert len(replay["rounds"]) == SHORT.max_rounds
    assert call(api, "GET", "/api/matches")[1]["matches"][0]["finished"] is True


def test_the_seat_can_be_eliminated_and_the_bots_finish_the_match() -> None:
    api = Api(Lobby(Rules(stages=3, starting_health=3)))
    match_id = new_match(api, bots=3)["id"]
    state: dict[str, Any] = {"phase": "planning"}
    for _ in range(20):
        if state["phase"] == "finished":
            break
        _, data = call(api, "POST", f"/api/matches/{match_id}/ready")
        state = data["state"]
    assert state["phase"] == "finished"
    assert state["seat"]["alive"] is False
    assert state["placements"][-1] == "you" or "you" in state["placements"]
    assert state["last"]["summary"]["outcome"] == "lost"


def test_preview_needs_a_market(api: Api) -> None:
    market_id = new_match(api)["id"]
    _ = call(api, "POST", f"/api/matches/{market_id}/actions", {"kind": "buy", "args": [0]})
    _ = call(api, "POST", f"/api/matches/{market_id}/actions", {"kind": "field", "args": [0]})
    status, data = call(api, "GET", f"/api/matches/{market_id}/preview")
    assert status == 200
    assert [entry["name"] for entry in data["odds"]] == ["ana", "bo"]
    assert all(0 <= entry["probability"] <= 1 for entry in data["odds"])
    power_id = new_match(api, market=False)["id"]
    assert call(api, "GET", f"/api/matches/{power_id}/preview") == (
        400,
        {"ok": False, "error": "the preview needs a market pack"},
    )


def test_spectating_shows_public_state_only(api: Api) -> None:
    match_id = new_match(api)["id"]
    _ = call(api, "POST", f"/api/matches/{match_id}/ready")
    status, data = call(api, "GET", f"/api/matches/{match_id}/spectate")
    assert status == 200
    state = data["state"]
    assert (state["spectator"], state["has_seat"], state["seat"]) == (True, True, None)
    assert [seat["name"] for seat in state["others"]] == ["you", "ana", "bo"]
    assert "shop" not in state["others"][0]
    assert state["last"]["summary"] is None
    assert state["last"]["report"]["round"] == "1-1"
    own = call(api, "GET", f"/api/matches/{match_id}")[1]["state"]
    assert own["seat"]["name"] == "you"
    assert own["last"]["summary"] is not None


def test_bot_matches_are_stepped_and_have_no_seat(api: Api) -> None:
    state = new_match(api, spectate=True, bots=3)
    match_id = state["id"]
    assert (state["spectator"], state["has_seat"], state["phase"]) == (
        True,
        False,
        "between rounds",
    )
    assert len(state["others"]) == 4
    status, data = call(api, "POST", f"/api/matches/{match_id}/step")
    assert status == 200
    assert data["state"]["last"]["report"]["round"] == "1-1"
    no_seat = (409, {"ok": False, "error": "this match has no player seat"})
    assert call(api, "POST", f"/api/matches/{match_id}/ready") == no_seat
    assert call(api, "POST", f"/api/matches/{match_id}/actions", {"kind": "reroll"}) == no_seat
    assert call(api, "GET", f"/api/matches/{match_id}/replay") == no_seat
    for _ in range(SHORT.max_rounds - 1):
        _ = call(api, "POST", f"/api/matches/{match_id}/step")
    assert call(api, "POST", f"/api/matches/{match_id}/step") == (
        409,
        {"ok": False, "error": "the match is finished"},
    )
    seat_id = new_match(api)["id"]
    assert call(api, "POST", f"/api/matches/{seat_id}/step") == (
        409,
        {"ok": False, "error": "only bot matches can be stepped"},
    )


def test_delete_and_unknown_routes(api: Api) -> None:
    match_id = new_match(api)["id"]
    assert call(api, "DELETE", f"/api/matches/{match_id}") == (200, {"ok": True})
    assert call(api, "DELETE", f"/api/matches/{match_id}") == (200, {"ok": True})
    missing = (404, {"ok": False, "error": "no such match"})
    assert call(api, "GET", f"/api/matches/{match_id}") == missing
    not_found = (404, {"ok": False, "error": "not found"})
    assert call(api, "GET", "/api/nope") == not_found
    assert call(api, "GET", f"/api/matches/{match_id}/nope") == not_found
    assert call(api, "GET", "/api/") == not_found
    not_allowed = (405, {"ok": False, "error": "method not allowed"})
    assert call(api, "PUT", "/api/health") == not_allowed
    assert call(api, "GET", f"/api/matches/{match_id}/ready") == not_allowed


def test_static_files(api: Api) -> None:
    script = "text/javascript; charset=utf-8"
    expected = {
        "/": "text/html; charset=utf-8",
        "/index.html": "text/html; charset=utf-8",
        "/app.js": script,
        "/logic.js": script,
        "/art.js": script,
        "/dom.js": script,
        "/figures.js": script,
        "/models.js": script,
        "/studio.js": script,
        "/pieces.js": script,
        "/scene.js": script,
        "/style.css": "text/css; charset=utf-8",
        "/favicon.svg": "image/svg+xml",
    }
    assert {path: kind for path, (_, kind) in STATIC.items()} == expected
    for path, content_type in expected.items():
        response = api.handle("GET", path)
        assert (int(response.status), response.content_type) == (200, content_type)
        assert response.body
    packaged = {entry.name for entry in files("tft").joinpath("web").iterdir() if entry.is_file()}
    assert {name for name, _ in STATIC.values()} == packaged
    assert api.handle("GET", "/?seed=3").status == 200
    page = api.handle("GET", "/").body.decode("utf-8")
    assert f"<title>{GAME_NAME}</title>" in page
    assert f'class="brand">{GAME_NAME}</h1>' in page
    assert api.handle("GET", "/../pyproject.toml").status == 404
    assert api.handle("GET", "/nope.js").status == 404
    assert api.handle("POST", "/app.js").status == 405


def keys_missing_from(script: str, names: list[str]) -> list[str]:
    """Return the ``names`` that are not keys of a table in the client script ``script``."""
    return [
        name
        for name in names
        if not re.search(rf'^  "?{re.escape(name)}"?: \[', script, flags=re.MULTILINE)
    ]


def test_the_art_covers_the_roster_the_traits_and_the_components(api: Api) -> None:
    art = api.handle("GET", "/art.js").body.decode("utf-8")
    names = [champion.name for champion in CHAMPIONS]
    names += list(TRAITS)
    names += [str(component) for component in Component]
    assert keys_missing_from(art, names) == []
    assert keys_missing_from(art, ["Nobody"]) == ["Nobody"]


def test_every_champion_has_a_3d_figure(api: Api) -> None:
    models = api.handle("GET", "/models.js").body.decode("utf-8")
    assert keys_missing_from(models, [champion.name for champion in CHAMPIONS]) == []


# The lobby --------------------------------------------------------------------


def test_the_lobby_evicts_finished_matches_first_then_the_least_recently_used() -> None:
    lobby = Lobby(SHORT, max_matches=2)
    first = lobby.create(1, 1, market=False, spectate=True)
    second = lobby.create(2, 1, market=False, spectate=True)
    _ = second.game.run()
    third = lobby.create(3, 1, market=False, spectate=True)
    assert set(lobby.matches) == {first.id, third.id}
    _ = lobby.get(first.id)
    fourth = lobby.create(4, 1, market=False, spectate=True)
    assert set(lobby.matches) == {first.id, fourth.id}
    assert [card["id"] for card in lobby.cards()] == [fourth.id, first.id]
    lobby.remove("unknown")
    with pytest.raises(ApiError, match="no such match"):
        lobby.get(third.id)


def test_the_lobby_validates_its_arguments() -> None:
    with pytest.raises(ValueError, match="max_matches"):
        Lobby(max_matches=0)
    lobby = Lobby(SHORT)
    for bots in (0, 8):
        with pytest.raises(ValueError, match="bots must be 1 to 7"):
            lobby.create(1, bots, market=True, spectate=False)
    assert json_response(200, {"a": 1}) == Response(200, b'{"a": 1}', JSON)


# Over HTTP --------------------------------------------------------------------


@pytest.fixture
def server() -> Iterator[GameServer]:
    game_server = create_server("127.0.0.1", 0, lobby=Lobby(SHORT))
    thread = threading.Thread(target=game_server.serve_forever, daemon=True)
    thread.start()
    yield game_server
    game_server.shutdown()
    game_server.server_close()
    thread.join(timeout=5)


def fetch(
    server: GameServer,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(  # noqa: S310 - a local test server
        server.url.rstrip("/") + path, data=body, method=method, headers=headers or {}
    )
    try:
        with opener.open(request, timeout=10) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        with error:
            return error.code, dict(error.headers), error.read()


def test_http_round_trip_with_security_headers(server: GameServer) -> None:
    assert server.url.startswith("http://127.0.0.1:")
    status, headers, body = fetch(server, "GET", "/api/health")
    assert (status, json.loads(body)["status"]) == (200, "ok")
    assert headers["Content-Type"] == JSON
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Cache-Control"] == "no-store"
    policy = headers["Content-Security-Policy"]
    assert "default-src 'self'" in policy
    assert "img-src 'self' data: blob:" in policy
    assert "unsafe" not in policy
    assert headers["Referrer-Policy"] == "no-referrer"
    status, headers, body = fetch(server, "GET", "/")
    assert status == 200
    assert headers["Content-Type"] == "text/html; charset=utf-8"
    payload = json.dumps({"seed": 3, "bots": 1}).encode()
    status, _, body = fetch(server, "POST", "/api/matches", payload, {"Content-Type": JSON})
    assert status == 201
    match_id = json.loads(body)["state"]["id"]
    status, _, body = fetch(server, "POST", f"/api/matches/{match_id}/ready", b"", {})
    assert (status, json.loads(body)["state"]["round"]["label"]) == (200, "1-2")
    status, _, body = fetch(server, "DELETE", f"/api/matches/{match_id}")
    assert (status, json.loads(body)) == (200, {"ok": True})


def test_http_rejects_oversized_and_malformed_bodies(server: GameServer) -> None:
    big = b"x" * (MAX_BODY + 1)
    status, _, body = fetch(server, "POST", "/api/matches", big, {"Content-Type": JSON})
    assert (status, json.loads(body)["error"]) == (413, "the request body is too large")
    status, _, body = fetch(server, "POST", "/api/matches", b"{", {"Content-Type": JSON})
    assert (status, json.loads(body)["error"]) == (400, "the request body must be a JSON object")
    status, _, body = fetch(server, "GET", "/api/health", None, {"Content-Length": "abc"})
    assert (status, json.loads(body)["error"]) == (400, "bad Content-Length")


def test_http_hides_unexpected_errors(server: GameServer, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> Response:
        message = "secret detail"
        raise RuntimeError(message)

    monkeypatch.setattr(server.api, "handle", boom)
    status, _, body = fetch(server, "GET", "/api/health")
    assert status == 500
    assert json.loads(body) == {"ok": False, "error": "internal error"}
    assert b"secret" not in body


def test_verbose_servers_log_requests(capfd: pytest.CaptureFixture[str]) -> None:
    loud = create_server("127.0.0.1", 0, lobby=Lobby(SHORT), verbose=True)
    thread = threading.Thread(target=loud.serve_forever, daemon=True)
    thread.start()
    try:
        assert fetch(loud, "GET", "/api/health")[0] == 200
    finally:
        loud.shutdown()
        loud.server_close()
        thread.join(timeout=5)
    assert "GET /api/health" in capfd.readouterr().err
