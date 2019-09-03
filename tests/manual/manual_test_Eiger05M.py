import logging

from detector_backend.starter import start_standard_setup
from detector_backend.detectors import DetectorDefinition, EIGER


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

eiger1m = DetectorDefinition(
    detector_name="Test Eiger 0.5M",
    detector_model=EIGER,
    geometry=[1, 1],
    bit_depth=16
)

udp_ip_and_port = [("127.0.0.1", 12000),
                   ("127.0.0.1", 12001),
                   ("127.0.0.1", 12002),
                   ("127.0.0.1", 12003)]

start_standard_setup(eiger1m, udp_ip_and_port)
