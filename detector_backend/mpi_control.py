import logging

from mpi4py import MPI

_logger_master = logging.getLogger("mpi_control_master")
_logger_client = logging.getLogger("mpi_control_client")


class MpiControlClient(object):

    def __init__(self):
        self.communicator = MPI.COMM_WORLD
        self.master_process_rank = self.communicator.size - 1

        if self.communicator.rank == self.master_process_rank:
            raise ValueError("The config client cannot be instantiated on "
                             "the master process with rank %d." % self.master_process_rank)

    def is_message_ready(self):
        return self.communicator.iprobe(source=self.master_process_rank)

    def get_message(self):
        _logger_client.debug("[%d] Receiving message from master_process_rank=%d.",
                             self.communicator.rank, self.master_process_rank)
        received_message = self.communicator.recv(source=self.master_process_rank)

        return received_message


class MpiControlMaster(object):

    def __init__(self):
        self.communicator = MPI.COMM_WORLD
        self.master_process_rank = self.communicator.size-1
        # Master process rank is the last rank. All other all clients.
        self.client_ranks = list(range(self.master_process_rank))

        _logger_master.info("Starting control master with master_process_rank=%d and client_ranks=%s",
                            self.master_process_rank, self.client_ranks)

        if self.communicator.rank != self.master_process_rank:
            raise ValueError("The config master must be instantiated on the "
                             "master process with rank %d." % self.master_process_rank)

    def send_message(self, message):

        _logger_master.info("Sending %s to all clients.", message)

        requests = []

        for client_rank in self.client_ranks:
            requests.append(self.communicator.issend(message, dest=client_rank))

        _logger_master.debug("Waiting for clients to receive message.")

        MPI.Request.Waitall(requests)

        _logger_master.info("All clients received message.")
