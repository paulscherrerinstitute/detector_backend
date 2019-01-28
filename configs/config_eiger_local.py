"""
# single module
mpirun -n 7 mpi-dafld --config-file config_eiger.py

# 1.5
mpirun -n 15 mpi-dafld --config-file config_eiger.py
"""


import sys
#new_path = '/home/l_det/Work/dafl.psieiger/nodes'
new_path = '../nodes'
new_path
if new_path not in sys.path:
    sys.path.append(new_path)


import logging
c = get_config()  # @UndefinedVariable


import mpi4py

from mpi4py import MPI

#mpi4py.profile(logfile="test")
comm = MPI.COMM_WORLD

# rank (size - 1)  runs the rest gateway, rank (size -2) runs the bulletin board - ignore both and decrease size by two
mpi_rank = comm.Get_rank()
mpi_size = comm.Get_size()

rank = mpi_rank
size = mpi_size - 2

GEOMETRY = [6, 3]
#c.ModuleReceiver.geometry = GEOMETRY  # number of modules, x and y
module_size = [512, 1024]
gap_chips = [2, 2]
gap_modules = [36, 8]
#gap_chips = [0, 0]
#gap_modules = [0, 0]
module_size_wgaps = [module_size[0] + gap_chips[0], module_size[1] + gap_chips[1] + 4]
#module_size_wgaps = [module_size[0], module_size[1]]
detector_size = [module_size_wgaps[0] * GEOMETRY[0], module_size_wgaps[1] * GEOMETRY[1]]
detector_size = [(GEOMETRY[0] - 1) * gap_modules[0] + detector_size[0],
                 (GEOMETRY[1] - 1) * gap_modules[1] + detector_size[1]]

c.ModuleReceiver.geometry = GEOMETRY  # number of modules, x and y
c.ModuleReceiver.module_size = module_size
c.ModuleReceiver.detector_size = detector_size
c.ZMQSender.module_size = module_size
c.ZMQSender.detector_size = detector_size
c.ZMQSender.geometry = GEOMETRY  # number of modules, x and y

#c.ModuleReceiver.bit_depth = 16
#c.ZMQSender.bit_depth = 16
#c.ZMQSender.detector_size = [module_size[0] * GEOMETRY[0], module_size[1] * GEOMETRY[1]]


RECEIVER_RANKS = [x for x in range(4 * c.ModuleReceiver.geometry[0] * c.ModuleReceiver.geometry[1])]  # [0, 1, 2, 3]
SENDERS_RANKS = [RECEIVER_RANKS[-1] +  1, ]


n_modules = c.ModuleReceiver.geometry[0] * c.ModuleReceiver.geometry[1]
receiver_ips = 4 * ["127.0.0.1"]
receiver_ips = n_modules * receiver_ips
# submodule numeration differs from the one in the setup file
receiver_ports = [50011 + i for i in range(4)]
# receiver_ports[2:] = receiver_ports[:1:-1]
for m in range(1, n_modules):
    receiver_ports += [i + m * 4 for i in receiver_ports[:4]]
submodule_index = n_modules * [0, 1, 2, 3]

# Ring Buffers settings
rb_writers_id = range(len(RECEIVER_RANKS))
#rb_followers_id = []
rb_fdir = "/dev/shm/rb/"
rb_head_file = rb_fdir + "rb_header.dat"
rb_imghead_file = rb_fdir + "rb_image_header.dat"
rb_imgdata_file = rb_fdir + "rb_image_data.dat"

c.ModuleReceiver.create_and_delete_ringbuffer_header = False

if rank in RECEIVER_RANKS:
    c.DataFlow.nodelist = [
        ('RECV', 'module_receiver_rb.ModuleReceiver'),
    ]
    if rank == 0:
        c.ModuleReceiver.create_and_delete_ringbuffer_header = True

    c.DataFlow.targets_per_node = { 'RECV' : []}
    c.ModuleReceiver.ip = receiver_ips[rank]
    c.ModuleReceiver.port = receiver_ports[rank]
    c.ModuleReceiver.submodule_index = submodule_index[rank]
    c.ModuleReceiver.module_index = int(rank / 4)
    c.ModuleReceiver.rb_id = rb_writers_id[rank]
    c.ModuleReceiver.rb_followers = SENDERS_RANKS
    c.ModuleReceiver.rb_head_file = rb_head_file
    c.ModuleReceiver.rb_imghead_file = rb_imghead_file
    c.ModuleReceiver.rb_imgdata_file = rb_imgdata_file
    c.ModuleReceiver.detector_name = "EIGER"
    c.ModuleReceiver.timeout = 0.5

    
elif rank in SENDERS_RANKS:
    c.DataFlow.nodelist = [
        ('ZMQ', 'module_zmq.ZMQSender'),
    ]
    c.DataFlow.targets_per_node = { 'ZMQ' : []}
    c.ZMQSender.uri = "tcp://127.0.0.1:40000"
    c.ZMQSender.socket_type = "PUSH"
    c.ZMQSender.rb_id = rank
    c.ZMQSender.rb_followers = rb_writers_id
    c.ZMQSender.rb_head_file = rb_head_file
    c.ZMQSender.rb_imghead_file = rb_imghead_file
    c.ZMQSender.rb_imgdata_file = rb_imgdata_file

    
c.BulletinBoardClient.prefix = u'backend'
c.BulletinBoardClient.postfix = str(rank)
#c.DataFlow.maxelements = 42
c.DataFlow.log_level = 'INFO'

c.RestGWApplication.rest_port = 8080
c.RestGWApplication.rest_host = u'0.0.0.0'   # pass u'0.0.0.0' to listen on all interfaces
c.RestGWApplication.trace_rest = True
c.RPCBulletinBoardApplication.trace_metrics = True
c.RPCDataflowApplication.initialize_dataflow_on_startup = True
# =============================================================================================
debug = dict(level='DEBUG')
info  = dict(level='INFO')
undef = dict(level=0)

log_config = dict( loggers =
                   {
                       'RestGWApplication' :           undef,
                       'RPCDataflowApplication' :      undef,
                       'DataFlow' :                    undef,
                       'ZMQSender':                    debug,
                       'ModuleReceiver':                 debug,
                   }
)

#c.XblBaseApplication.log_level = logging.DEBUG
c.XblBaseApplication.log_config = log_config

# =============================================================================================