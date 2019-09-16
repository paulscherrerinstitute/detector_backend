import logging

from detector_backend.profile.receive_write import receive_and_write
from detector_backend.detectors import DetectorDefinition, JUNGFRAU

default_logging_level = logging.INFO
logging.basicConfig(level=default_logging_level)

# logging.getLogger("rest_api").setLevel(logging.DEBUG)
# logging.getLogger("udp_receiver").setLevel(logging.DEBUG)
# logging.getLogger("rb_assembler").setLevel(logging.DEBUG)
# logging.getLogger("zmq_sender").setLevel(logging.DEBUG)
# logging.getLogger("mpi_ringbuffer_master").setLevel(logging.DEBUG)
# logging.getLogger("mpi_ringbuffer_client").setLevel(logging.DEBUG)
# logging.getLogger("mpi_control_master").setLevel(logging.DEBUG)
# logging.getLogger("mpi_control_client").setLevel(logging.DEBUG)

jf4m = DetectorDefinition(
    detector_name="Test JF 4M",
    detector_model=JUNGFRAU,
    geometry=[8, 1],
    bit_depth=16
)

udp_ip_and_port = [
    ("10.30.20.6", 50060),
    ("10.30.20.6", 50061),
    ("10.30.20.6", 50062),
    ("10.30.20.6", 50063),
    ("10.30.20.6", 50064),
    ("10.30.20.6", 50065),
    ("10.30.20.6", 50066),
    ("10.30.20.6", 50067)]

receive_and_write(jf4m, udp_ip_and_port)
