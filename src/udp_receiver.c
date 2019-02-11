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
#include "utils_metadata.c"
#include "utils_ringbuffer.c"
#include "utils_receiver.c"


#ifdef JUNGFRAU 
  #include "jungfrau.c"
#endif

#ifdef EIGER
  #include "eiger.c"
#endif

inline bool receive_packet (int sock, char* udp_packet, size_t udp_packet_bytes, 
  barebone_packet* bpacket, detector_definition* det_definition )
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

inline void save_packet (
  barebone_packet* bpacket, rb_metadata* rb_meta, 
  counter* counters, detector* det, detector_definition* det_definition ) 
{
  
  if (!is_slot_ready_for_frame(bpacket->framenum, counters))
  {
    commit_if_slot_dangling(counters, rb_meta);
    
    claim_next_slot(rb_meta);

    initialize_rb_header(rb_meta);

    initialize_counters_for_new_frame(counters, bpacket->framenum);
  }

  counters->current_frame_recv_packets++;
  counters->total_recv_packets++;

  int line_number = get_packet_line_number(rb_meta, bpacket->packetnum);  

  copy_data(*det, *rb_meta, bpacket->data, line_number);

  update_rb_header(rb_meta, bpacket, counters);

  if(is_frame_complete(rb_meta->n_packets_per_frame, counters))
  {
    #ifdef DEBUG
      printf("[save_packet][mod_number %d] Frame complete, got packet %d  #%d of %d frame %lu / %lu\n", 
        rb_meta->mod_number, bpacket->packetnum, counters->current_frame_recv_packets, 
        rb_meta->n_packets_per_frame, bpacket->framenum, counters->current_frame);
    #endif

    commit_slot(rb_meta->rb_writer_id, rb_meta->rb_current_slot);

    counters->current_frame = NO_CURRENT_FRAME;
    counters->total_recv_frames++;
  }
}

int put_data_in_rb (
  int sock, int bit_depth, int rb_current_slot, 
  int rb_header_id, int rb_hbuffer_id, int rb_dbuffer_id, int rb_writer_id, 
  uint32_t n_frames, float timeout, detector det) {
  /*!
    Main routine to be called from python. Infinite loop with timeout calling for socket receive and putting data in memory, 
    checking that all packets are acquired.
   */
  
  if (bit_depth != 16 && bit_depth != 32) 
  {
    printf("[put_data_in_rb][%d] Please setup bit_depth to 16 or 32.\n", getpid());
    return -1;
  }

  if ((strcmp(det.detector_name, "EIGER") != 0) && (strcmp(det.detector_name, "JUNGFRAU") != 0))
  {
    printf("[put_data_in_rb][%d] Please setup detector_name to EIGER or JUNGFRAU.\n", getpid());
    return -1;
  }

  rb_metadata rb_meta = get_ringbuffer_metadata (
    rb_writer_id, rb_header_id, rb_hbuffer_id, rb_dbuffer_id, rb_current_slot, 
    det, det_definition.data_bytes_per_packet, bit_depth );

  struct timeval udp_socket_timeout;
  udp_socket_timeout.tv_sec = 0;
  udp_socket_timeout.tv_usec = 50;
  setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&udp_socket_timeout, sizeof(struct timeval));

  struct timeval timeout_start_time;
  gettimeofday(&timeout_start_time, NULL);

  uint64_t last_stats_print_total_recv_frames = 0;
  
  struct timeval last_stats_print_time;
  gettimeofday(&last_stats_print_time, NULL);

  counter counters = {NO_CURRENT_FRAME, 0, 0, 0, 0, 0};
  char udp_packet[det_definition.udp_packet_bytes];
  barebone_packet bpacket;

  while (true)
  {
    bool is_packet_received = receive_packet (
      sock, (char*)&udp_packet, det_definition.udp_packet_bytes, &bpacket, &det_definition
    );

    if (is_packet_received) 
    {
      save_packet(&bpacket, &rb_meta, &counters, &det, &det_definition);

      // Reset timeout time.
      gettimeofday(&timeout_start_time, NULL);
    }
    else if (is_timeout_expired(timeout, timeout_start_time))
    {
      // If images are lost in the last frame.
      commit_if_slot_dangling(&counters, &rb_meta);

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

  return counters.total_recv_frames + counters.total_lost_frames;
}
