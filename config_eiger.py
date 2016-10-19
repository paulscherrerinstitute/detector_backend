"""
mpirun -n 4 mpi-dafld --config-file config_mpi.py
"""


import sys
new_path = '/home/l_det/code/dafl.psieiger'
if new_path not in sys.path:
    sys.path.append(new_path)


import logging
c = get_config()  # @UndefinedVariable



from mpi4py import MPI
comm = MPI.COMM_WORLD

# rank (size - 1)  runs the rest gateway, rank (size -2) runs the bulletin board - ignore both and decrease size by two
mpi_rank = comm.Get_rank()
mpi_size = comm.Get_size()

rank = mpi_rank
size = mpi_size - 2

RECEIVER_RANKS = [0, 1, 2, 3]
SENDERS_RANKS = []

print(rank, size)
#supported_mpi_sizes = [3, ]
#if mpi_size not in supported_mpi_sizes:
#    raise ValueError("mpi size (number of mpi processes) must be in %s" % supported_mpi_sizes)

c.BulletinBoardClient.prefix = u'backend'
c.BulletinBoardClient.postfix = str(rank)
#c.DataFlow.maxelements = 42
c.DataFlow.log_level = 'INFO'

c.ModuleReceiver.geometry = (1, 1)  # number of modules, x and y 
c.ModuleReceiver.bit_depth = 16
c.ZMQSender.bit_depth = 16

n_modules = c.ModuleReceiver.geometry[0] * c.ModuleReceiver.geometry[1]
receiver_ips = 2 * ["10.0.30.200"] + 2 * ["10.0.40.200"]
receiver_ports = [50001, 50002, 50004, 50003] #[50001 + i for i in range(4 * n_modules)]
submodule_index = n_modules * [0, 1, 2, 3]

# Ring Buffers settings
rb_writers_id = range(len(RECEIVER_RANKS))
#rb_followers_id = SENDERS_RANKS
rb_followers_id = []
rb_fdir = "/dev/shm/eiger/"
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
    c.ModuleReceiver.rb_id = rb_writers_id[rank]
    c.ModuleReceiver.rb_followers = rb_followers_id
    c.ModuleReceiver.rb_head_file = rb_head_file
    c.ModuleReceiver.rb_imghead_file = rb_imghead_file
    c.ModuleReceiver.rb_imgdata_file = rb_imgdata_file    

elif rank in SENDERS_RANKS:
    c.DataFlow.nodelist = [
        ('ZMQ', 'module_zmq.ZMQSender'),
    ]
    c.DataFlow.targets_per_node = { 'ZMQ' : []}
    c.ZMQSender.uri = "tcp://10.0.30.200:9999"
    c.ZMQSender.socket_type = "PUB"
    c.ZMQSender.rb_id = rank
    c.ZMQSender.ModuleReceiver.rb_followers = rb_writers_id
    c.ZMQSender.rb_head_file = rb_head_file
    c.ZMQSender.rb_imghead_file = rb_imghead_file
    c.ZMQSender.rb_imgdata_file = rb_imgdata_file    

    

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
