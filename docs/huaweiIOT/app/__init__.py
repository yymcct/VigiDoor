"""
Flask 应用工厂
"""
from flask import Flask
from flask_cors import CORS


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    # 注册蓝图
    from app.routes.health import health_bp
    from app.routes.stream import stream_bp
    from app.routes.zlm_webhook import zlm_bp

    app.register_blueprint(health_bp)                          # GET  /health
    app.register_blueprint(stream_bp, url_prefix="/api/v1")    # POST /api/v1/stream/start|stop
    app.register_blueprint(zlm_bp, url_prefix="/index/hook")   # POST /index/hook/on_stream_not_found|on_stream_none_reader

    return app
