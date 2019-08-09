#define _GNU_SOURCE
#include <stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <inttypes.h>
#include <sys/time.h>
#include <ring_buffer.h>
#include <arpa/inet.h>
#include <sched.h>

#include "detectors.h"
#include "utils_ringbuffer.c"
#include "utils_receiver.c"


#ifdef JUNGFRAU
  #include "jungfrau.c"
#endif

#ifdef EIGER
  #include "eiger.c"
#endif

bool receive_packet (int sock, char* udp_packet, size_t udp_packet_bytes,
  barebone_packet* bpacket)
{
  const int received_data_len = get_udp_packet(sock, udp_packet, udp_packet_bytes);

  *bpacket = interpret_udp_packet(udp_packet, received_data_len);

  #ifdef DEBUG
    if(received_data_len > 0){
      printf("[receive_packet][%d] nbytes %ld framenum: %lu packetnum: %i\n",
        getpid(), bpacket->data_len, bpacket->framenum, bpacket->packetnum);
    }
  #endif

  return bpacket->is_valid;
}

void save_packet (
  barebone_packet* bpacket, rb_metadata* rb_meta, counter* counters,
  detector* det, rb_header* header, rb_state* rb_current_state)
{

  if (!is_slot_ready_for_frame(bpacket->framenum, counters))
  {
    commit_if_slot_dangling(counters, rb_meta, header, rb_current_state);

    claim_next_slot(rb_meta, rb_current_state);

    initialize_rb_header(header, rb_meta, bpacket);

    initialize_counters_for_new_frame(counters, bpacket->framenum);
  }

  counters->current_frame_recv_packets++;
  counters->total_recv_packets++;

  long dest_offset = bpacket->packetnum * det->bytes_data_per_packet;

  memcpy(
      (char*) (rb_meta.data_slot_origin) + dest_offset,
      (char*) bpacket->data,
      det->bytes_data_per_packet
  );

  update_rb_header(header, bpacket);

  if(is_frame_complete(rb_meta->n_packets_per_frame, counters))
  {
    #ifdef DEBUG
      printf("[save_packet][mod_number %d] Frame complete, got packet %d  #%d of %d frame %lu / %lu\n",
        rb_meta->mod_number, bpacket->packetnum, counters->current_frame_recv_packets,
        rb_meta->n_packets_per_frame, bpacket->framenum, counters->current_frame);
    #endif

    copy_rb_header(header, rb_current_state, counters, rb_meta->n_packets_per_frame);

    commit_slot(rb_meta->rb_writer_id, rb_current_state->rb_current_slot);

    counters->current_frame = NO_CURRENT_FRAME;
    counters->total_recv_frames++;
  }
}

void assemble_jf_image (rb_metadata rb_meta, detector det, uint32_t n_frames, float timeout)
{
  struct timeval timeout_start_time;
  gettimeofday(&timeout_start_time, NULL);

  rb_header header;

  rb_state rb_current_state = {-1, NULL, NULL};
  counter counters = {NO_CURRENT_FRAME, 0, 0, 0, 0, 0};

  while (true)
  {
    bool is_packet_received = receive_packet (
      sock, (char*)&udp_packet, det.bytes_per_packet, &bpacket
    );

    if (is_packet_received)
    {
      save_packet(&bpacket, &rb_meta, &counters, &det, &header, &rb_current_state);

      // Reset timeout time.
      gettimeofday(&timeout_start_time, NULL);
    }
    else if (is_timeout_expired(timeout, timeout_start_time))
    {
      // If images are lost in the last frame.
      commit_if_slot_dangling(&counters, &rb_meta, &header, &rb_current_state);

      break;
    }

    if (is_acquisition_completed(n_frames, &counters))
    {
      printf("[put_data_in_rb][mod_number %d] Acquisition finished.", rb_meta.mod_number);
      break;
    }

    if (counters.total_recv_frames % PRINT_STATS_N_FRAMES_MODULO == 0
      && counters.total_recv_frames != last_stats_print_total_recv_frames)
    {
      print_statistics(&counters, &last_stats_print_time);

      last_stats_print_total_recv_frames = counters.total_recv_frames;
    }
  }
}
