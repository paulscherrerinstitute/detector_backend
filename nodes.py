'''
Created on Feb 21, 2014

@author: billich
'''
from dafl.application import XblLoggingConfigurable
from dafl.traits import Int, Unicode
from dafl.dataflow import DataFlowNode, DataFlow

import time


class NumberGenerator(DataFlowNode):
    delay = Int(1, config=True, reconfig=True)
    start   = Int(1, config=True, reconfig=True)
    stop   = Int(10, config=True, reconfig=True)
    increment = Int(1, config=True, reconfig=True)

    def __init__(self, **kwargs):
        super(NumberGenerator, self).__init__(**kwargs)
        self.log.debug('__init__() start=%i stop=%i increment=%i', self.start, self.stop, self.increment)
        self.next_value = self.start

    def send(self, data):
        if self.next_value < self.stop:
            self.log.debug('pass_on(%i)', self.next_value)
            self.metrics.incr('NumberGenerator.values_send')
            self.pass_on(self.next_value)
            self.next_value += self.increment
        else:
            self.log.debug('StopIteration')
            raise StopIteration
        time.sleep(self.delay)
        return(1)

    def reset(self):
        self.log.debug("%s.reset()",self.__class__.__name__)
        super(NumberGenerator, self).reset()
        self.next_value = self.start

    def reconfigure(self, new):
        super(NumberGenerator, self).reconfigure(new)
        self.next_value = self.start

class NumberWriter(DataFlowNode):

    filename = Unicode(u'data.txt', config=True, reconfig=True, help='output filename with optional path')

    def __init__(self, **kwargs):
        super(NumberWriter, self).__init__(**kwargs)

    def send(self,data):
        self.log.debug("send() got %s" % (data))
        self.pass_on(data)

    def reset(self):
        pass

if __name__ == '__main__':
    pass
