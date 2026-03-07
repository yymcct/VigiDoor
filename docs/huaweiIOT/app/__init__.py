"""
Flask 应用工厂
"""
from flask_api import FlaskAPI
from flask_cors import CORS


def create_app() -> FlaskAPI:
    app = FlaskAPI(__name__)
    CORS(app)

    # 注册蓝图
    from app.routes.health import health_bp
    from app.routes.stream import stream_bp
    from app.routes.zlm_webhook import zlm_bp
    from app.routes.voice import voice_bp

    app.register_blueprint(health_bp)                          # GET  /health
    app.register_blueprint(stream_bp, url_prefix="/api/v1")    # POST /api/v1/stream/start|stop
    app.register_blueprint(zlm_bp, url_prefix="/index/hook")   # POST /index/hook/on_stream_not_found|on_stream_none_reader
    app.register_blueprint(voice_bp, url_prefix="/api/v1/voice")  # POST /api/v1/voice/call/*

    # 初始化 WebSocket（必须在蓝图注册之后）
    from app.services.websocket_handler import init_socketio
    socketio = init_socketio(app)
    
    # 将 socketio 实例存储到 app 扩展中，以便在其他地方使用
    app.socketio = socketio

    return app
