# 📘 foxwebsite Web フレームワーク公式ドキュメント  
> 軽量・非同期・Flask 風の Python Web フレームワーク —— 高校生が個人開発・継続メンテナンス中 ❤️  
> サポート（寄付）はこちら：[ifdian.net/a/shunian](https://www.ifdian.net/a/shunian)  
> 連絡先メール：sbox520@163.com  

---

## ✅ 1. インストールとクイックスタート  

### 依存パッケージのインストール  

```bash
pip install uvicorn
```

（任意）Jinja2 テンプレートエンジンを使用する場合（機能が豊富なため推奨）：

```bash
pip install jinja2
```

> foxwebsite には標準で `string.Template` エンジンが組み込まれており、Jinja2 をインストールしなくても基本的なテンプレート機能が利用可能です。

---

### 最初のアプリケーション作成  

`app.py` を新規作成：

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

実行コマンド：

```bash
python app.py
```

ブラウザで [http://127.0.0.1:8000](http://127.0.0.1:8000) にアクセスして動作を確認してください！

---

## 🧭 2. ルーティングシステム  

### 基本ルート  

```python
@app.route("/about")
def about(request):
    return "About Page"
```

複数の HTTP メソッドに対応：

```python
@app.route("/submit", methods=["GET", "POST"])
def submit(request):
    if request.method == "POST":
        return "Submitted!"
    return "<form method='post'><button>Submit</button></form>"
```

ショートカットデコレータ（`@app.get`, `@app.post` など）：

```python
@app.get("/info")
def get_info(request):
    return "This is GET only"

@app.post("/login")
async def login(request):  # 非同期関数もサポート
    data = await request.json()  # JSON データを非同期で読み取り
    return {"message": "Login received", "data": data}
```

パスパラメータでの型変換（例: `{id:int}`）に対応：

```python
@app.route("/post/{post_id:int}")
def view_post(request):
    post_id = request.params["post_id"]
    return f"<h3>投稿 #{post_id} を表示中</h3>"
```

---

## 📥📤 3. リクエストとレスポンス  

### リクエストオブジェクト（`request`）  

ハンドラ関数は `request` オブジェクトを受け取り、以下の属性を利用できます：

- `request.method` — HTTP メソッド（GET, POST など）  
- `request.path` — リクエストされたパス  
- `request.query` — クエリパラメータの辞書（例: `?name=Bob` → `{"name": "Bob"}`）  
- `request.params` — パスパラメータ（例: `/user/{name}` → `{"name": "Alice"}`）  
- `request.headers` — リクエストヘッダーの辞書  
- `request.body` — 生のリクエストボディ（bytes）  
- `await request.json()` — JSON ボディを非同期でパース  
- `await request.form()` — form データを非同期でパース  

例：

```python
@app.post("/api/data")
async def handle_data(request):
    json_data = await request.json()
    name = json_data.get("name")
    return {"hello": name}
```

### レスポンス  

以下の戻り値形式をサポートしています：

- `str` → HTML テキストとして返却（`Content-Type: text/html`）  
- `dict` → 自動で JSON にシリアライズ（`Content-Type: application/json`）  
- `Response` オブジェクト → ステータスコード・ヘッダー・Content-Type を細かく制御可能  

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

## 🔐 4. セッション管理  

セッション機能を使用するには、アプリ作成時に `secret_key` を指定してください：

```python
app = create_app(secret_key="your-super-secret-key-here")
```

ルート内でセッションを利用する例：

```python
@app.get("/set")
def set_session(request):
    request.session["user"] = "Alice"
    return "セッションを設定しました！"

@app.get("/get")
def get_session(request):
    user = request.session.get("user", "Guest")
    return f"Hello, {user}"
```

セッションは署名付き Cookie で実装されており、データはクライアント側に保存されます。

---

## 🎨 5. テンプレートレンダリング  

以下の2種類のテンプレートエンジンをサポート：

1. 組み込み：`string.Template`（追加インストール不要）  
2. 任意：Jinja2（条件分岐・繰り返しなど高度な機能あり）  

### 組み込みテンプレート（`string.Template`）の使用  

```python
@app.get("/hello/{name}")
def hello(request):
    name = request.params["name"]
    return app.render_string("Hello, $name!", name=name)
```

### Jinja2 テンプレートの使用  

Jinja2 をインストールし、テンプレートファイルを `templates/` ディレクトリに配置してください。

```python
@app.get("/profile/{name}")
def profile(request):
    name = request.params["name"]
    return app.render_template("profile.html", name=name, age=16)
```

`templates/profile.html` の例：

```html
<h1>Hello, {{ name }}!</h1>
<p>You are {{ age }} years old.</p>
```

---

## 🖼️ 6. 静的ファイルの配信  

`static/` ディレクトリ内のファイル（CSS・JS・画像など）を自動で配信します。

例：

- ファイルパス：`static/style.css`  
- アクセスURL：`http://localhost:8000/static/style.css`  

`static_dir` 引数で静的ファイルディレクトリをカスタマイズ可能：

```python
app = create_app(secret_key="...", static_dir="public")
```

---

## ❌ 7. エラーハンドリング  

`@app.errorhandler` デコレータでエラーハンドラを登録できます：

```python
@app.errorhandler(404)
def not_found(request):
    return "<h1>ページが見つかりません 😢</h1>", 404

@app.errorhandler(500)
def server_error(request):
    return "<h1>サーバーエラー 🛠️</h1>", 500
```

独自例外のハンドリングも可能：

```python
class UnauthorizedError(Exception):
    pass

@app.errorhandler(UnauthorizedError)
def handle_unauthorized(request, exception):
    return "アクセスが拒否されました！", 401
```

---

## 🚀 8. デプロイと実行  

開発中は組み込みの `app.run()` を使用：

```python
app.run(host="127.0.0.1", port=8000)
```

本番環境では、ASGI サーバー（例：Uvicorn）経由で実行することを推奨：

```bash
uvicorn app:app
```

Gunicorn + Uvicorn によるマルチプロセスデプロイもサポート：

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app
```

---

## ❓ 9. よくある質問（FAQ）  

**Q：foxwebsite は同期・非同期のどちらですか？**  
A：**完全非同期**（`async`/`await` ベース）で設計されており、同期関数と非同期関数を混在して記述できます。

**Q：WSGI に対応していますか？**  
A：いいえ。foxwebsite は **ASGI フレームワーク** のため、Uvicorn・Hypercorn などの ASGI サーバーが必要です。

**Q：データベース接続は可能ですか？**  
A：はい！非同期 ORM / ドライバ（例：`aiomysql`, `asyncpg`, `Tortoise ORM`）との組み合わせを推奨します。

**Q：テンプレートに Jinja2 は必須ですか？**  
A：いいえ。シンプルな用途には組み込みの `string.Template` で十分です。Jinja2 は複雑なロジックや再利用性の高いテンプレート向けです。

**Q：テストはどうすればよいですか？**  
A：現時点では `requests` や `httpx` を使って HTTP リクエストを送信する方法が一般的です。将来的には専用のテストクライアントを提供する予定です。

---

> 🌱 成長中のフレームワークです。Issue や Pull Request によるご協力を、心より歓迎いたします！  
> GitHub：[https://github.com/shunianssy/foxwebsite](https://github.com/shunianssy/foxwebsite)
