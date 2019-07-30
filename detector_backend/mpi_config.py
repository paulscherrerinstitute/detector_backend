from mpi4py import MPI


class MpiConfigClient(object):

    def __init__(self, ringbuffer):
        self.communicator = MPI.COMM_WORLD
        self.ringbuffer = ringbuffer

        master_process_rank = self.communicator.size - 1
        if self.communicator.rank == master_process_rank:
            raise ValueError("The config client cannot be instantiated on "
                             "the master process with rank %d." % master_process_rank)

    def get_config(self):
        result = None

        self.communicator.Irecv(result)

        return result


class MpiConfigMaster(object):

    def __init__(self, ringbuffer):
        self.communicator = MPI.COMM_WORLD
        self.ringbuffer = ringbuffer

        master_process_rank = self.communicator.size-1
        if self.communicator.rank == master_process_rank:
            raise ValueError("The config master must be instantiated on the "
                             "master process with rank %d." % master_process_rank)

    def send_config(self, config_to_send):
        self.communicator.Bcast(config_to_send, root=self.communicator.rank)
