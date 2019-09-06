from mpi4py import MPI

from detector_backend.module.h5_writer import start_h5_writer
from detector_backend.module.rest_api import start_rest_api
from detector_backend.module.udp_receiver import start_udp_receiver
from detector_backend.mpi_control import MpiControlClient, MpiControlMaster
from detector_backend.mpi_ringbuffer import MpiRingBufferClient, MpiRingBufferMaster


def receive_and_write(detector_definition, udp_ip_and_port):
    current_process_rank = MPI.COMM_WORLD.rank
    total_processes = MPI.COMM_WORLD.size

    receiver_ranks = list(range(detector_definition.n_submodules_total))
    if len(receiver_ranks) != len(udp_ip_and_port):
        raise ValueError("Got %d n_submodule_total from the detector_definition but %d udp_ip_and_port values." %
                         (len(receiver_ranks), len(udp_ip_and_port)))

    writer_rank = receiver_ranks[-1] + 1
    rest_rank = writer_rank + 1

    # total processes = total receivers + sender + preview + rest api
    total_expected_processes = len(receiver_ranks) + 2

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
                               follower_ids=[writer_rank],
                               detector_def=detector_definition,
                               as_reader=False
                           ),
                           control_client=MpiControlClient()
                           )

    elif current_process_rank == writer_rank:

        start_h5_writer(name="H5 writer",
                        detector_def=detector_definition,
                        ringbuffer=MpiRingBufferClient(
                            process_id=current_process_rank,
                            follower_ids=receiver_ranks,
                            detector_def=detector_definition,
                        ))

    else:
        raise ValueError("Process with rank %d is not assigned to any module." % current_process_rank)
