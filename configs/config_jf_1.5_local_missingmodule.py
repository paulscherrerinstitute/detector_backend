"""
mpirun -n 6 mpi-dafld --config-file config_jf_1.5_testbed.py
"""


import sys
new_path = "../nodes"
if new_path not in sys.path:
    sys.path.append(new_path)


import logging
c = get_config()  # @UndefinedVariable



rb_fdir = "/dev/shm/rb/"
#rb_fdir = "/mnt/north/"
rb_head_file = rb_fdir + "rb_header.dat"
rb_imghead_file = rb_fdir + "rb_image_header.dat"
rb_imgdata_file = rb_fdir + "rb_image_data.dat"

from mpi4py import MPI
comm = MPI.COMM_WORLD

# rank (size - 1)  runs the rest gateway, rank (size -2) runs the bulletin board - ignore both and decrease size by two
mpi_rank = comm.Get_rank()
mpi_size = comm.Get_size()

rank = mpi_rank
size = mpi_size - 2

geometry = [1, 3]
module_size = [512, 1024]
n_modules = geometry[0] * geometry[1]
n_modules = geometry[0] * geometry[1]
#gap_chips = [2, 2]
#gap_modules = [36, 8]
gap_chips = [0, 0]
gap_modules = [0, 0]
#module_size_wgaps = [module_size[0] + gap_chips[0], module_size[1] + gap_chips[1] + 4]
module_size_wgaps = [module_size[0], module_size[1]]
detector_size = [(geometry[0] - 1) * gap_modules[0] + module_size_wgaps[0] * geometry[0], 
                (geometry[1] - 1) * gap_modules[1] + module_size_wgaps[1] * geometry[1]]
#detector_size = [(GEOMETRY[0] - 1) * gap_modules[0] + detector_size[0],
#                 (GEOMETRY[1] - 1) * gap_modules[1] + detector_size[1]]

c.ModuleReceiver.geometry = geometry  # number of modules, x and y
c.ModuleReceiver.module_size = module_size
c.ModuleReceiver.detector_size = detector_size
c.ZMQSender.module_size = module_size
c.ZMQSender.detector_size = detector_size

IGNORED_MODULES = [2,]

RECEIVER_RANKS = [i for i in range(n_modules)]
FOLLOWERS = [i for i in range(n_modules)]
SENDERS_RANKS = [RECEIVER_RANKS[-1] + 1, ]
#ip = 3 * ["10.30.10.3", ]
ip = n_modules * ["127.0.0.1", ]
port = [10001 + i for i in range(n_modules)]

for mod in IGNORED_MODULES:
    FOLLOWERS.remove(mod)

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
    c.ModuleReceiver.ip = ip[rank]
    c.ModuleReceiver.port = port[rank]

    c.ModuleReceiver.rb_id = rank
    #if rank != 2:
    c.ModuleReceiver.rb_followers = SENDERS_RANKS
    c.ModuleReceiver.rb_head_file = rb_head_file
    c.ModuleReceiver.rb_imghead_file = rb_imghead_file
    c.ModuleReceiver.rb_imgdata_file = rb_imgdata_file
    c.ModuleReceiver.geometry = geometry
    c.ModuleReceiver.module_size = module_size
    c.ModuleReceiver.module_index = rank # FIXME
    c.ModuleReceiver.detector_name = "JUNGFRAU"

elif rank in SENDERS_RANKS:
    c.DataFlow.nodelist = [
        ('ZMQ', 'module_zmq.ZMQSender'),
    ]
    c.DataFlow.targets_per_node = { 'ZMQ' : []}
    c.ZMQSender.uri = "tcp://127.0.0.1:40000"
    c.ZMQSender.socket_type = "PUSH"

    c.ZMQSender.rb_id = rank
    c.ZMQSender.rb_followers = FOLLOWERS
    print("FOLLOWERS rank %d:" % rank, FOLLOWERS)
    c.ZMQSender.rb_head_file = rb_head_file
    c.ZMQSender.rb_imghead_file = rb_imghead_file
    c.ZMQSender.rb_imgdata_file = rb_imgdata_file
    c.ZMQSender.geometry = geometry
    c.ZMQSender.module_size = module_size


#c.DataFlow.maxitterations = 20

#c.aliases = dict(maxitterations='DataFlow.maxitterations',
#                 start='NumberGenerator.start',
#                 stop='NumberGenerator.stop')

c.RestGWApplication.rest_port = 8081
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
                       'ModuleReceiver': info,
                       'ZMQSender': info
                   }
)

c.XblBaseApplication.log_config = log_config

# =============================================================================================


