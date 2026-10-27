"""
Servidor central da Sala Segura.

Roda com:  python app.py        (ou flask --app app run --host 0.0.0.0)
Painel:    http://<ip>:5000/
API:       http://<ip>:5000/api/...
"""
from flask import Flask, redirect, url_for

import config
import db
from api import bp_api
from web import bp_web


def create_app():
    app = Flask(__name__)
    app.config.from_object(config)

    db.init_app(app)
    app.register_blueprint(bp_api)
    app.register_blueprint(bp_web)

    @app.route("/")
    def index():
        return redirect(url_for("web.monitoramento"))

    return app


app = create_app()

if __name__ == "__main__":
    # host 0.0.0.0 para a Raspberry enxergar o servidor na rede local
    app.run(host="0.0.0.0", port=5000, debug=True)
