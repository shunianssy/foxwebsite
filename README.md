- 快速入门
- 路由系统
- 请求与响应
- Session 会话
- 模板渲染
- 静态文件
- 错误处理
- 部署运行
- 常见问题

---

# 📘 foxwebsite Web 框架官方文档  
> 一个轻量级、异步、Flask 风格的 Python Web 框架 —— 由中学生独立开发并持续维护 ❤️  
> 项目邮箱：sbox520@163.com

---

## ✅ 1. 安装与快速启动

### 安装依赖

```bash
pip install uvicorn
```

（可选）如需使用 Jinja2 模板引擎：

```bash
pip install jinja2
```

> foxwebsite 自带 `string.Template` 引擎，不装 Jinja2 也能用基础模板功能。

---

### 创建第一个应用

新建 `app.py`：

```python
from foxwebsite import create_app

app = create_app(secret_key="your-secret-here")

@app.route("/")
def home(request):
    return "<h1>Hello, foxwebsite!</h1>"

@app.route("/user/{name}")
def user_profile(request):
    name = request.params["name"]
    return f"<h2>Welcome, {name}!</h2>"

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
```

运行：

```bash
python app.py
```

访问 http://127.0.0.1:8000 看效果！

---

## 🧭 2. 路由系统

### 基础路由

```python
@app.route("/about")
def about(request):
    return "About Page"
```

支持多个方法：

```python
@app.route("/submit", methods=["GET", "POST"])
def submit(request):
    if request.method == "POST":
        return "Submitted!"
    return "<form method='post'><button>Submit</button></form>"
```

快捷装饰器：

```python
@app.get("/info")
def get_info(request):
    return "This is GET only"

@app.post("/login")
async def login(request):  # 支持 async 函数
    data = await request.json()
    return {"status": "ok", "user": data.get("username")}
```

---

### 动态路由参数

使用 `{参数名}` 占位：

```python
@app.route("/article/{id}")
def article(request):
    article_id = request.params["id"]  # ← 从路径提取
    return f"Article ID: {article_id}"
```

访问 `/article/123` → `request.params = {"id": "123"}`

> 注意：目前只支持单层路径参数，不支持正则自定义（如 `\d+`），但你可以手动在函数内校验类型。

---

### 反向路由：`url_for`

注册时自动记录路由，可用 `url_for` 生成 URL：

```python
@app.route("/user/{name}", methods=["GET"])
def profile(request):
    ...

# 在其他 handler 中：
redirect_url = app.url_for("GET:/user/{name}", name="Alice")
# 返回 "/user/Alice"
```

⚠️ 注意：endpoint 格式是 `"METHOD:path"`，区分大小写！

---

## 📥 3. 请求对象 `Request`

每个 handler 接收一个 `request` 参数，包含：

| 属性/方法           | 说明 |
|---------------------|------|
| `request.method`    | HTTP 方法（GET/POST...） |
| `request.path`      | 请求路径 |
| `request.query_params` | 查询参数字典（如 `?a=1&b=2`） |
| `request.cookies`   | Cookie 字典 |
| `await request.body()` | 原始请求体（bytes） |
| `await request.json()` | 解析 JSON 请求体（返回 dict） |
| `request.params`    | 动态路由参数（如 `{name}`） |

示例：

```python
@app.route("/search")
def search(request):
    q = request.query_params.get("q", [""])[0]  # query_params 是列表值
    return f"You searched: {q}"

@app.post("/api/data")
async def api_data(request):
    data = await request.json()
    return {"received": data}
```

---

## 🍪 4. 会话管理（Session）

foxwebsite 自动处理带签名的安全 Session。

### 读写 Session

```python
@app.route("/login", methods=["POST"])
async def login(request):
    data = await request.json()
    # 登录成功，保存到 session
    request.session["user_id"] = 123
    request.session["username"] = data["username"]
    return {"message": "Login success"}

@app.route("/me")
def me(request):
    username = request.session.get("username", "Guest")
    return f"Hello, {username}!"

@app.route("/logout")
def logout(request):
    # 清空 session 并删除 cookie
    request.clear_session()  # ← 推荐用法
    return "Logged out"
```

> 所有对 `request.session` 的修改，在响应时会自动序列化 + 签名 + 设置 Cookie。

---

### Session 安全机制

- 使用 HMAC-SHA256 签名，防止篡改。
- Cookie 名默认为 `micropy_session`，可通过 `app.session_cookie_name` 修改。
- 必须设置 `secret_key`，否则签名无意义！

```python
app = create_app(secret_key="your-very-long-random-secret-string!")
```

> 生产环境请勿使用默认 `"dev-secret"`！

---

## 🖼️ 5. 模板渲染

默认模板目录：`./templates`

