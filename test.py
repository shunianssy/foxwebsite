from foxwebsite import create_app

app = create_app()

@app.route("/")
def home(request):
    count = request.session.get("count", 0) + 1
    request.session["count"] = count
    return f"<h1>You visited {count} times!</h1>"

@app.route("/clear")
def clear_session(request):
    app.clear_session(request)
    return "<h1>Session cleared. Refresh to start over.</h1>"

@app.route("/user/{name}")
def user_profile(request):
    name = request.params["name"]
    return f"<h1>Hello, {name}!</h1>"

@app.route("/about")
def about(request):
    return app.render_template("about.html")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)