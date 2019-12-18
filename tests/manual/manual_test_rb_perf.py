from detector_backend.utils_ringbuffer import create_rb_files

from detector_backend.detectors import DetectorDefinition, EIGER

from tests.utils import MockRingBufferClient, MockRingBufferMaster

import ringbuffer as rb


def test_prefilled_buffer(n_buffer_slots, rb_folder, detector: DetectorDefinition, n_slots_to_fill):

    create_rb_files(n_buffer_slots, detector.image_header_n_bytes, detector.image_data_n_bytes, rb_folder=rb_folder)

    rb_master = MockRingBufferMaster(rb_folder=rb_folder)
    rb_master.create_buffer()

    rb_client_writer = MockRingBufferClient(
        process_id=0,
        follower_ids=[],
        detector_def=detector,
        as_reader=False,
        rb_folder=rb_folder
    )

    rb_client_reader = MockRingBufferClient(
        process_id=1,
        follower_ids=[0],
        detector_def=detector,
        as_reader=True,
        rb_folder=rb_folder
    )

    rb_client_writer.init_buffer()
    rb_client_reader.init_buffer()

    for i_slot in range(n_slots_to_fill):

        rb_current_slot = rb.claim_next_slot(rb_client_writer.rb_consumer_id)
        if rb_current_slot == -1:
            raise RuntimeError("Cannot get next slot from ringbuffer. Are the RB files available?")

        if not rb.commit_slot(rb_client_writer.rb_consumer_id, rb_current_slot):
            raise RuntimeError("Cannot commit rb slot %d." % rb_current_slot)




def main():
    pass


if __name__ == "__main__":
    main()
