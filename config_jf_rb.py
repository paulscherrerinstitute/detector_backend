"""
mpirun -n 4 mpi-dafld --config-file config_jf_rb.py
"""


import sys
#new_path = '/home/l_det/code/dafl.jungfrau'
new_path = "/home/sala/Work/GIT/psi/HPDI/dafl.jungfrau"
if new_path not in sys.path:
    sys.path.append(new_path)


import logging
c = get_config()  # @UndefinedVariable


geometry = [3, 1]
module_size = [512, 1024]

rb_fdir = "/dev/shm/eiger/"
rb_head_file = rb_fdir + "rb_header.dat"
rb_imghead_file = rb_fdir + "rb_image_header.dat"
rb_imgdata_file = rb_fdir + "rb_image_data.dat"

c.RestGWApplication.rest_port = 8081
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
                     'ModuleReceiver': debug,
                    'ZMQSender': debug
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

RECEIVER_RANKS = [0, 1, 2]
SENDERS_RANKS = [3, ]
port = [9000, 9001, 9002]

#supported_mpi_sizes = [3, ]
#if mpi_size not in supported_mpi_sizes:
#    raise ValueError("mpi size (number of mpi processes) must be in %s" % supported_mpi_sizes)

c.BulletinBoardClient.prefix = u'backend'
c.BulletinBoardClient.postfix = str(rank)
#c.DataFlow.maxelements = 42
c.DataFlow.log_level = 'INFO'

if rank in RECEIVER_RANKS:
    if rank == 0:
        c.ModuleReceiver.create_and_delete_ringbuffer_header = True

    c.DataFlow.nodelist = [
        ('RECV', 'module_receiver_rb.ModuleReceiver'),
    ]
    c.DataFlow.targets_per_node = { 'RECV' : []}

    #c.ModuleReceiver.ip = "192.168.10.10"
    c.ModuleReceiver.ip = "127.0.0.1"
    c.ModuleReceiver.port = port[rank]

    c.ModuleReceiver.rb_id = rank
    c.ModuleReceiver.rb_followers = SENDERS_RANKS
    c.ModuleReceiver.rb_head_file = rb_head_file
    c.ModuleReceiver.rb_imghead_file = rb_imghead_file
    c.ModuleReceiver.rb_imgdata_file = rb_imgdata_file
    c.ModuleReceiver.geometry = geometry
    c.ModuleReceiver.module_size = module_size
    c.ModuleReceiver.module_index = rank # FIXME

elif rank in SENDERS_RANKS:
    c.DataFlow.nodelist = [
        ('ZMQ', 'module_zmq.ZMQSender'),
    ]
    c.DataFlow.targets_per_node = { 'ZMQ' : []}
    #c.ZMQSender.uri = "tcp://192.168.10.10:9999"
    c.ZMQSender.uri = "tcp://127.0.0.1:9999"
    c.ZMQSender.socket_type = "PUSH"

    c.ZMQSender.rb_id = rank
    c.ZMQSender.rb_followers = RECEIVER_RANKS
    c.ZMQSender.rb_head_file = rb_head_file
    c.ZMQSender.rb_imghead_file = rb_imghead_file
    c.ZMQSender.rb_imgdata_file = rb_imgdata_file
    c.ZMQSender.geometry = geometry
    c.ZMQSender.module_size = module_size


#c.DataFlow.maxitterations = 20

#c.aliases = dict(maxitterations='DataFlow.maxitterations',
#                 start='NumberGenerator.start',
#                 stop='NumberGenerator.stop')


