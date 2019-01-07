#define _GNU_SOURCE
#include <stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <stdio.h>
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
#include "jungfrau.c"
#include "eiger.c"
#include "utils.c"


inline void claim_and_initialize_slot (
  int* rb_current_slot, char** data_slot_origin, rb_header** header_slot_origin, 
  int rb_writer_id, int rb_dbuffer_id, int rb_hbuffer_id, int mod_number, 
  int bit_depth, int n_packets_per_frame)
{
  *rb_current_slot = rb_claim_next_slot(rb_writer_id);
  while(*rb_current_slot == -1)
  {
    *rb_current_slot = rb_claim_next_slot(rb_writer_id);
  }

  *data_slot_origin = (char *) rb_get_buffer_slot(rb_dbuffer_id, *rb_current_slot);
  // Bytes offset in current buffer slot = mod_number * (bytes/pixel)
  *data_slot_origin += (mod_origin * bit_depth) / 8;
  
  *header_slot_origin = (rb_header *) rb_get_buffer_slot(rb_hbuffer_id, *rb_current_slot);
  // computing the origin and stride of memory locations
  *header_slot_origin += mod_number;

  initialize_rb_header(*header_slot_origin, n_packets_per_frame);
}

inline bool is_slot_ready_for_frame (
  uint64_t frame_number, counter *counters, int n_packets_per_frame, 
  int rb_current_slot, int rb_writer_id)
{
  // We already have a slot for this frame.
  if (counters->current_frame == frame_number) 
  {
    return true;
  }
  // We got a new frame before the last one was commited. Commit the dangling slot.
  else if (counters->current_frame != NO_CURRENT_FRAME)
  {
    commit_slot(rb_writer_id, rb_current_slot)

    //do_stats with recv_packets -1
    counters->lost_frames = n_packets_per_frame - (counters->recv_packets - 1);

    counters->recv_packets = 1;
  }

  return false;
}

