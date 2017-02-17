from bottle import route, run, request, Bottle
import zmq
#from zmq_utils_python import zmq_writer
from multiprocessing import Process, Pipe
import os
import argparse
import requests
from dafl_client import DaflClient
import json


class State(object):
    state = "NEW"
    writer = None
    backend = None
    writer_state = None
    backend_state = None


global state
state = State()

states = {
    "NEW": 0, 
    "INITIALIZED": 1,
    "CONFIGURED": 2,
    "OPEN": 3,
    "CLOSED": 4
}


rest_server = Bottle()


class RestProxy(object):

    def __init__(self, ip, port, backend_url, writer_url):
        self.writer_url = writer_url
        self.backend_url = backend_url
        self._app = Bottle()
        self._route()
        self._host = ip
        self._port = port
        self.backend_client = DaflClient(url=backend_url)
        self.writer_client = DaflClient(url=writer_url)
        self.writer_state = None
        self.backend_state = None

    def _route(self):
        self._app.route("/state", method="GET", callback=self.get_state)

    def start(self):
        self._app.run(host=self._host, port=self._port)
    
    def get_state(self):
        r = self.writer_client.send_request("GET", "/status")
        if r is None:
            return json.loads("{'message': 'error'}")
        if r.json()["data"]["is_running"]:
            self.writer_state = "OPEN"
        else:
            self.writer_state = "CONFIGURED"
        return json.loads('{"writer_state": "%s", "backend_state": "%s"}' % (self.writer_state, self.backend_state))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--writer', '-w', type=str,
                        help='Writer REST url')
    parser.add_argument('--backend', '-b', type=str,
                        help='DAQ backend REST url')
    parser.add_argument('--url', '-u', type=str,
                        help='REST server url')

    args = parser.parse_args()

    ip, port = args.url.replace("http://", "").split(":")
    rest_proxy = RestProxy(ip, port, args.backend, args.writer)
    rest_proxy.start()

