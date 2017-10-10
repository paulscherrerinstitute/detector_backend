"""
mpirun -n 4 mpi-dafld --config-file config_mpi.py
"""


import sys
new_path = '/home/l_det/code/dafl.jungfrau'
if new_path not in sys.path:
    sys.path.append(new_path)


import logging
c = get_config()  # @UndefinedVariable


c.RestGWApplication.rest_port = 8080
c.RestGWApplication.rest_host = u'0.0.0.0'   # pass u'0.0.0.0' to listen on all interfaces
c.RestGWApplication.trace_rest = True
c.RPCBulletinBoardApplication.trace_metrics = True
c.RPCDataflowApplication.initialize_dataflow_on_startup = False
# =============================================================================================
debug = dict(level='DEBUG')
info  = dict(level='INFO')
undef = dict(level=0)

log_config = dict( loggers =
                    {
                     'RestGWApplication' :           undef,
                     'RPCDataflowApplication' :      undef,
                     #'RPCBulletinBoardApplication' : info,
                     #'MPIReceivingConnection' :      debug,
                     #'MPISendingConnection' :        debug,
                     #'MPIRPCConnection' :            debug,
                     'DataFlow' :                    undef,
                     #'NumberGenerator':              debug,
                     'NumberWriter':                 undef,
                    }
                 )

#c.XblBaseApplication.log_level = logging.DEBUG
c.XblBaseApplication.log_config = log_config

# =============================================================================================

from mpi4py import MPI
comm = MPI.COMM_WORLD

# rank (size - 1)  runs the rest gateway, rank (size -2) runs the bulletin board - ignore both and decrease size by two
mpi_rank = comm.Get_rank()
mpi_size = comm.Get_size()

rank = mpi_rank
size = mpi_size - 2

print(rank, size)
supported_mpi_sizes = [3, ]
if mpi_size not in supported_mpi_sizes:
    raise ValueError("mpi size (number of mpi processes) must be in %s" % supported_mpi_sizes)

c.BulletinBoardClient.prefix = u'backend'
c.BulletinBoardClient.postfix = str(rank)
#c.DataFlow.maxelements = 42
c.DataFlow.log_level = 'DEBUG'
c.DataFlow.nodelist = [
                           ('RECV', 'module_receiver_rb.ModuleReceiver'),
                           ('ZMQ', 'module_receiver_rb.ZMQSender')
                           ]
c.DataFlow.targets_per_node = { 'RECV' : ['ZMQ', ]}

c.ModuleReceiver.ip = "192.168.10.10"
c.ZMQSender.uri = "tcp://192.168.10.10:9999"

#c.DataFlow.maxitterations = 20

#c.aliases = dict(maxitterations='DataFlow.maxitterations',
#                 start='NumberGenerator.start',
#                 stop='NumberGenerator.stop')


