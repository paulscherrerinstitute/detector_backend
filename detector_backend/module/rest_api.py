import json
from logging import getLogger

import bottle

ENDPOINT_RESET = "/reset"

_logger = getLogger(__name__)


def register_rest_interface(app, manager):

    @app.post(ENDPOINT_RESET)
    def reset():
        manager.reset()

        return {"state": "ok",
                "status": "Backend reset completed."}

    @app.error(500)
    def error_handler_500(error):
        bottle.response.content_type = 'application/json'
        bottle.response.status = 200

        error_text = str(error.exception)

        _logger.error(error_text)

        return json.dumps({"state": "error",
                           "status": error_text})


class Manager(object):
    def __init__(self, ringbuffer, control_master):
        self.ringbuffer = ringbuffer
        self.control_master = control_master

    def reset(self):
        self.control_master.send_message(1)
        self.ringbuffer.reset_header()


def start_rest_api(rest_host, rest_port, ringbuffer, control_master):
    manager = Manager(ringbuffer, control_master)

    ringbuffer.create_buffer()

    app = bottle.Bottle()
    register_rest_interface(app, manager)

    try:
        _logger.info("Starting rest API on port %s." % rest_port)
        bottle.run(app=app, host=rest_host, port=rest_port)
    finally:
        pass
