"""Argos backend application entry point."""

from flask import Flask

from feeds.articles import blueprint as articles_blueprint
from feeds.database import initialize
from feeds.routes import blueprint as fetch_blueprint
from rag.routes import blueprint as rag_blueprint
from system.configuration import blueprint as configuration_blueprint
from system.health import blueprint as health_blueprint


def create_app() -> Flask:
    application = Flask(__name__)
    for blueprint in (
        health_blueprint,
        configuration_blueprint,
        articles_blueprint,
        fetch_blueprint,
        rag_blueprint,
    ):
        application.register_blueprint(blueprint)
    return application


app = create_app()


if __name__ == "__main__":
    initialize()
    app.run(host="0.0.0.0", port=8000, debug=False)
