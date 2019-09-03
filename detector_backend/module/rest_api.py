import json
from logging import getLogger

import bottle

ENDPOINT_RESET = "/reset"

_logger = getLogger("rest_api")


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
        _logger.info("Starting rest API on rest_host=%s, rest_port=%s." % (rest_host,rest_port))
        bottle.run(app=app, host=rest_host, port=rest_port)
    except KeyboardInterrupt:
        pass
    except:
        _logger.exception("Rest Api terminated with exception.")
