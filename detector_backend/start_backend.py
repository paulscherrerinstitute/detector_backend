from mpi4py import MPI

from detector_backend.detector.base import DetectorConfig, EIGER
from detector_backend.get_ipports_fromcfg import get_ips_ports_fromcfg
from detector_backend.module.udp_receiver import start_udp_receiver
from detector_backend.module.zmq_sender import start_writer_sender, start_preview_sender
from detector_backend.rest.server import start_rest_api
from detector_backend.utils_ringbuffer import RingBufferConfig

eiger9m = DetectorConfig(
    detector=EIGER,
    name="Eiger9M",
    geometry=[6, 3]
)

udp_ips, udp_ports = get_ips_ports_fromcfg("tmp.config")

RECEIVER_RANKS = eiger9m.get_receiver_ranks()
SENDER_RANK = RECEIVER_RANKS[-1] + 1
PREVIEW_RANK = RECEIVER_RANKS[-1] + 2

current_process_rank = MPI.COMM_WORLD.rank
total_processes = MPI.COMM_WORLD.size

# total processes = total receivers + rest api + sender + preview
total_expected_processes = len(RECEIVER_RANKS) + 3

if total_processes != total_expected_processes:
    raise ValueError("Expected %d total processes, but got %d. Fix mpi-run procedure.")

# The last rank is always the REST api.
if current_process_rank == total_processes - 1:
    start_rest_api(host="0.0.0.0", port=8080)

elif current_process_rank in RECEIVER_RANKS:

    start_udp_receiver(udp_ip=udp_ips[current_process_rank],
                       udp_port=udp_ports[current_process_rank],
                       detector_config=eiger9m,
                       ringbuffer_config=RingBufferConfig(
                           process_id=current_process_rank,
                           follower_ids=[SENDER_RANK, PREVIEW_RANK]
                       ))

elif current_process_rank == SENDER_RANK:

    start_writer_sender(bind_url="tcp://localhost:40000",
                        zmq_mode="PUSH",
                        detector_config=eiger9m,
                        ringbuffer_config=RingBufferConfig(
                            process_id=current_process_rank,
                            follower_ids=RECEIVER_RANKS
                        ))

elif current_process_rank == PREVIEW_RANK:

    start_preview_sender(bind_url="tcp://localhost:50000",
                         zmq_mode="PUB",
                         detector_config=eiger9m,
                         ringbuffer_config=RingBufferConfig(
                             process_id=current_process_rank,
                             follower_ids=RECEIVER_RANKS
                         ))

else:
    raise ValueError("Process with rank %d is not assigned to any module." % current_process_rank)
