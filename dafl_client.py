from __future__ import print_function, unicode_literals, division, absolute_import
import requests
import json
import logging
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')


class DaflClient(object):

    def __init__(self, url="http://localhost:8080/v1/"):
        self.url = url
        self.response = None
        self.individual_state = ''

    def send_request(self, method, url, json={}):
        if method not in ["POST", "GET"]:
            logger.error("Only supported methods are POST, GET")
            return None
        try:
            if method == "GET":
                self.request = requests.get(url)
            elif method == "POST":
                self.request = requests.post(url, json=json)
                if request.status_code != 200:
                    logger.error("Error in getting %s: %s" %(url, request.reason))
                    return None
        except requests.ConnectionError:
            logger.error(sys.exc_info()[1])
            return None
        return request

    @staticmethod
    def return_response(response):
        if response is None:
            return response
        return response.content
        
    @property
    def state(self, ):
        content = self.send_request("GET", self.url + "state")
        if content is None:
            return

        content = content.json()
        self.individual_state = content['individual_state']
        return content["global_state"]

    def initialize(self, cfg={}):
        response = self.send_request("POST", self.url + 'state/initialize', json=cfg)
        return self.return_response(response)

    def configure(self, cfg={}):
        response = self.send_request("POST", self.url + 'state/configure', json=cfg)
        return self.return_response(response)
    
    def open(self, cfg={}):
        response = self.send_request("POST", self.url + 'state/open', json=cfg)
        return self.return_response(response)

    def close(self, cfg={}):
        response = self.send_request("POST", self.url + 'state/close', json=cfg)
        return self.return_response(response)

    def reset(self, cfg={}):
        response = self.send_request("POST", self.url + 'state/reset', json=cfg)
        return self.return_response(response)
