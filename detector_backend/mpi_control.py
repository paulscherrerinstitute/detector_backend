from mpi4py import MPI


class MpiControlClient(object):

    def __init__(self):
        self.communicator = MPI.COMM_WORLD
        self.master_process_rank = self.communicator.size - 1

        if self.communicator.rank == self.master_process_rank:
            raise ValueError("The config client cannot be instantiated on "
                             "the master process with rank %d." % self.master_process_rank)

    def is_message_ready(self):
        return self.communicator.iprobe(int_source=self.master_process_rank)

    def get_message(self):

        received_message = self.communicator.recv(int_source=self.master_process_rank)

        return received_message


class MpiControlMaster(object):

    def __init__(self):
        self.communicator = MPI.COMM_WORLD
        self.master_process_rank = self.communicator.size-1

        if self.communicator.rank != self.master_process_rank:
            raise ValueError("The config master must be instantiated on the "
                             "master process with rank %d." % self.master_process_rank)

    def send_message(self, message):
        self.communicator.bcast(message, root=self.master_process_rank)
