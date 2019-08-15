import unittest
from multiprocessing import Process
from time import sleep
import ringbuffer as rb

from detector_backend.detectors import DetectorDefinition, EIGER
from detector_backend.module.udp_receiver import start_udp_receiver
from detector_backend.utils_ringbuffer import create_rb_files, get_frame_metadata, get_frame_data
from tests.utils import MockRingBufferClient, MockControlClient, generate_udp_stream, generate_submodule_eiger_packets,\
    MockRingBufferMaster, cleanup_rb_files


class UdpReceiverTests(unittest.TestCase):

    def setUp(self):
        self.receive_process = []

    def tearDown(self):
        for process in self.receive_process:
            process.terminate()

        self.receive_process = []
        rb.reset()

    @classmethod
    def setUpClass(cls):
        create_rb_files(100, 64, 2*512*256)

    @classmethod
    def tearDownClass(cls):
        cleanup_rb_files()

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
                                                 image_header_n_bytes=test_eiger.image_header_n_bytes,
                                                 image_data_n_bytes=test_eiger.raw_image_data_n_bytes,
                                                 bit_depth=test_eiger.bit_depth,
                                                 as_reader=True)
        ringbuffer_client.init_buffer()

        def start_receiver():
            ringbuffer_client_udp = MockRingBufferClient(
                process_id=udp_receiver_rank,
                follower_ids=[],
                image_header_n_bytes=test_eiger.image_header_n_bytes,
                image_data_n_bytes=test_eiger.raw_image_data_n_bytes,
                bit_depth=test_eiger.bit_depth,
                as_reader=False
            )

            ringbuffer_client.init_buffer()

            start_udp_receiver(udp_ip=udp_ip,
                               udp_port=udp_port,
                               detector_def=test_eiger,
                               submodule_index=0,
                               ringbuffer=ringbuffer_client_udp,
                               control_client=test_control_client)

        self.receive_process.append(Process(target=start_receiver))
        self.receive_process[-1].start()

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

    def test_multi_module_placement(self):
        udp_ip = "127.0.0.1"
        udp_port = [12001, 12002, 12003, 12004]
        bit_depth = 16
        udp_receiver_ranks = [0, 1, 2, 3]
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

        ringbuffer_client = MockRingBufferClient(process_id=4,
                                                 follower_ids=udp_receiver_ranks,
                                                 image_header_n_bytes=test_eiger.image_header_n_bytes,
                                                 image_data_n_bytes=test_eiger.raw_image_data_n_bytes,
                                                 bit_depth=test_eiger.bit_depth,
                                                 as_reader=True)
        ringbuffer_client.init_buffer()

        def start_receiver(process_id, process_udp_port):
            ringbuffer_client_udp = MockRingBufferClient(
                process_id=process_id,
                follower_ids=[4],
                image_header_n_bytes=test_eiger.image_header_n_bytes,
                image_data_n_bytes=test_eiger.raw_image_data_n_bytes,
                bit_depth=test_eiger.bit_depth,
                as_reader=False
            )

            ringbuffer_client.init_buffer()

            start_udp_receiver(udp_ip=udp_ip,
                               udp_port=process_udp_port,
                               detector_def=test_eiger,
                               submodule_index=process_id,
                               ringbuffer=ringbuffer_client_udp,
                               control_client=test_control_client)

        self.receive_process.append(Process(target=start_receiver, args=(0, udp_port[0])))
        self.receive_process[-1].start()

        self.receive_process.append(Process(target=start_receiver, args=(1, udp_port[1])))
        self.receive_process[-1].start()

        self.receive_process.append(Process(target=start_receiver, args=(2, udp_port[2])))
        self.receive_process[-1].start()

        self.receive_process.append(Process(target=start_receiver, args=(3, udp_port[3])))
        self.receive_process[-1].start()

        rb_current_slot = rb.claim_next_slot(ringbuffer_client.rb_consumer_id)
        self.assertEqual(rb_current_slot, -1, "You should not be able to get this RB slice yet.")

        sleep(0.2)

        # Receiver 0
        generate_udp_stream(udp_ip, udp_port[0],
                            message_generator=generate_submodule_eiger_packets(bit_depth, n_frames))

        rb_current_slot = rb.claim_next_slot(ringbuffer_client.rb_consumer_id)
        self.assertEqual(rb_current_slot, -1, "You should not be able to get this RB slice yet.")

        # Receiver 1
        generate_udp_stream(udp_ip, udp_port[1],
                            message_generator=generate_submodule_eiger_packets(bit_depth, n_frames))

        rb_current_slot = rb.claim_next_slot(ringbuffer_client.rb_consumer_id)
        self.assertEqual(rb_current_slot, -1, "You should not be able to get this RB slice yet.")

        # Receiver 2
        generate_udp_stream(udp_ip, udp_port[2],
                            message_generator=generate_submodule_eiger_packets(bit_depth, n_frames))

        rb_current_slot = rb.claim_next_slot(ringbuffer_client.rb_consumer_id)
        self.assertEqual(rb_current_slot, -1, "You should not be able to get this RB slice yet.")

        # Receiver 3
        generate_udp_stream(udp_ip, udp_port[3],
                            message_generator=generate_submodule_eiger_packets(bit_depth, n_frames))

        sleep(0.2)

        rb_current_slot = rb.claim_next_slot(ringbuffer_client.rb_consumer_id)
        self.assertNotEqual(rb_current_slot, -1, "No frames found in ringbuffer.")

        self.assertListEqual(list(rb.get_header_info(0).committed_slots[:2]), [n_frames, n_frames])

        for i in range(n_frames):
            self.assertEqual(i, rb_current_slot)

            metadata_pointer = rb.get_buffer_slot(ringbuffer_client.rb_hbuffer_id, rb_current_slot)
            metadata = get_frame_metadata(metadata_pointer, len(udp_port))

            self.assertListEqual(metadata["framenums"], [i+1] * len(udp_port))
            self.assertListEqual(metadata["missing_packets_1"], [0] * len(udp_port))
            self.assertListEqual(metadata["missing_packets_2"], [0] * len(udp_port))
            self.assertListEqual(metadata["pulse_ids"], [0] * len(udp_port))
            self.assertListEqual(metadata["daq_recs"], [0] * len(udp_port))
            self.assertListEqual(metadata["module_number"], list(range(len(udp_port))))
            self.assertListEqual(metadata["module_enabled"], [1] * len(udp_port))
            self.assertEqual(metadata["frame"], i+1)
            self.assertEqual(metadata["daq_rec"], 0)
            self.assertEqual(metadata["pulse_id"], 0)
            self.assertEqual(metadata["is_good_frame"], 1)
            self.assertListEqual(metadata["pulse_id_diff"], [0] * len(udp_port))
            self.assertListEqual(metadata["framenum_diff"], [0] * len(udp_port))

            n_pixels = test_eiger.detector_size_raw[0] * test_eiger.detector_size_raw[1]
            data_pointer = rb.get_buffer_slot(ringbuffer_client.rb_dbuffer_id, rb_current_slot)
            data = get_frame_data(data_pointer, [n_pixels])
            self.assertEqual(int(data.sum()/(i+1)), 2048, "Data transfered error in frame %d." % i)

            self.assertTrue(rb.commit_slot(ringbuffer_client.rb_consumer_id, rb_current_slot))
            rb_current_slot = rb.claim_next_slot(ringbuffer_client.rb_consumer_id)

        self.assertEqual(-1, rb.claim_next_slot(ringbuffer_client.rb_consumer_id))


if __name__ == "__main__":
    unittest.main()
