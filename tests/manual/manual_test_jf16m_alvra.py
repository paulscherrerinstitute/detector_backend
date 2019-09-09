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

j16m = DetectorDefinition(
    detector_name="Test JF 16M",
    detector_model=JUNGFRAU,
    geometry=[31, 1],
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
	("10.30.20.6", 50067),
	("10.30.20.6", 50068),
	("10.30.20.6", 50069),
	("10.30.20.6", 50070),
	("10.30.20.6", 50071),
	("10.30.20.6", 50072),
	("10.30.20.6", 50073),
	("10.30.20.6", 50074),
	("10.30.20.6", 50075),
	("10.30.20.6", 50076),
#	("10.30.20.6", 50077),
	("10.30.20.6", 50078),
	("10.30.20.6", 50079),
	("10.30.20.6", 50080),
	("10.30.20.6", 50081),
	("10.30.20.6", 50082),
	("10.30.20.6", 50083),
	("10.30.20.6", 50084),
	("10.30.20.6", 50085),
	("10.30.20.6", 50086),
	("10.30.20.6", 50087),
	("10.30.20.6", 50088),
	("10.30.20.6", 50089),
	("10.30.20.6", 50090),
	("10.30.20.6", 50091),
]

receive_and_write(jf16m, udp_ip_and_port)
