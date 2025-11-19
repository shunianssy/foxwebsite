以下是 **foxwebsite Web 框架官方文件** 的 **繁體中文版本**（純繁體，無簡體或英文對照，保留原始結構與技術術語準確性）：

---

# 📘 foxwebsite Web 框架官方文件  
> 一個輕量級、非同步、Flask 風格的 Python Web 框架 —— 由一名中學生獨立開發並持續維護 ❤️  
> 歡迎贊助我：[ifdian.net/a/shunian](https://www.ifdian.net/a/shunian)  
> 專案聯絡信箱：sbox520@163.com  

---

## ✅ 1. 安裝與快速啟動  

### 安裝依賴  

```bash
pip install uvicorn
```

（可選）若需使用 Jinja2 範本引擎（雖為可選，但仍推薦使用）：

```bash
pip install jinja2
```

> foxwebsite 內建支援 `string.Template` 引擎，即使未安裝 Jinja2，仍可使用基礎範本功能。

---

### 建立第一個應用程式  

建立 `app.py`：

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

執行：

```bash
python app.py
```

開啟瀏覽器訪問 http://127.0.0.1:8000 查看效果！

---

## 🧭 2. 路由系統  

### 基礎路由  

```python
@app.route("/about")
def about(request):
    return "About Page"
```

支援多種 HTTP 方法：

```python
@app.route("/submit", methods=["GET", "POST"])
def submit(request):
    if request.method == "POST":
        return "Submitted!"
    return "<form method='post'><button>Submit</button></form>"
```

快捷裝飾器（`@app.get`, `@app.post` 等）：

```python
@app.get("/info")
def get_info(request):
    return "This is GET only"

@app.post("/login")
async def login(request):  # 支援非同步函式
    data = await request.json()  # 非同步解析 JSON 資料
    return {"message": "Login received", "data": data}
```

路徑參數支援型別轉換（如 `{id:int}`）：

```python
@app.route("/post/{post_id:int}")
def view_post(request):
    post_id = request.params["post_id"]
    return f"<h3>正在檢視文章 #{post_id}</h3>"
```

---

## 📥📤 3. 請求與回應  

### 請求物件（Request）  

每個路由處理函式皆接收一個 `request` 物件，包含以下屬性：

- `request.method` — HTTP 方法（GET、POST 等）  
- `request.path` — 請求路徑  
- `request.query` — 查詢參數字典（如 `?name=Bob` → `{"name": "Bob"}`）  
- `request.params` — 路徑參數（如 `/user/{name}` → `{"name": "Alice"}`）  
- `request.headers` — 請求標頭字典  
- `request.body` — 原始請求主體（bytes）  
- `await request.json()` — 非同步解析 JSON 主體  
- `await request.form()` — 非同步解析表單資料  

範例：

```python
@app.post("/api/data")
async def handle_data(request):
    json_data = await request.json()
    name = json_data.get("name")
    return {"hello": name}
```

### 回應（Response）  

支援多種回傳型別：

- 字串 → 以 HTML 文字回傳（`text/html`）  
- 字典 → 自動序列化為 JSON（`application/json`）  
- `Response` 物件 → 可自訂狀態碼、標頭、內容類型等  

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

## 🔐 4. Session 會話管理  

啟用 Session 需於建立應用時傳入 `secret_key`：

```python
app = create_app(secret_key="your-super-secret-key-here")
```

於路由中使用 session：

```python
@app.get("/set")
def set_session(request):
    request.session["user"] = "Alice"
    return "Session 已設定！"

@app.get("/get")
def get_session(request):
    user = request.session.get("user", "Guest")
    return f"Hello, {user}"
```

Session 以簽章 Cookie 實作，資料儲存於用戶端。

---

## 🎨 5. 範本渲染  

支援兩種範本引擎：

1. 內建：`string.Template`（無需額外依賴）  
2. 可選：Jinja2（功能更強大，支援條件判斷、迴圈等）  

### 使用內建範本（`string.Template`）  

```python
@app.get("/hello/{name}")
def hello(request):
    name = request.params["name"]
    return app.render_string("Hello, $name!", name=name)
```

### 使用 Jinja2 範本  

請先安裝 Jinja2，並將範本檔案置於 `templates/` 目錄下。

```python
@app.get("/profile/{name}")
def profile(request):
    name = request.params["name"]
    return app.render_template("profile.html", name=name, age=16)
```

`templates/profile.html` 範例：

```html
<h1>Hello, {{ name }}!</h1>
<p>You are {{ age }} years old.</p>
```

---

## 🖼️ 6. 靜態檔案  

自動提供 `static/` 目錄下的檔案（如 CSS、JavaScript、圖片等）。

例如：

- 檔案路徑：`static/style.css`  
- 可透過 URL 存取：`http://localhost:8000/static/style.css`  

可透過 `static_dir` 參數自訂靜態目錄：

```python
app = create_app(secret_key="...", static_dir="public")
```

---

## ❌ 7. 錯誤處理  

使用 `@app.errorhandler` 註冊錯誤處理器：

```python
@app.errorhandler(404)
def not_found(request):
    return "<h1>頁面未找到 😢</h1>", 404

@app.errorhandler(500)
def server_error(request):
    return "<h1>伺服器錯誤 🛠️</h1>", 500
```

亦支援自訂例外處理：

```python
class UnauthorizedError(Exception):
    pass

@app.errorhandler(UnauthorizedError)
def handle_unauthorized(request, exception):
    return "存取遭拒！", 401
```

---

## 🚀 8. 部署與執行  

開發階段可使用內建 `app.run()`：

```python
app.run(host="127.0.0.1", port=8000)
```

生產環境建議使用 Uvicorn 執行 ASGI 應用：

```bash
uvicorn app:app
```

支援 Gunicorn + Uvicorn 多行程部署：

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app
```

---

## ❓ 9. 常見問題  

**Q：foxwebsite 是同步還是非同步框架？**  
A：完全非同步（基於 `async`/`await`），同時支援同步與非同步路由函式混合撰寫。

**Q：是否相容 WSGI？**  
A：不相容。foxwebsite 為 ASGI 框架，需搭配 Uvicorn、Hypercorn 等 ASGI 伺服器使用。

**Q：能否連接資料庫？**  
A：可以！推薦搭配非同步資料庫套件，如 `aiomysql`、`asyncpg` 或 `Tortoise ORM`。

**Q：範本是否必須使用 Jinja2？**  
A：非必需。內建 `string.Template` 已足夠應付簡單需求；Jinja2 適用於需邏輯控制的複雜頁面。

**Q：如何進行測試？**  
A：目前可使用 `requests` 或 `httpx` 發送測試請求；未來版本將提供專用測試客戶端。

---

> 🌱 這是一個持續成長中的框架，歡迎提交 Issue 或 Pull Request！  
> GitHub：[https://github.com/shunianssy/foxwebsite](https://github.com/shunianssy/foxwebsite)
