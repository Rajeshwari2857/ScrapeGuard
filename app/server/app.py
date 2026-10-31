from flask import Flask
from flask_cors import CORS
from .db import init_db

def create_app():
    app = Flask(__name__)
    CORS(app, supports_credentials=True)
    # lazy init — don't fail if Mongo not reachable in demo
    try:
        app.db = init_db()
    except Exception as e:
        print(f"[db] init skipped: {e}")
        app.db = None

    from .routes_ingest import bp as ingest_bp
    from .routes_dashboard import bp as dash_bp
    from .routes_fixes import bp as fixes_bp
    from .routes_projects import bp as proj_bp
    app.register_blueprint(ingest_bp)
    app.register_blueprint(dash_bp)
    app.register_blueprint(fixes_bp)
    app.register_blueprint(proj_bp)

    @app.get("/health")
    def health():
        return {"ok": True, "db": app.db is not None}

    @app.get("/")
    @app.get("/dashboard")
    def serve_dashboard():
        import os
        from flask import send_file
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dash_path = os.path.join(root_dir, "scrapeguard-dashboard.html")
        return send_file(dash_path)

    return app

if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=True)
