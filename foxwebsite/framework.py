import os
import re
import json
import hmac
import hashlib
import asyncio
import traceback
from typing import Callable, Dict, Tuple, Optional, Any, List
from urllib.parse import parse_qs
from string import Template
from contextvars import ContextVar
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError
import uvicorn

# ======================
# 上下文变量
# ======================
_request_ctx = ContextVar("request", default=None)
_session_ctx = ContextVar("session", default=None)
_app_ctx = ContextVar("app", default=None)

# ======================
# 工具函数
# ======================

def sign(data: str, secret: str) -> str:
    return hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()

def serialize_session(data: dict, secret: str) -> str:
    serialized = json.dumps(data, separators=(',', ':'), sort_keys=True)
    sig = sign(serialized, secret)
    return f"{serialized}.{sig}"

def deserialize_session(value: str, secret: str) -> Optional[dict]:
    if not isinstance(value, str) or "." not in value:
        return None
    data, sig = value.rsplit(".", 1)
    if not hmac.compare_digest(sig, sign(data, secret)):
        return None
    try:
        return json.loads(data)
    except:
        return None

# ======================
# 请求类
# ======================

class Request:
    def __init__(self, scope, receive):
        self.scope = scope
        self.method = scope["method"]
        self.path = scope["path"]
        self.query_params = parse_qs(scope.get("query_string", b"").decode())
        self._body = None
        self.receive = receive
        self._cookies = None
        self.params = {}  # 路径参数
        self._response_headers = []

    @property
    def cookies(self):
        if self._cookies is None:
            self._cookies = {}
            for header in self.scope.get("headers", []):
                if header[0].lower() == b"cookie":
                    cookie_str = header[1].decode()
                    for item in cookie_str.split(";"):
                        if "=" in item:
                            k, v = item.strip().split("=", 1)
                            self._cookies[k] = v
        return self._cookies

    async def body(self):
        if self._body is None:
            body = b""
            more_body = True
            while more_body:
                message = await self.receive()
                body += message.get("body", b"")
                more_body = message.get("more_body", False)
            self._body = body
        return self._body

    def clear_session(self):
        """清除 session 并设置删除 cookie 的响应头"""
        if hasattr(self, "session") and isinstance(self.session, dict):
            self.session.clear()
        cookie_header = f"{self.app.session_cookie_name}=deleted; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly"
        self._response_headers.append((b"set-cookie", cookie_header.encode()))

    async def json(self):
        body = await self.body()
        return json.loads(body.decode()) if body else None

# ======================
# 响应函数
# ======================

async def send_response(send, status: int, content: str, content_type: str = "text/html"):
    content_bytes = content.encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", content_type.encode()),
            (b"content-length", str(len(content_bytes)).encode())
        ],
    })
    await send({
        "type": "http.response.body",
        "body": content_bytes,
    })

async def send_json(send, data, status: int = 200):
    content = json.dumps(data, ensure_ascii=False)
    await send_response(send, status, content, "application/json")

