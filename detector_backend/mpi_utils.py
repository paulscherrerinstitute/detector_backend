from mpi4py import MPI

from detector_backend import config


class ConfigReceiver(object):

    def __init__(self, ringbuffer):
        self.communicator = MPI.COMM_WORLD
        self.ringbuffer = ringbuffer

        if self.communicator.Get_rank() == config.REST_PROCESS_RANK:
            raise ValueError("ConfigReceiver cannot be instantiated on "
                             "process with rank == config.REST_PROCESS_RANK (%d)." % config.REST_PROCESS_RANK)

    def get_config(self):
        result = None

        self.communicator.Irecv(result, source=config.REST_PROCESS_RANK)

        if result is not None:
            self.communicator.barrier()

        return result

    def wait_for_confirmation(self):
        self.communicator.barrier()
        self.communicator.barrier()


class ConfigSender(object):

    def __init__(self, ringbuffer):
        self.communicator = MPI.COMM_WORLD
        self.ringbuffer = ringbuffer

        if self.communicator.rank != config.REST_PROCESS_RANK:
            raise ValueError("ConfigSender cannot be instantiated on "
                             "process with rank != config.REST_PROCESS_RANK (%d)." % config.REST_PROCESS_RANK)

        self.receiver_ranks = [x for x in range(1, self.communicator.size+1)]

    def send_config(self, config_to_send):

        for rank in self.receiver_ranks:
            self.communicator.Isend(config_to_send, dest=rank)

        # Wait for everyone to receive the new configuration.
        self.communicator.barrier()

        self.communicator.barrier()

