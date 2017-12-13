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

    def send_request(self, method, url, json_cfg={}):
        print(self.url + url)
        if method not in ["POST", "GET"]:
            logger.error("Only supported methods are POST, GET")
            return None
        try:
            if method == "GET":
                self.request = requests.get(self.url + url)
            elif method == "POST":
                self.request = requests.post(self.url + url, json=json_cfg)
            if self.request.status_code != 200:
                logger.error("Error in getting %s: %s" %(self.url + url, self.request.reason))
                try:
                    t  = json.loads(self.request.text)
                    if "error" in t:
                        print(t['error'])
                    else:
                        print(t[t.find("<pre>Trace"):t.find("</body>")])
                except:
                    logger.error(self.request.text)
                return None
        except requests.ConnectionError:
            logger.error(sys.exc_info()[1])
            return None
        return self.request

    @staticmethod
    def return_response(response):
        if response is None:
            return response
        return response.content
        
    @property
    def state(self, ):
        content = self.send_request("GET", "/state")
        logger.info(content)
        if content is None:
            return

        content = content.json()
        self.individual_state = content['individual_state']
        return content["global_state"]

    def initialize(self, cfg={}):
        response = self.send_request("POST", '/state/initialize', json_cfg=cfg)
        return self.return_response(response)

    def configure(self, cfg={}):
        response = self.send_request("POST", '/state/configure', json_cfg=cfg)
        return self.return_response(response)
    
    def open(self, cfg={}):
        response = self.send_request("POST", '/state/open', json_cfg=cfg)
        return self.return_response(response)

    def close(self, cfg={}):
        response = self.send_request("POST", '/state/close', json_cfg=cfg)
        return self.return_response(response)

    def reset(self, cfg={}):
        response = self.send_request("POST", '/state/reset', json_cfg=cfg)
        return self.return_response(response)

    def get_metrics(self, *args):
        """
        Input: strings, identifying the metrics name
        Output: dict 
        """
        print(args)
        answer = json.loads(self.send_request("GET", "/metrics").content)["value"]["backend"]
        if args:
            ret = {k: answer.get(k, None) for k in args}
        else:
            ret = answer
        return ret
