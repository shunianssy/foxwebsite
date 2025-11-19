#[简体中文](https://github.com/shunianssy/foxwebsite/blob/main/README-Zn.md)
# 📘 foxwebsite Web Framework Official Documentation  
> A lightweight, asynchronous, Flask-style Python web framework — independently developed and maintained by a high school student ❤️  
> Support me on: [ifdian.net/a/shunian](https://www.ifdian.net/a/shunian)  
> Contact: sbox520@163.com  

---

## ✅ 1. Installation & Quick Start  

### Install Dependencies  

```bash
pip install uvicorn
```

*(Optional)* To use the Jinja2 template engine (recommended for richer templating):

```bash
pip install jinja2
```

> foxwebsite includes a built-in `string.Template` engine, so basic templating works even without installing Jinja2.

---

### Create Your First Application  

Create `app.py`:

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

Run it:

```bash
python app.py
```

Visit http://127.0.0.1:8000 to see the result!

---

## 🧭 2. Routing System  

### Basic Routes  

```python
@app.route("/about")
def about(request):
    return "About Page"
```

Support for multiple HTTP methods:

```python
@app.route("/submit", methods=["GET", "POST"])
def submit(request):
    if request.method == "POST":
        return "Submitted!"
    return "<form method='post'><button>Submit</button></form>"
```

Shortcut decorators (`@app.get`, `@app.post`, etc.):

```python
@app.get("/info")
def get_info(request):
    return "This is GET only"

@app.post("/login")
async def login(request):  # async functions supported
    data = await request.json()  # parse JSON asynchronously
    return {"message": "Login received", "data": data}
```

Path parameters with type conversion (e.g., `{id:int}`):

```python
@app.route("/post/{post_id:int}")
def view_post(request):
    post_id = request.params["post_id"]
    return f"<h3>Viewing post #{post_id}</h3>"
```

---

## 📥📤 3. Request & Response  

### Request Object  

Each handler receives a `request` object with the following attributes:

- `request.method` — HTTP method (e.g., GET, POST)  
- `request.path` — requested URL path  
- `request.query` — parsed query string (e.g., `?name=Bob` → `{"name": "Bob"}`)  
- `request.params` — path parameters (e.g., `/user/{name}` → `{"name": "Alice"}`)  
- `request.headers` — request headers as a dictionary  
- `request.body` — raw request body (bytes)  
- `await request.json()` — parse JSON request body asynchronously  
- `await request.form()` — parse form-encoded data asynchronously  

Example:

```python
@app.post("/api/data")
async def handle_data(request):
    json_data = await request.json()
    name = json_data.get("name")
    return {"hello": name}
```

### Response  

Multiple return types are supported:

- `str` → returned as HTML text (`text/html`)  
- `dict` → auto-serialized to JSON (`application/json`)  
- `Response` object → full control over status, headers, and content type  

```python
from foxwebsite import Response

@app.get("/custom")
def custom_response(request):
    return Response(
        body="<h1>Custom!</h1>",
        status=201,
        headers={"X-Frame-Options": "DENY"},
        content_type="text/html"
    )
```

---

## 🔐 4. Session Management  

Enable sessions by providing a `secret_key` during app creation:

```python
app = create_app(secret_key="your-super-secret-key-here")
```

Use sessions in route handlers:

```python
@app.get("/set")
def set_session(request):
    request.session["user"] = "Alice"
    return "Session set!"

@app.get("/get")
def get_session(request):
    user = request.session.get("user", "Guest")
    return f"Hello, {user}"
```

Sessions are cookie-based and signed; all session data is stored on the client side.

---

## 🎨 5. Template Rendering  

Two template engines supported:

1. Built-in: `string.Template` (zero dependencies)  
2. Optional: Jinja2 (richer syntax and logic)

### Using Built-in Template (`string.Template`)  

```python
@app.get("/hello/{name}")
def hello(request):
    name = request.params["name"]
    return app.render_string("Hello, $name!", name=name)
```

### Using Jinja2 Templates  

Ensure Jinja2 is installed and templates reside in the `templates/` directory.

```python
@app.get("/profile/{name}")
def profile(request):
    name = request.params["name"]
    return app.render_template("profile.html", name=name, age=16)
```

Example `templates/profile.html`:

```html
<h1>Hello, {{ name }}!</h1>
<p>You are {{ age }} years old.</p>
```

---

## 🖼️ 6. Static Files  

Files under `static/` are served automatically (CSS, JS, images, etc.).

Example:

- File: `static/style.css`  
- URL: `http://localhost:8000/static/style.css`  

Customize static directory via `static_dir`:

```python
app = create_app(secret_key="...", static_dir="public")
```

---

## ❌ 7. Error Handling  

Register error handlers with `@app.errorhandler`:

```python
@app.errorhandler(404)
def not_found(request):
    return "<h1>Page Not Found 😢</h1>", 404

@app.errorhandler(500)
def server_error(request):
    return "<h1>Server Error 🛠️</h1>", 500
```

Custom exceptions are also supported:

```python
class UnauthorizedError(Exception):
    pass

@app.errorhandler(UnauthorizedError)
def handle_unauthorized(request, exception):
    return "Access denied!", 401
```

---

## 🚀 8. Deployment  

For development, use the built-in `app.run()`:

```python
app.run(host="127.0.0.1", port=8000)
```

For production, run as an ASGI app with Uvicorn:

```bash
uvicorn app:app
```

Multi-process deployment with Gunicorn + Uvicorn:

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app
```

---

## ❓ 9. Frequently Asked Questions  

**Q: Is foxwebsite synchronous or asynchronous?**  
A: Fully asynchronous (based on `async`/`await`). Route handlers may be sync or async.

**Q: Is it WSGI-compatible?**  
A: No. foxwebsite is an ASGI framework and requires ASGI servers like Uvicorn or Hypercorn.

**Q: Can I connect to a database?**  
A: Yes! Recommended async libraries: `aiomysql`, `asyncpg`, or `Tortoise ORM`.

**Q: Do I have to use Jinja2 for templates?**  
A: No. The built-in `string.Template` suffices for simple use cases; Jinja2 is for complex rendering.

**Q: How do I test my app?**  
A: You can use `requests` or `httpx` to send test HTTP requests. A test client is planned for future releases.

---

> 🌱 A growing framework — contributions, issues, and PRs are warmly welcome!  
> GitHub: [https://github.com/shunianssy/foxwebsite](https://github.com/shunianssy/foxwebsite)