async def serve_file(send, file_path: str, content_type: str = "text/html"):
    if os.path.exists(file_path) and os.path.isfile(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        await send_response(send, 200, content, content_type)
    else:
        await send_response(send, 404, "File not found")

# ======================
# MicroPy 核心
# ======================

class MicroPy:
    def __init__(self, template_folder="templates", static_url_path="/static", secret_key="dev-secret"):
        self.template_folder = template_folder
        self.static_url_path = static_url_path
        self.secret_key = secret_key
        self.session_cookie_name = "micropy_session"
        self.session_serializer = URLSafeTimedSerializer(secret_key, salt="session")
        self.app = self  # 兼容 Flask 风格
        os.makedirs(template_folder, exist_ok=True)

        # 路由系统
        self.routes: List[Tuple[re.Pattern, str, Callable]] = []
        self.route_map: Dict[str, str] = {}  # 用于 url_for

        # 模板系统
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_folder),
            autoescape=True,
            extensions=["jinja2.ext.loopcontrols"]
        )

        # 配置系统
        # 在 MicroPy 中添加配置
        self.config = {
            "SECRET_KEY": secret_key,
            "SESSION_COOKIE_NAME": "micropy_session",
            "SESSION_COOKIE_SECURE": False,  # 生产环境设为 True
            "SESSION_COOKIE_HTTPONLY": True,  # 防止 XSS
            "SESSION_COOKIE_SAMESITE": "Lax",  # 防 CSRF
            "SESSION_PERMANENT": False,
            "SESSION_EXPIRE_AT_BROWSER_CLOSE": True,
            "DEBUG": False,
            "TESTING": False,
        }

        # 中间件
        self.before_request_funcs = []
        self.after_request_funcs = []
        self.errorhandler_funcs = {}

        # 全局上下文
        self._app_context = None

    def config_from_object(self, obj):
        """从对象加载配置"""
        for key in dir(obj):
            if key.isupper():
                self.config[key] = getattr(obj, key)

    def config_from_pyfile(self, filename):
        """从 Python 文件加载配置"""
        with open(filename, "r") as f:
            exec(f.read(), self.config)

    def config_from_envvar(self, var_name):
        """从环境变量加载配置"""
        value = os.getenv(var_name)
        if value:
            self.config.update(json.loads(value))

    def config_from_prefixed_env(self, prefix):
        """从前缀环境变量加载配置"""
        for key, value in os.environ.items():
            if key.startswith(prefix + "_"):
                subkey = key[len(prefix) + 1:].lower()
                self.config[subkey] = value

    def route(self, path: str, methods=("GET",)):
        pattern_str = "^" + re.escape(path) + "$"
        pattern_str = re.sub(r"\\{([^}/]+)\\}", r"(?P<\1>[^/]+)", pattern_str)
        pattern = re.compile(pattern_str)

        def decorator(handler: Callable):
            for method in methods:
                self.routes.append((pattern, method.upper(), handler))
                self.route_map[f"{method.upper()}:{path}"] = path
            return handler
        return decorator

    def get(self, path: str):
        return self.route(path, methods=["GET"])

    def post(self, path: str):
        return self.route(path, methods=["POST"])

    def url_for(self, endpoint: str, **values) -> str:
        if endpoint in self.route_map:
            path = self.route_map[endpoint]
            for k, v in values.items():
                path = path.replace(f"{{{k}}}", str(v))
            return path
        return "/"

    def render_template(self, filename: str, **context) -> str:
        try:
            template = self.jinja_env.get_template(filename)
            return template.render(**context)
        except TemplateNotFound:
            raise FileNotFoundError(f"Template {filename} not found.")
        except TemplateSyntaxError as e:
            raise RuntimeError(f"Template syntax error in {filename}: {e}")

    def before_request(self, func):
        self.before_request_funcs.append(func)
        return func

    def after_request(self, func):
        self.after_request_funcs.append(func)
        return func

    def errorhandler(self, code_or_exception):
        def decorator(func):
            self.errorhandler_funcs[code_or_exception] = func
            return func
        return decorator

    def abort(self, code: int):
        """主动抛出错误，触发 errorhandler"""
        raise RuntimeError(f"Abort with status code {code}")

    def clear_session(self, request):
        request.session.clear()
        cookie_header = f"{self.session_cookie_name}=deleted; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly"
        request._response_headers.append((b"set-cookie", cookie_header.encode()))

    def _build_headers_with_session(self, request, content_type: str = "text/html") -> List[Tuple[bytes, bytes]]:
        headers = [
            (b"content-type", content_type.encode()),
        ]

        if hasattr(request, "_response_headers"):
            headers.extend(request._response_headers)

        if hasattr(request, "session") and isinstance(request.session, dict) and request.session:
            try:
                session_data = serialize_session(request.session, self.secret_key)
                cookie_header = f"{self.session_cookie_name}={session_data}; Path=/; HttpOnly"
                if self.config["SESSION_COOKIE_SECURE"]:
                    cookie_header += "; Secure"
                if self.config["SESSION_COOKIE_SAMESITE"]:
                    cookie_header += f"; SameSite={self.config['SESSION_COOKIE_SAMESITE']}"
                if self.config["SESSION_PERMANENT"]:
                    cookie_header += f"; Max-Age={self.config.get('PERMANENT_SESSION_LIFETIME', 31536000)}"
                headers.append((b"set-cookie", cookie_header.encode()))
            except Exception as e:
                print(f"Session serialization failed: {e}")

        return headers

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        request = Request(scope, receive)
        method = request.method
        path = request.path

        # 解析 session —— 确保它总是 dict，永不为 None
        cookie = request.cookies.get(self.session_cookie_name)
        session_data = deserialize_session(cookie, self.secret_key)
        request.session = session_data if isinstance(session_data, dict) else {}
        
        # 忽略 favicon.ico
        if path == "/favicon.ico":
            await send_response(send, 204, "", "image/x-icon")
            return

        # 静态文件
        if path.startswith(self.static_url_path):
            file_path = "." + path
            if os.path.exists(file_path) and os.path.isfile(file_path):
                ext = os.path.splitext(file_path)[1]
                ct_map = {
                    ".css": "text/css", ".js": "application/javascript",
                    ".png": "image/png", ".jpg": "image/jpeg", ".ico": "image/x-icon",
                    ".html": "text/html", ".json": "application/json"
                }
                ct = ct_map.get(ext, "application/octet-stream")
                with open(file_path, "rb") as f:
                    data = f.read()
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"content-type", ct.encode()),
                        (b"content-length", str(len(data)).encode())
                    ],
                })
                await send({
                    "type": "http.response.body",
                    "body": data,
                })
                return

        # 路由匹配
        handler = None
        for pattern, method_name, func in self.routes:
            match = pattern.match(path)
            if match and method_name == method:
                handler = func
                request.params = match.groupdict()
                break

        if not handler:
            await send_response(send, 404, "<h1>404 The route does not exist.</h1>")
            return

        # 执行 before_request
        for func in self.before_request_funcs:
            try:
                result = func()
                if result is not None:
                    await send_json(send, result, 400)
                    return
            except Exception as e:
                print(f"Before request error: {e}")
                await send_response(send, 500, f"Before request error: {e}")
                return

        try:
            # 调用 handler
            response = await handler(request) if asyncio.iscoroutinefunction(handler) else handler(request)

            # === 处理响应 ===
            if response is None or response == "":
                # 自动渲染模板
                auto_template = (path.strip("/") or "index") + ".html"
                auto_path = os.path.join(self.template_folder, auto_template)
                if os.path.exists(auto_path):
                    with open(auto_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    headers = self._build_headers_with_session(request, "text/html")
                    content_bytes = content.encode("utf-8")
                    headers.append((b"content-length", str(len(content_bytes)).encode()))
                    await send({
                        "type": "http.response.start",
                        "status": 200,
                        "headers": headers,
                    })
                    await send({
                        "type": "http.response.body",
                        "body": content_bytes,
                    })
                    return
                else:
                    await send_response(send, 404, "Template not found")
                    return

            # === 处理返回值 ===
            if isinstance(response, str):
                # 返回字符串
                content_bytes = response.encode("utf-8")
                headers = self._build_headers_with_session(request, "text/html")
                headers.append((b"content-length", str(len(content_bytes)).encode()))
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": headers,
                })
                await send({
                    "type": "http.response.body",
                    "body": content_bytes,
                })

            elif isinstance(response, dict):
                # 返回字典 → JSON
                content = json.dumps(response, ensure_ascii=False)
                headers = self._build_headers_with_session(request, "application/json")
                content_bytes = content.encode("utf-8")
                headers.append((b"content-length", str(len(content_bytes)).encode()))
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": headers,
                })
                await send({
                    "type": "http.response.body",
                    "body": content_bytes,
                })

            elif isinstance(response, tuple):
                # 返回 (str, int) 或 (dict, int)
                if len(response) == 2:
                    content, status = response
                    if isinstance(content, str):
                        content_bytes = content.encode("utf-8")
                        headers = self._build_headers_with_session(request, "text/html")
                        headers.append((b"content-length", str(len(content_bytes)).encode()))
                        await send({
                            "type": "http.response.start",
                            "status": status,
                            "headers": headers,
                        })
                        await send({
                            "type": "http.response.body",
                            "body": content_bytes,
                        })
                    elif isinstance(content, dict):
                        content = json.dumps(content, ensure_ascii=False)
                        headers = self._build_headers_with_session(request, "application/json")
                        content_bytes = content.encode("utf-8")
                        headers.append((b"content-length", str(len(content_bytes)).encode()))
                        await send({
                            "type": "http.response.start",
                            "status": status,
                            "headers": headers,
                        })
                        await send({
                            "type": "http.response.body",
                            "body": content_bytes,
                        })
                    else:
                        # 如果 content 不是 str 或 dict，返回 500
                        await send_response(send, 500, "Invalid response type")
                else:
                    # tuple 长度不为 2，返回 500
                    await send_response(send, 500, "Invalid response tuple length")

            else:
                # 其他类型，如 Response 对象
                await send_response(send, 200, str(response), "text/html")

        except Exception as e:
            # 打印错误堆栈
            print("\n" + "="*60)
            print("❌ INTERNAL SERVER ERROR")
            print(f"Path: {path}")
            print(f"Method: {method}")
            traceback.print_exc()
            print("="*60 + "\n")

            # 检查 errorhandler
            error_handler = self.errorhandler_funcs.get(type(e), self.errorhandler_funcs.get(Exception))
            if error_handler:
                try:
                    result = error_handler(e)
                    if isinstance(result, str):
                        await send_response(send, 500, result)
                    elif isinstance(result, dict):
                        await send_json(send, result, 500)
                    elif isinstance(result, int):
                        await send_response(send, result, "text/html")
                    else:
                        await send_response(send, 500, "Internal Server Error")
                except Exception as e2:
                    print(f"Error in errorhandler: {e2}")
                    await send_response(send, 500, "Internal Server Error")
            else:
                await send_response(send, 500, f"<h1>500 Internal Server Error</h1><pre>{str(e)}</pre>")

        # 执行 after_request
        for func in self.after_request_funcs:
            try:
                result = func()
                if result is not None:
                    # 处理返回值
                    pass
            except Exception as e:
                print(f"After request error: {e}")

    def run(self, host="127.0.0.1", port=8000):
        try:
            import uvicorn
        except ImportError:
            raise ImportError("Uvicorn is required. Install with: pip install uvicorn")
        uvicorn.run(self, host=host, port=port, log_level="info")

# ======================
# 全局变量（Flask 风格）
# ======================
app = None
request = None
session = None

def create_app(*args, **kwargs) -> MicroPy:
    global app
    app = MicroPy(*args, **kwargs)
    return app

print("This project was initiated by a junior high school student and subsequently maintained throughout high school.")
print("If you have any questions, please email sbox520@163.com")