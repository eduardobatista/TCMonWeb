import os
from pathlib import Path
from flask import Flask
import json

from main.driverhardware import driverhardware

def create_app(debug=False):

    filedir= Path(os.path.realpath(__file__)).parent
    # print(filedir)
    with open(filedir / 'settings.json') as f:
        config = json.load(f)

    """Create an application."""
    app = Flask(__name__,static_url_path="/static")

    app.MAINPATH = Path(os.path.realpath(__file__)).parents[0]

    app.debug = debug

    app.driver = driverhardware()

    from main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    return app