inline bool receive_save_packet(int sock, int rb_hbuffer_id, int *rb_current_slot, int rb_dbuffer_id, int rb_writer_id, uint32_t mod_origin, 
  int mod_number, int n_lines_per_packet, int n_packets_per_frame, counter* counters, detector det, int bit_depth, detector_definition det_definition){

  const char udp_packet[det_definition.udp_packet_bytes];
  const int received_data_len = get_udp_packet(sock, &udp_packet, det_definition.udp_packet_bytes);

  barebone_packet bpacket = det_definition.interpret_udp_packet(udp_packet, received_data_len);

  #ifdef DEBUG
    if(received_data_len > 0){
      printf("[UDPRECEIVER][%d] nbytes %ld framenum: %lu packetnum: %i\n", getpid(), bpacket.data_len, bpacket.framenum, bpacket.packetnum);
    }
  #endif

  // Invalid size/empty packet. received_data_len == 0 in this case.
  if(received_data_len != det_definition.udp_packet_bytes)
  {
    return false;
  }

  counters->recv_packets++;

  char* data_slot_origin;
  rb_header* header_slot_origin

  if (!is_slot_ready_for_frame(bpacket.framenum, counters, n_packets_per_frame, *rb_current_slot, rb_writer_id)
  {
 
    claim_and_initialize_slot(rb_current_slot, &data_slot_origin, &header_slot_origin,
      rb_writer_id, rb_dbuffer_id, rb_hbuffer_id, mod_number, bit_depth, n_packets_per_frame);

    counters->current_frame = bpacket.framenum;
  }

  // assuming packetnum sequence is 0..N-1
  int line_number = n_lines_per_packet * (n_packets_per_frame - bpacket.packetnum - 1);

  det_definition.copy_data(det, line_number, n_lines_per_packet, ringbuffer_slot_origin, bpacket.data, bit_depth);

  // updating counters
  update_rb_header(ph, bpacket, n_packets_per_frame, counters, mod_number);

  // commit the slot if this is the last packet of the frame
  if(counters->recv_packets == n_packets_per_frame)
  {
    //this is the last packet of the frame
    #ifdef DEBUG
      printf("[receive_save_packet][mod_number %d] Frame complete, got packet %d  #%d of %d frame %lu / %lu\n", 
        mod_number, bpacket->packetnum, counters->recv_packets, n_packets_per_frame, 
        bpacket->framenum, counters->current_frame);
    #endif

    counters->recv_frames++;
    //counters->recv_packets = 0;
    counters->current_frame = NO_CURRENT_FRAME; // this will cause getting a new slot afterwards
    counters->lost_frames = 0;

    commit_slot(rb_writer_id, *rb_current_slot)
  }

  return true;
}

int put_data_in_rb(int sock, int bit_depth, int rb_current_slot, int rb_header_id, int rb_hbuffer_id, int rb_dbuffer_id, int rb_writer_id, 
                    int16_t n_frames, float timeout, detector det){
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

  detector_definition det_definition;
  if (strcmp(det.detector_name, "EIGER") == 0)
  {
    det_definition = eiger_definition;
  } 
  else if (strcmp(det.detector_name, "JUNGFRAU") == 0) 
  {
    det_definition = jungfrau_definition;
  }

  uint32_t mod_origin = get_current_module_offset_in_pixels(det);
  int mod_number = get_current_module_index(det);
  int n_packets_per_frame = get_n_packets_per_frame(det, det_definition.data_bytes_per_packet, bit_depth);
  int n_lines_per_packet = get_n_lines_per_packet(det, det_definition.data_bytes_per_packet, bit_depth);

  #ifdef DEBUG
    printf("[put_data_in_rb][%d] mod_origin: %d mod_number: %d bit_depth: %d n_frames:%d\n",
      getpid(), mod_origin, mod_number, bit_depth, n_frames);
  #endif

  struct timeval udp_socket_timeout;
  udp_socket_timeout.tv_sec = 0;
  udp_socket_timeout.tv_usec = 50;
  setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&udp_socket_timeout, sizeof(struct timeval));

  struct timeval timeout_start_time;
  gettimeofday(&timeout_start_time, NULL);

  struct timeval last_stats_print_time;
  gettimeofday(&last_stats_print_time, NULL);

  counter counters;
  counters.current_frame = NO_CURRENT_FRAME;
  counters.recv_frames = 0;

  while(true)
  {
    bool is_packet_received = receive_save_packet (
      sock, rb_hbuffer_id, &rb_current_slot, rb_dbuffer_id, rb_writer_id, 
      mod_origin, mod_number, n_lines_per_packet, n_packets_per_frame, 
      &counters, det, bit_depth, det_definition );

    if (!is_packet_received && is_timeout_expired(timeout, timeout_start_time)) 
    {
      // Flushes the last message, in case the last frame lost packets.
      if (commit_slot(rb_writer_id, rb_current_slot)) 
      {
        printf(
        "[put_data_in_rb][mod_number %d] Timeout. Committed slot %d with %d packets.",
        mod_number, rb_current_slot, counters.recv_packets );
      }

      break;
    }

    // TODO: Check if this condition is needed.
    if (n_frames != -1 && counters.recv_frames >= n_frames) 
    {
      // Flushes the last message, in case the last frame lost packets.
      if (commit_slot(rb_writer_id, rb_current_slot))
      {
        printf(
        "[put_data_in_rb][mod_number %d] Finished. Committed slot %d with %d packets.",
        mod_number, rb_current_slot, counters.recv_packets );
      }

      break;
    }

    if (counters.recv_frames % PRINT_STATS_N_FRAMES_MODULO == 0 
      && counters.recv_frames != 0)
    {
      print_statistics(&counters, last_stats_print_time);
      
      gettimeofday(&last_stats_print_time, NULL);
    }

    // Reset timeout time.
    gettimeofday(&timeout_start_time, NULL);
  }

  return counters.recv_frames;
}
