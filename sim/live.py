"""Session-scoped daily continuation; keep only the latest day's browser trace."""

from datetime import date, timedelta
import threading
import time
import uuid

from sim.interactables.manifest import load_manifest
from sim.interactables.simulation import run_day


class LiveSessions:
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()

    def request(self, method, path, payload=None):
        # Import lazily: Council owns pinned world-input validation and HTTP errors.
        from sim.council import CouncilError, _world_inputs

        with self.lock:
            now = time.monotonic()
            self.sessions = {key: value for key, value in self.sessions.items()
                             if now - value["touched"] < 7 * 86400}
            if method == "POST" and path == "/api/council/live":
                population = payload.get("population")
                policy = payload.get("policy")
                if type(population) is not int or population not in (200, 600, 1200, 2400) or policy not in ("baseline", "emergency"):
                    raise CouncilError(400, "invalid_live_run", "Choose a supported population and policy.")
                if len(self.sessions) >= 16:
                    raise CouncilError(503, "live_capacity", "Too many active live sessions. Restart the local service to clear unused sessions.")
                manifest = load_manifest()
                world, district, snapshot = _world_inputs(population, manifest["seed"])
                session = dict(population=population, policy=policy, seed=manifest["seed"],
                               timezone=manifest["timezone"], date=manifest["start_date"],
                               district=district, snapshot=snapshot, snapshot_hash=world["source_sha256"],
                               checkpoint=None, day=0, touched=now)
                session_id = str(uuid.uuid4())
                trace, checkpoint = self._day(session, session_id)
                session.update(trace=trace, checkpoint=checkpoint)
                self.sessions[session_id] = session
                return trace

            parts = path.removeprefix("/api/council/live/").split("/")
            session = self.sessions.get(parts[0])
            if session is None:
                raise CouncilError(404, "live_session_missing", "This live session has expired or the service restarted. Restart the simulation.")
            session["touched"] = now
            if method == "POST" and len(parts) == 2 and parts[1] == "close":
                del self.sessions[parts[0]]
                return {"closed": True}
            if method == "GET" and len(parts) == 1:
                return session["trace"]
            if method == "POST" and len(parts) == 2 and parts[1] == "next":
                day = payload.get("day")
                if type(day) is not int:
                    raise CouncilError(400, "invalid_live_day", "day must be an integer.")
                if day == session["day"] - 1:
                    return session["trace"]  # Retry after a lost response must not settle twice.
                if day != session["day"]:
                    raise CouncilError(409, "live_day_changed", "The live session has already advanced.")
                following = {**session, "date": (date.fromisoformat(session["date"]) + timedelta(days=1)).isoformat(),
                             "day": day + 1}
                trace, checkpoint = self._day(following, parts[0])
                following.update(trace=trace, checkpoint=checkpoint)
                self.sessions[parts[0]] = following
                return trace
            raise CouncilError(404, "not_found", "Live simulation resource was not found.")

    @staticmethod
    def _day(session, session_id):
        checkpoint = {}
        trace = run_day(session["district"], session["date"], session["population"], session["seed"],
                        session["policy"] == "emergency", site_snapshot=session["snapshot"],
                        site_snapshot_sha256=session["snapshot_hash"], timezone_name=session["timezone"],
                        carry=session["checkpoint"], checkpoint_out=checkpoint)
        trace.update(live_session_id=session_id, live_day=session["day"],
                     live_trace_url=f"/api/council/live/{session_id}")
        trace["assumptions"]["scope"] = (
            "Continuous synthetic daily operations. Cash, food and prices carry across midnight; "
            "daily service capacity renews. No recurring income, supplier imports or municipal grants "
            "are assumed. Daily ledgers are rebased from the preceding close; reports cover this day only."
        )
        return trace, checkpoint


sessions = LiveSessions()
