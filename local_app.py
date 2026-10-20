"""Opt-in loopback HTTP interface; never registered by the hosted application."""
import ipaddress
import secrets

from flask import jsonify, request, send_from_directory

from app import ROOT, create_app
from local_jobs import JobConflict, JobMissing


def create_local_app(manager, origin="http://127.0.0.1:8000"):
    app = create_app()
    app.config.update(LOCAL_ORIGIN=origin, LOCAL_TOKEN=secrets.token_urlsafe(32),
                      LOCAL_RUN_FILES=manager.files, MAX_CONTENT_LENGTH=16384)

    @app.before_request
    def local_boundary():
        expected = app.config["LOCAL_ORIGIN"]
        try:
            local = ipaddress.ip_address(request.remote_addr).is_loopback
        except (TypeError, ValueError):
            local = False
        if (not local or request.host_url.rstrip("/") != expected or
                request.headers.get("Origin", expected) != expected or
                request.headers.get("Sec-Fetch-Site") == "cross-site"):
            return jsonify(error="Use this server's printed loopback URL"), 403
        if request.path.startswith("/api/local/") and request.path != "/api/local/config":
            token = request.headers.get("X-Inquest-Token", "")
            if not secrets.compare_digest(token, app.config["LOCAL_TOKEN"]):
                return jsonify(error="Refresh the local investigation page to reconnect"), 403

    @app.after_request
    def private_response(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.errorhandler(JobMissing)
    def missing(error):
        return jsonify(error=str(error)), 404

    @app.errorhandler(JobConflict)
    def conflict(error):
        return jsonify(error=str(error)), 409

    @app.errorhandler(413)
    def too_large(error):
        return jsonify(error="Request exceeds the local 16 KiB limit"), 413

    @app.get("/investigate")
    def investigate():
        response = send_from_directory(ROOT / "public", "investigate.html")
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; base-uri 'none'; object-src 'none'; "
            "form-action 'none'; frame-ancestors 'none'"
        )
        return response

    @app.get("/api/local/config")
    def config():
        return jsonify(token=app.config["LOCAL_TOKEN"], suites=manager.catalog,
                       budgets=[5, 10, 20], backend="offline heuristic", policy="v2")

    @app.get("/api/local/jobs")
    def jobs():
        return jsonify(jobs=manager.list())

    @app.post("/api/local/jobs")
    def start():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) != {"suite", "case_id", "budget", "request_key"}:
            return jsonify(error="Provide suite, case_id, budget and request_key only"), 400
        try:
            result = manager.submit(**body)
        except ValueError as error:
            if isinstance(error, JobConflict):
                raise
            return jsonify(error=str(error)), 400
        return jsonify(result), 202

    @app.get("/api/local/jobs/<job_id>")
    def job(job_id):
        return jsonify(manager.get(job_id))

    @app.post("/api/local/jobs/<job_id>/cancel")
    def cancel(job_id):
        return jsonify(manager.cancel(job_id))

    @app.post("/api/local/jobs/<job_id>/resume")
    def resume(job_id):
        return jsonify(manager.resume(job_id)), 202

    return app
