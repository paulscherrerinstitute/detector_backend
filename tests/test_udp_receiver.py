import os
import unittest
from multiprocessing import Process
from time import sleep
import ringbuffer as rb
from detector_backend import config

from detector_backend.detectors import DetectorDefinition, EIGER
from detector_backend.module.udp_receiver import start_udp_receiver
from tests.utils import MockRingBufferClient, MockControlClient, generate_udp_stream, generate_submodule_eiger_packets, \
    MockRingBufferMaster


class UdpReceiverTests(unittest.TestCase):

    def setUp(self):
        self.receive_process = None

    def tearDown(self):
        if self.receive_process is not None:
            self.receive_process.terminate()
            self.receive_process = None

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        if os.path.isfile(config.DEFAULT_RB_HEAD_FILE):
            os.remove(config.DEFAULT_RB_HEAD_FILE)

        if os.path.isfile(config.DEFAULT_RB_IMAGE_HEAD_FILE):
            os.remove(config.DEFAULT_RB_IMAGE_HEAD_FILE)

        if os.path.isfile(config.DEFAULT_RB_IMAGE_DATA_FILE):
            os.remove(config.DEFAULT_RB_IMAGE_DATA_FILE)

    def test_single_receiver(self):
        udp_ip = "127.0.0.1"
        udp_port = 12001
        bit_depth = 16
        udp_receiver_rank = 10
        n_frames = 10

        test_eiger = DetectorDefinition(
            detector_name="Test Eiger 0.5M",
            detector_model=EIGER,
            geometry=[1, 1],
            bit_depth=bit_depth
        )

        test_control_client = MockControlClient()

        ringbuffer_master = MockRingBufferMaster()
        ringbuffer_master.create_buffer()

        ringbuffer_client = MockRingBufferClient(process_id=0,
                                                 follower_ids=[udp_receiver_rank],
                                                 detector_config=test_eiger,
                                                 as_reader=True)
        ringbuffer_client.init_buffer()

        def start_receiver():
            ringbuffer_client_udp = MockRingBufferClient(
                process_id=udp_receiver_rank,
                follower_ids=[],
                detector_config=test_eiger,
                as_reader=False
            )

            ringbuffer_client.init_buffer()

            start_udp_receiver(udp_ip=udp_ip,
                               udp_port=udp_port,
                               detector_def=test_eiger,
                               module_id=2,
                               submodule_id=0,
                               ringbuffer=ringbuffer_client_udp,
                               control_client=test_control_client)

        self.receive_process = Process(target=start_receiver)
        self.receive_process.start()

        rb_current_slot = rb.claim_next_slot(ringbuffer_client.rb_consumer_id)
        self.assertEqual(rb_current_slot, -1, "You should not be able to get this RB slice yet.")

        self.assertEqual(list(rb.get_header_info(0).committed_slots)[udp_receiver_rank], -1)

        sleep(0.2)

        generate_udp_stream(udp_ip, udp_port,
                            message_generator=generate_submodule_eiger_packets(bit_depth, n_frames))

        sleep(0.2)

        rb_current_slot = rb.claim_next_slot(ringbuffer_client.rb_consumer_id)
        self.assertNotEqual(rb_current_slot, -1, "No frames found in ringbuffer.")

        self.assertEqual(list(rb.get_header_info(0).committed_slots)[udp_receiver_rank], n_frames)
