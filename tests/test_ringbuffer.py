import ctypes
import unittest

import numpy

import ringbuffer as rb
from detector_backend.detectors import DetectorDefinition, JUNGFRAU
from detector_backend.utils_ringbuffer import create_rb_files, get_frame_data
from tests.utils import MockRingBufferMaster, cleanup_rb_files, MockRingBufferClient


class RingbufferTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        create_rb_files(100, 64, 2 * 512 * 256, 2 * 540 * 256)

    @classmethod
    def tearDownClass(cls):
        cleanup_rb_files()

    def test_data_transfer(self):
        master = MockRingBufferMaster()
        master.create_buffer()

        jf_test_det = DetectorDefinition(
            detector_name="0.5 JF",
            detector_model=JUNGFRAU,
            geometry=[1, 1],
            bit_depth=16
        )

        writer = MockRingBufferClient(
            process_id=1,
            follower_ids=[],
            detector_def=jf_test_det,
            as_reader=False
        )

        writer.init_buffer()

        receiver = MockRingBufferClient(
            process_id=2,
            follower_ids=[1],
            detector_def=jf_test_det
        )

        receiver.init_buffer()

        writer_current_slot = rb.claim_next_slot(writer.rb_consumer_id)
        self.assertNotEqual(writer_current_slot, -1, "The writer should be able to get the slot.")

        receiver_current_slot = rb.claim_next_slot(receiver.rb_consumer_id)
        self.assertEqual(receiver_current_slot, -1, "The reader should not be able to get the slot yet.")

        sent_data = numpy.random.randint(low=0, high=128, size=64, dtype="uint16")

        write_pointer = rb.get_buffer_slot(writer.rb_raw_dbuffer_id, writer_current_slot)
        ctypes.memmove(write_pointer, sent_data.ctypes.data, sent_data.nbytes)
        rb.commit_slot(writer.rb_consumer_id, writer_current_slot)

        receiver_current_slot = rb.claim_next_slot(receiver.rb_consumer_id)
        self.assertEqual(receiver_current_slot, writer_current_slot, "Slot should be ready for the receiver.")

        receive_pointer = rb.get_buffer_slot(receiver.rb_raw_dbuffer_id, receiver_current_slot)
        received_data = get_frame_data(receive_pointer, [64])

        numpy.testing.assert_array_equal(sent_data, received_data)
