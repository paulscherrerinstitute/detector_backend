#include "detectors.h"

inline void initialize_rb_header (rb_header* header, rb_metadata* rb_meta, barebone_packet* bpacket)
{
  uint64_t ones = ~((uint64_t)0);
  
  for(int i=0; i < 8; i++) 
  {
    header->framemetadata[i] = 0;
  }

  header->framemetadata[2] = 
    ones >> (64 - rb_meta->n_packets_per_frame);
  
  header->framemetadata[3] = 0;
  
  if(rb_meta->n_packets_per_frame > 64)
  {
    header->framemetadata[3] = 
      ones >> (128 - rb_meta->n_packets_per_frame);
  }

  header->framemetadata[0] = bpacket->framenum;
  header->framemetadata[4] = (uint64_t) bpacket->bunchid;
  header->framemetadata[5] = (uint64_t) bpacket->debug;
  header->framemetadata[6] = (uint64_t) rb_meta->mod_number;
  header->framemetadata[7] = (uint64_t) 1;
}

inline void update_rb_header (rb_header* header, barebone_packet* bpacket)
{   
  const uint64_t mask = 1;
  if(bpacket->packetnum < 64)
  {
    header->framemetadata[2] &= ~(mask << bpacket->packetnum);
  }
  else
  {
    header->framemetadata[3] &= ~(mask << (bpacket->packetnum - 64));
  }
}

inline uint64_t copy_rb_header(rb_header* header, rb_metadata* rb_meta, counter *counters)
{
  uint64_t lost_packets = rb_meta->n_packets_per_frame - counters->current_frame_recv_packets;
  header.framemetadata[1] = lost_packets;

  memcpy(rb_meta->header_slot_origin, header, sizeof(rb_header))

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
  counter* counters, rb_metadata* rb_meta)
{
  if (counters->current_frame != NO_CURRENT_FRAME)
  {
    uint64_t lost_packets = copy_rb_header(rb_header* header, rb_meta, counters)
    
    counters->total_lost_packets += lost_packets;
    counters->total_lost_frames++;

    commit_slot(rb_meta->rb_writer_id, rb_meta->rb_current_slot);

    #ifdef DEBUG
      printf("[commit_if_slot_dangling][%d] framenum: %lu lost_packets: %lu\n", 
        getpid(), counters->current_frame, lost_packets);
    #endif
  }
}

inline void claim_next_slot(rb_metadata* rb_meta)
{
  rb_meta->rb_current_slot = rb_claim_next_slot (rb_meta->rb_writer_id );
  while(rb_meta->rb_current_slot == -1)
  {
    rb_meta->rb_current_slot = rb_claim_next_slot(rb_meta->rb_writer_id );
  }

  rb_meta->data_slot_origin = (char *) rb_get_buffer_slot (
    rb_meta->rb_dbuffer_id, rb_meta->rb_current_slot 
  );

  // Bytes offset in current buffer slot = mod_number * (bytes/pixel)
  rb_meta->data_slot_origin += (rb_meta->mod_origin * rb_meta->bit_depth) / 8;
  
  rb_meta->header_slot_origin = (rb_header *) rb_get_buffer_slot (
    rb_meta->rb_hbuffer_id, rb_meta->rb_current_slot
  );
  rb_meta->header_slot_origin += rb_meta->mod_number;
}