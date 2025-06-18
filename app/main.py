import os

from flask import Flask
from waitress import serve
from . import create_app
from .routes import routes

app = create_app()
app.register_blueprint(routes)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 4567))
    #app.run(debug=True, host="0.0.0.0", port=port)
    serve(app, host='0.0.0.0', port=port)
    print(f"Server is running on port {port}")
