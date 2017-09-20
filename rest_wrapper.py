from bottle import route, request, Bottle, run
import requests
import json
from collections import Counter

import logging
log = logging.getLogger('bottle')
log.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
#formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')


class Config(object):
    writer_name = "writer"
    proxy_name = "writer_proxy"
    writer_url = "http://xbl-daq-28:41000/api/v1/" + writer_name
    backend_url = "http://localhost:8080/v1"
    writer_status = "DOWN"
    backend_status = "DOWN"
    status = "DOWN"

    
global _config
_config = Config()

rest_server = Bottle()

writer_statuses = {False: "CONFIGURED", True: "OPEN", None: "CONFIGURED"}
writer_cfg_params = ["output_file", ]
backend_cfg_params = ["bit_depth", "period", "n_frames"]


def interpret_status(backend, writer):
    logger.debug("Raw statuses: backend %s writer %s" % (backend, writer))
    if writer == "CONFIGURED":
        if backend != "OPEN":
            return backend
        else:
            return writer
    else:
        return backend


@rest_server.route('/api/v1/state', method="GET")
def state():
    logger.debug({"status": "ok", "state": get_status()})
    return {"status": "ok", "state": get_status()}

    
def get_status():
    global _config
    backend_status = json.loads(requests.get(_config.backend_url + "/state").text)["global_state"]
    writer_status = requests.get(_config.writer_url + "/status").text
    logger.debug("Writer got %s %s" % (writer_status, json.loads(writer_status)["data"]["is_running"]))
    writer_status = writer_statuses[json.loads(writer_status)["data"]["is_running"]]
    logger.debug("Writer status %s" % writer_status)
    #print({"status": interpret_status(backend_status, writer_status),
    #        "details": {"backend": backend_status, "writer": writer_status}})
    return {"status": interpret_status(backend_status, writer_status),
            "details": {"backend": backend_status, "writer": writer_status}}


@rest_server.route('/api/v1/configure', method="POST")
def configure():
    cfg = json.loads(request.body.read())
    writer_cfg = {}
    backend_cfg = {"settings": {}}
    logger.debug("Configuration: %s" % cfg)
    for k, v in cfg["settings"].items():
        if k in writer_cfg_params:
            writer_cfg[k] = v
        if k in backend_cfg_params:
            backend_cfg["settings"][k] = v
    logger.debug("Configurations for backend and writer: %s %s" % (backend_cfg, writer_cfg))

    if "output_file" in writer_cfg:
        if writer_cfg["output_file"][-3:] != ".h5":
            writer_cfg["output_file"] += ".h5"
            
    r = requests.post(_config.backend_url + "/state/configure", json=backend_cfg).text
    logger.debug("Backend cfg got %s" % r)
    if r != "CONFIGURED":
        logger.error("Cannot setup backend parameters, aborting: %s" % r)
        return {"state": _config.status, "message": r}

    r = json.loads(requests.post(_config.writer_url + "/parameters", json=writer_cfg).text)
    logger.debug("Writer cfg got %s" % r)
    if r["status"] != "ok":
        logger.error("Cannot setup writer parameters, aborting: %s" % r)
        return {"state": _config.status, "message": r["message"]}

    return {"status": "ok", "state": get_status()}


@rest_server.route('/api/v1/open', method="POST")
def open():
    status = get_status()
    if status["status"] != "CONFIGURED":
        return {"state": "error", "message": "Cannot open in state %s" % status["status"]}
    r = requests.post(_config.backend_url + "/state/open", json={}).text
    logger.debug("Opening backend got %s" % r)
    if r != "OPEN":
        logger.error("Cannot setart backend, aborting: %s" % r)
        return {"status": "error", "message": r["message"], "state": get_status()}
    
    r = requests.put(_config.writer_url + "/").text
    if json.loads(r)["status"] != "ok":
        logger.error("Cannot start writer, aborting: %s" % r)
        return {"status": "error", "message": r, "state": get_status()}
    logger.debug("Opening writer got %s" % r)
    return {"status": "ok", "state": get_status()}


@rest_server.route('/api/v1/close', method="POST")
def close():
    status = get_status()
    if status["status"] != "OPEN":
        return {"state": "error", "message": "Cannot close in state %s" % status["status"]}
    r = requests.post(_config.backend_url + "/state/close", json={}).text
    logger.debug("Stopping backend got %s" % r)
    if r != "CLOSED" and r != "CLOSING":
        logger.error("Cannot stop backend, aborting: %s" % r)
        return {"status": "error", "message": r, "state": get_status()}
    
    r = requests.delete(_config.writer_url + "/").text
    if json.loads(r)["status"] != "ok":
        logger.error("Cannot stop writer, aborting: %s" % r)
        return {"status": "error", "message": r["message"], "state": get_status()}
    logger.debug("Stoppping writer got %s" % r)
    return {"status": "ok", "state": get_status()}


@rest_server.route('/api/v1/reset', method="POST")
def reset():
    status = get_status()
    if status["status"] != "CLOSED":
        return {"state": "error", "message": "Cannot reset in state %s" % status["status"]}
    r = requests.post(_config.backend_url + "/state/reset", json={}).text
    logger.debug("Stopping backend got %s" % r)
    if r != "INITIALIZED":
        logger.error("Cannot stop backend, aborting: %s" % r)
        return {"status": "error", "message": r, "state": get_status()}
    
    return {"status": "ok", "state": get_status()}


@rest_server.route('/api/v1/configure_rest', method="POST")
def setup_rest_server():
    global _config
    data = json.loads(request.body.read())
    config.writer_url = data['settings']["writer_url"]
    config.backend_url = data['settings']["backend_url"]

    return _config.status


if __name__ == "__main__":
    run(rest_server, host='127.0.0.1', port=8000, debug=True)
