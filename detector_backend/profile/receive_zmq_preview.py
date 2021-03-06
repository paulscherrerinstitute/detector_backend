from mpi4py import MPI

from detector_backend.module.rest_api import start_rest_api
from detector_backend.module.udp_receiver import start_udp_receiver
from detector_backend.module.zmq_sender import start_writer_sender, start_preview_sender
from detector_backend.mpi_control import MpiControlMaster, MpiControlClient
from detector_backend.mpi_ringbuffer import MpiRingBufferMaster, MpiRingBufferClient


def receive_zmq_preview(detector_definition, udp_ip_and_port):
    current_process_rank = MPI.COMM_WORLD.rank
    total_processes = MPI.COMM_WORLD.size

    receiver_ranks = list(range(detector_definition.n_submodules_total))
    if len(receiver_ranks) != len(udp_ip_and_port):
        raise ValueError("Got %d n_submodule_total from the detector_definition but %d udp_ip_and_port values." %
                         (len(receiver_ranks), len(udp_ip_and_port)))

    sender_rank = receiver_ranks[-1] + 1
    preview_rank = sender_rank + 1
    rest_rank = preview_rank + 1

    # total processes = total receivers + sender + preview + rest api
    total_expected_processes = len(receiver_ranks) + 3

    if total_processes != total_expected_processes:
        raise ValueError("Expected %d total processes, but got %d. "
                         "Use 'mpiexec -n %d -m mpi4py [start_script]' call." % (total_expected_processes,
                                                                                 total_processes,
                                                                                 total_expected_processes))

    # The last rank is always the REST api.
    if current_process_rank == rest_rank:
        start_rest_api(rest_host="0.0.0.0", rest_port=8080,
                       ringbuffer=MpiRingBufferMaster(),
                       control_master=MpiControlMaster())

    elif current_process_rank in receiver_ranks:

        start_udp_receiver(udp_ip=udp_ip_and_port[current_process_rank][0],
                           udp_port=udp_ip_and_port[current_process_rank][1],
                           detector_def=detector_definition,
                           submodule_index=current_process_rank,
                           ringbuffer=MpiRingBufferClient(
                               process_id=current_process_rank,
                               follower_ids=[sender_rank, preview_rank],
                               detector_def=detector_definition,
                               as_reader=False
                           ),
                           control_client=MpiControlClient()
                           )

    elif current_process_rank == sender_rank:

        start_writer_sender(name="Writer Sender",
                            bind_url="tcp://127.0.0.1:40000",
                            zmq_mode="PUSH",
                            detector_def=detector_definition,
                            ringbuffer=MpiRingBufferClient(
                                process_id=current_process_rank,
                                follower_ids=receiver_ranks,
                                detector_def=detector_definition,
                            ))

    elif current_process_rank == preview_rank:

        start_preview_sender(name="Preview Sender",
                             bind_url="tcp://127.0.0.1:50000",
                             zmq_mode="PUB",
                             detector_def=detector_definition,
                             ringbuffer=MpiRingBufferClient(
                                 process_id=current_process_rank,
                                 follower_ids=receiver_ranks,
                                 detector_def=detector_definition,
                             ))

    else:
        raise ValueError("Process with rank %d is not assigned to any module." % current_process_rank)
