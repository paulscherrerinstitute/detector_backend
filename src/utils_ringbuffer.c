#include "detectors.h"

inline void initialize_rb_header (rb_header* header,
                                  int n_packets_per_frame,
                                  uint16_t submodule_index,
                                  barebone_packet* bpacket)
{
  uint64_t ones = ~((uint64_t)0);
  
  for(int i=0; i < 8; i++) 
  {
    header->framemetadata[i] = 0;
  }

  header->framemetadata[2] = 
    ones >> (64 - n_packets_per_frame);
  
  header->framemetadata[3] = 0;
  
  if(n_packets_per_frame > 64)
  {
    header->framemetadata[3] = 
      ones >> (128 - n_packets_per_frame);
  }

  header->framemetadata[0] = bpacket->framenum;
  header->framemetadata[4] = (uint64_t) bpacket->bunchid;
  header->framemetadata[5] = (uint64_t) bpacket->debug;
  header->framemetadata[6] = (uint64_t) submodule_index;
  header->framemetadata[7] = (uint64_t) 1;
}

inline void update_rb_header (rb_header* header, barebone_packet* bpacket)
{
  const uint64_t mask = 1;

  if(bpacket->packetnum < 64)
  {
    header->framemetadata[2] ^= mask << bpacket->packetnum;
  }
  else
  {
    header->framemetadata[3] ^= mask << (bpacket->packetnum - 64);
  }
}

inline uint64_t copy_rb_header(
    rb_header* header, rb_state* rb_current_state, counter *counters, int n_packets_per_frame)
{
  uint64_t lost_packets = n_packets_per_frame - counters->current_frame_recv_packets;
  header->framemetadata[1] = lost_packets;

  memcpy(rb_current_state->header_slot_origin, header, sizeof(rb_header));

  return lost_packets;
}

inline bool commit_slot (int rb_writer_id, int rb_current_slot)
{
  if (rb_current_slot != -1)
  {
    rb_commit_slot(rb_writer_id, rb_current_slot);
    return true;
  } 
  else 
  {
    printf("[commit_slot][ERROR] I should have been committing a slot, but it is -1\n");
    return false;
  }
}

inline void commit_if_slot_dangling (
    counter* counters, rb_metadata* rb_meta, rb_header* header, rb_state* rb_current_state, int n_packets_per_frame)
{
  if (counters->current_frame != NO_CURRENT_FRAME)
  {
    uint64_t lost_packets = copy_rb_header(header, rb_current_state, counters, n_packets_per_frame);
    
    counters->total_lost_packets += lost_packets;
    counters->total_lost_frames++;

    commit_slot(rb_meta->rb_writer_id, rb_current_state->rb_current_slot);

    #ifdef DEBUG
      printf("[commit_if_slot_dangling][%d] framenum: %"PRIu64" lost_packets: %"PRIu64"\n",
        getpid(), counters->current_frame, lost_packets);
    #endif

    counters->current_frame = NO_CURRENT_FRAME;
  }
}

inline bool claim_next_slot(rb_metadata* rb_meta, rb_state* rb_current_state)
{
  rb_current_state->rb_current_slot = rb_claim_next_slot(rb_meta->rb_writer_id);
  if(rb_current_state->rb_current_slot == -1)
  {
    return false;
  }

  rb_current_state->data_slot_origin = (char *) rb_get_buffer_slot (
    rb_meta->rb_dbuffer_id, rb_current_state->rb_current_slot
  );
  
  rb_current_state->header_slot_origin = (rb_header *) rb_get_buffer_slot (
    rb_meta->rb_hbuffer_id, rb_current_state->rb_current_slot
  );

  return true;
}
