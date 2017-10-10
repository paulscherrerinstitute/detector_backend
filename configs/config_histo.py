c = get_config()  # @UndefinedVariable

import logging
import nodes


c.DataFlow.maxelements = 42
c.DataFlow.log_level = 'DEBUG'
c.DataFlow.nodelist = [
    ('SOURCE', 'nodes.NumberGenerator'),
    ('SINK1', 'nodes.NumberWriter'),
    ('SINK2', 'nodes.NumberWriter'),
#    ('FSINK', 'dafl.examples.nodes.NumberMerger')
]

c.DataFlow.targets_per_node = {'SOURCE': ['SINK1', 'SINK2'],
#                               'SINK1': ['FSINK',],
#                               'SINK2': ['FSINK',],
#                               'FSINK': []
}
#c.DataFlow.targets_per_node = {'SOURCE': ['SINK'], }
c.DataFlow.maxitterations = 20

c.RPCDataflowApplication.initialize_dataflow_on_startup = True

#c.RPCBulletinBoardApplication.rpc_connection_class = u'dafl.rpc.ZMQRPCConnection'
#c.RPCBulletinBoardApplication.pipe_connection_class = u'dafl.rpc.ZMQRPCConnection'
#c.RPCBulletinBoardApplication.rpc_connection_class = u'dafl.connection.DevNullSendingConnection'
#c.RPCBulletinBoardApplication.pipe_connection_class = u'dafl.connection.DummyConnection'
#c.BulletinBoardClient.connection_class = u'dafl.rpc.ZMQRPCConnection'



#c.RestGWApplication.trace_rest = True
c.XblBaseApplication.log_level = logging.DEBUG
#c.RPCBulletinBoardApplication.log_level = logging.DEBUG

c.aliases = dict(maxitterations='DataFlow.maxitterations',
                 start='NumberGenerator.start',
                 stop='NumberGenerator.stop')


