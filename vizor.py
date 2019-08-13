import glob
import json
import os
import socket
from bokeh.application import Application
from bokeh.application.handlers import FunctionHandler
from bokeh.client import pull_session
from bokeh.embed import server_document
from bokeh.embed import server_session
from bokeh.server.server import BaseServer
from bokeh.server.tornado import BokehTornado
from bokeh.server.util import bind_sockets
from flask import Flask
from flask import abort, request
from flask import render_template
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop

from plotting import render_vizard

app = Flask(__name__, static_url_path='/static')


@app.route('/')
def dir_listing():
    BASE_DIR = app.config["BASE_DIR"]

    # Return 404 if path doesn't exist
    if not os.path.exists(BASE_DIR):
        return abort(404)

    # Show directory contents
    dirlist = []
    names = []
    descriptions = []
    searched_folders = glob.iglob(BASE_DIR + '/**/metadata.json', recursive=True)
    sorted_folder = sorted(searched_folders, key=lambda folder: os.path.getctime(folder), reverse=True)
    for experiment in sorted_folder:
        full_path = os.path.dirname(experiment)
        dirlist.append(full_path.replace(BASE_DIR, ""))
        with open(experiment, "r") as f:
            try:
                metadata = json.load(f)
            except:
                metadata = {}
            if "name" in metadata:
                names.append(metadata["name"])
            else:
                names.append("NO NAME")
            if "description" in metadata:
                descriptions.append(metadata["description"])
            else:
                descriptions.append("NO DESCRIPTION")
    return render_template('files.html', files_names_description=zip(dirlist, names, descriptions))


@app.route('/view/<path:req_path>')
def render_run(req_path):
    BASE_DIR = app.config["BASE_DIR"]
    bokehport = app.config["BOKEH_PORT"]
    # Joining the base and the requested path
    abs_path = os.path.join(BASE_DIR, req_path)

    if os.path.exists(abs_path):
        # Check if path seems to be a valid dictionary with a metadata.json
        if os.path.isfile(os.path.join(abs_path, 'metadata.json')):
            bokeh_script = server_document('http://localhost:{}/bokeh'.format(bokehport),
                                           arguments={"req_path": abs_path})
            return render_template("score.html", bokeh_div=bokeh_script)
    return dir_listing()


bkapp = Application(FunctionHandler(render_vizard))


def bk_worker(bokehsockets, flask_port):
    bokeh_tornado = BokehTornado({'/bokeh': bkapp}, extra_websocket_origins=["localhost",
                                                                             "127.0.0.1",
                                                                             "0.0.0.0",
                                                                             "*"
                                                                             ])
    bokeh_http = HTTPServer(bokeh_tornado)
    bokeh_http.add_sockets(bokehsockets)

    io_loop = IOLoop.current()
    server = BaseServer(io_loop, bokeh_tornado, bokeh_http)
    server.start()
    server.io_loop.start()


if __name__ == '__main__':
    from threading import Thread

    bokehsockets, bokehport = bind_sockets("0.0.0.0", 0)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('0.0.0.0', 0))
    flaskport = sock.getsockname()[1]
    sock.close()

    Thread(target=bk_worker, args=([bokehsockets, flaskport])).start()
    app.config["BASE_DIR"] = os.path.expanduser('~/REINVENT/')
    app.config["BOKEH_PORT"] = bokehport
    print("Running Vizor on http://localhost:{}/".format(flaskport))
    app.run(port=flaskport, debug=False)