### 基础用法

创建 `templates/index.html`：

```html
<!DOCTYPE html>
<html>
<head><title>Welcome</title></head>
<body>
  <h1>Hello, $name!</h1>
</body>
</html>
```

在 handler 中渲染：

```python
@app.route("/")
def home(request):
    return app.render_template("index.html", name="Alice")
```

> 默认使用 Python 内置 `string.Template`，语法简单：`$变量名` 或 `${变量名}`

---

### 使用 Jinja2（推荐）

安装后自动启用：

```bash
pip install jinja2
```

模板语法更强大：

```html
<!-- templates/profile.html -->
<h1>Welcome, {{ username }}!</h1>
{% if age >= 18 %}
  <p>成年人</p>
{% else %}
  <p>未成年人</p>
{% endif %}
```

Python 代码无需改动：

```python
return app.render_template("profile.html", username="Bob", age=17)
```

---

### 自动模板功能（懒人福利✨）

如果 handler **没有返回值**（或返回空字符串），框架会自动查找模板：

```python
@app.route("/about")
def about(request):
    pass  # 不返回任何内容
```

→ 框架自动寻找 `templates/about.html`

→ 如果访问 `/`，则找 `templates/index.html`

非常适合纯静态页面！

---

## 📁 6. 静态文件服务

默认静态文件路径前缀：`/static`

放置你的 CSS/JS/图片到项目根目录下的 `./static` 文件夹：

```
your-project/
├── static/
│   ├── style.css
│   └── logo.png
├── templates/
└── app.py
```

访问：

- `http://localhost:8000/static/style.css`
- `http://localhost:8000/static/logo.png`

框架自动根据扩展名设置正确的 `Content-Type`。

---

## ❌ 7. 错误处理

### 自动 500 页面

程序出错时，控制台会打印完整 traceback，浏览器显示：

```html
<h1>500 Internal Server Error</h1>
<pre>错误信息...</pre>
```

方便调试！

---

### 自定义 404

未匹配路由时，默认返回：

```html
<h1>404 The route does not exist.</h1>
```

你也可以注册一个万能兜底路由：

```python
@app.route("/{path:path}")  # ← 注意：此功能当前未实现，需手动加到最后
def not_found(request):
    return "Custom 404 page", 404
```

> ⚠️ 当前版本不支持 `{path:path}` 通配符，你可以把“兜底路由”放在所有路由最后手动匹配。

---

## 🚀 8. 运行与部署

### 开发运行

```python
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
```

启动后访问 http://127.0.0.1:8000

---

### 生产部署（使用 Uvicorn）

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

> `app:app` 表示 `app.py` 文件中的 `app` 对象。

建议配合 Nginx + Supervisor 使用。

---

## ❓ 9. 常见问题（FAQ）

### Q1: 为什么不能像 Flask 一样直接用 `from micropy import request, session`？

A: 因为 foxwebsite 是异步并发框架，全局变量会被多个请求互相覆盖。我们计划在下一版通过 `contextvars` 实现上下文安全的全局代理。目前请直接使用 handler 的 `request` 参数。

---

### Q2: 如何设置自定义状态码或响应头？

A: 目前版本暂不支持直接返回元组 `(content, status_code)`，但你可以：

```python
# 临时方案：手动 send
async def my_handler(request):
    await send_json(request.scope['send'], {"error": "Not Found"}, 404)
    return  # 必须 return 阻止后续处理
```

或等待未来版本支持 `Response` 类。

---

### Q3: Session 存储在哪里？支持 Redis 吗？

A: 当前 Session 存储在客户端 Cookie 中（加密签名），无服务器存储。优点：无状态、易扩展；缺点：容量有限（约 4KB）、不适合存敏感数据。未来可插件化支持服务端存储（如 Redis）。

---

### Q4: 支持 WebSocket 或上传文件吗？

A: 当前版本专注 HTTP。WebSocket 和 multipart/form-data 文件上传是未来重要功能，欢迎提交需求或 PR！

---

## 📬 10. 联系与贡献

本项目由一名初中生发起，高中持续维护。欢迎交流、提问、贡献代码！

📧 邮箱：sbox520@163.com  
🌟 如果你喜欢这个项目，请告诉你的朋友，或在 GitHub 上点亮星星！

---

## 🛠️ 附录：项目结构建议

```
my-micropy-app/
├── app.py                  # 主程序
├── templates/              # HTML 模板
│   ├── index.html
│   └── user.html
├── static/                 # 静态资源
│   ├── style.css
│   └── script.js
└── requirements.txt        # 依赖
```

`requirements.txt` 示例：

```
uvicorn
jinja2  # 可选
```

---

—— 致敬每一位热爱代码的少年

--- 