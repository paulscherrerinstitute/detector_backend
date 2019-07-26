from mpi4py import MPI

from detector_backend.module.rest import start_rest_api
from detector_backend.get_ipports_fromcfg import get_ips_ports_fromcfg
from detector_backend.module.udp_receiver import start_udp_receiver
from detector_backend.module.zmq_sender import start_writer_sender
from detector_backend.utils_ringbuffer import RingBuffer


def start_standard_setup(detector_definition, detector_config_filename):

    current_process_rank = MPI.COMM_WORLD.rank
    total_processes = MPI.COMM_WORLD.size

    udp_ips, udp_ports = get_ips_ports_fromcfg(detector_config_filename)

    # All UDP receiving ranks, writer sender, preview sender, REST Api.
    receiver_ranks = list(range(detector_definition.n_submodules_total))
    sender_rank = receiver_ranks[-1] + 1
    preview_rank = sender_rank + 1
    rest_rank = preview_rank + 1

    # total processes = total receivers + sender + preview + rest api
    total_expected_processes = len(receiver_ranks) + 3

    if total_processes != total_expected_processes:
        raise ValueError("Expected %d total processes, but got %d. Fix mpi-run call.")

    # The last rank is always the REST api.
    if current_process_rank == rest_rank:
        start_rest_api(host="0.0.0.0", port=8080, ringbuffer=None)

    elif current_process_rank in receiver_ranks:

        start_udp_receiver(udp_ip=udp_ips[current_process_rank],
                           udp_port=udp_ports[current_process_rank],
                           detector_def=detector_definition,
                           ringbuffer=RingBuffer(
                               process_id=current_process_rank,
                               follower_ids=[sender_rank, preview_rank],
                               detector_config=detector_definition
                           ),
                           module_id=current_process_rank // 4,
                           submodule_id=current_process_rank % 4
                           )

    elif current_process_rank == sender_rank:

        start_writer_sender(name="Writer Sender",
                            bind_url="tcp://localhost:40000",
                            zmq_mode="PUSH",
                            detector_def=detector_definition,
                            ringbuffer=RingBuffer(
                                process_id=current_process_rank,
                                follower_ids=receiver_ranks,
                                detector_config=detector_definition
                            ))

    elif current_process_rank == preview_rank:
        pass
        # start_preview_sender(name="Preview Sender",
        #                      bind_url="tcp://localhost:50000",
        #                      zmq_mode="PUB",
        #                      detector_def=detector_definition,
        #                      ringbuffer=RingBuffer(
        #                          process_id=current_process_rank,
        #                          follower_ids=RECEIVER_RANKS,
        #                          detector_config=detector_definition
        #                      ))

    else:
        raise ValueError("Process with rank %d is not assigned to any module." % current_process_rank)
