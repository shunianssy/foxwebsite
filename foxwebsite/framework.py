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

try:
    import jinja2
    JINJA_AVAILABLE = True
except ImportError:
    JINJA_AVAILABLE = False

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
        """Flask 风格：request.session.clear() 并自动清除 cookie"""
        if hasattr(self, "session") and isinstance(self.session, dict):
            self.session.clear()
        # 通知框架发送删除 cookie 的 header
        if not hasattr(self, "_response_headers"):
            self._response_headers = []
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
        os.makedirs(template_folder, exist_ok=True)

        # 路由系统：支持静态和动态
        self.routes: List[Tuple[re.Pattern, str, Callable]] = []
        self.route_map: Dict[str, str] = {}  # 用于 url_for

        # Jinja2 支持
        if JINJA_AVAILABLE:
            self.jinja_env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(template_folder),
                autoescape=True
            )
        else:
            self.jinja_env = None

    def route(self, path: str, methods=("GET",)):
        # 转换 {name} 为正则
        pattern_str = "^" + re.escape(path) + "$"
        pattern_str = re.sub(r"\\{([^}/]+)\\}", r"(?P<\1>[^/]+)", pattern_str)
        pattern = re.compile(pattern_str)

        def decorator(handler: Callable):
            for method in methods:
                self.routes.append((pattern, method.upper(), handler))
                # 注册到 url_for 映射
                self.route_map[f"{method.upper()}:{path}"] = path
            return handler
        return decorator

    def get(self, path: str):
        return self.route(path, methods=["GET"])

    def post(self, path: str):
        return self.route(path, methods=["POST"])

    # ======================
    # 反向路由：url_for
    # ======================
    def url_for(self, endpoint: str, **values) -> str:
        """endpoint: 'GET:/user/{name}'"""
        if endpoint in self.route_map:
            path = self.route_map[endpoint]
            for k, v in values.items():
                path = re.sub(rf"{{\s*{k}\s*}}", str(v), path)
            return path
        return "/"

    # ======================
    # 模板渲染（Jinja2 优先）
    # ======================
    def render_template(self, filename: str, **context) -> str:
        filepath = os.path.join(self.template_folder, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Template {filename} not found.")

        if self.jinja_env:
            template = self.jinja_env.get_template(filename)
            return template.render(**context)
        else:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            template = Template(content)
            return template.substitute(**context)

    # ======================
    # 构建带 Session Cookie 的响应头
    # ======================
    def _build_headers_with_session(self, request, content_type: str = "text/html") -> List[Tuple[bytes, bytes]]:
        headers = [
            (b"content-type", content_type.encode()),
        ]

        # 如果有自定义响应头（比如 clear_session 设置的），合并进来
        if hasattr(request, "_response_headers"):
            headers.extend(request._response_headers)

        # 如果 session 非空，设置新 cookie
        if hasattr(request, "session") and isinstance(request.session, dict) and request.session:
            session_data = serialize_session(request.session, self.secret_key)
            cookie_header = f"{self.session_cookie_name}={session_data}; Path=/; HttpOnly"
            headers.append((b"set-cookie", cookie_header.encode()))

        return headers

    def clear_session(self, request):
        """清空 session 并设置删除 cookie 的响应头"""
        request.session.clear()  # 清空内存中的 session
        # 设置一个已过期的 cookie，让浏览器删除它
        cookie_header = f"{self.session_cookie_name}=deleted; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly"
        # 保存到 request，以便在响应时发送
        if not hasattr(request, "_response_headers"):
            request._response_headers = []
        request._response_headers.append((b"set-cookie", cookie_header.encode()))


    # ======================
    # ASGI 协议入口
    # ======================
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

        try:
            # 调用 handler —— 必须接收 request 参数
            response = await handler(request) if asyncio.iscoroutinefunction(handler) else handler(request)

            # === 自动模板返回 ===
            if response is None or response == "":
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

            # === 处理响应并自动附加 Session Cookie ===
            if isinstance(response, dict):
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
            elif isinstance(response, str):
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
            else:
                content = str(response)
                content_bytes = content.encode("utf-8")
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

        except Exception as e:
            # 打印完整错误堆栈到控制台
            print("\n" + "="*60)
            print("❌ INTERNAL SERVER ERROR")
            print(f"Path: {path}")
            print(f"Method: {method}")
            traceback.print_exc()
            print("="*60 + "\n")
            # 返回错误页面
            await send_response(send, 500, f"<h1>500 Internal Server Error</h1><pre>{str(e)}</pre>")


    def run(self, host="127.0.0.1", port=8000):
        try:
            import uvicorn
        except ImportError:
            raise ImportError("Uvicorn is required. Install with: pip install uvicorn")
        uvicorn.run(self, host=host, port=port, log_level="info")


# ======================
# 全局变量（Flask 风格）—— 注意：这里只是占位，实际全局 request/session 需在 __init__.py 用 contextvars 实现
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