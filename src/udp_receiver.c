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

#define PRINT_STATS_N_FRAMES_MODULO 100

int get_udp_packet(int socket_fd, void* buffer, size_t buffer_len) 
{
  size_t n_bytes = recv(socket_fd, buffer, buffer_len, 0);

  // Did not receive a valid frame packet.
  if (n_bytes != buffer_len) {
    return 0;
  }

  return n_bytes;
}


bool act_on_new_frame (
  counter *counters, int n_packets_per_frame, barebone_packet *bpacket, 
  int *rb_current_slot, int rb_writer_id )
{

  bool commit_flag=false;

  // this fails in case frame number is not updated by the detector (or its simulation)
  if(counters->recv_packets == n_packets_per_frame 
    && bpacket->framenum == counters->current_frame){
  //this is the last packet of the frame
  #ifdef DEBUG
    printf("[UDPRECV] Frame complete, got packet %d  #%d of %d frame %lu / %lu\n", bpacket->packetnum, counters->recv_packets, 
      n_packets_per_frame, bpacket->framenum, counters->current_frame);
  #endif

    counters->recv_frames++;
    //counters->recv_packets = 0;
    counters->current_frame = 0; // this will cause getting a new slot afterwards
    commit_flag = true; // for committing the slot later
    counters->lost_frames = 0;
  }
  // this means we are in a new frame (first one included)
  else if (counters->current_frame != bpacket->framenum){        
    if(counters->recv_packets != n_packets_per_frame && counters->recv_packets != 1){
      // this means we lost some packets before, and we have a dangling slot. Current frame is set to 0 when a complete frame is committed
      if(counters->current_frame != 0){
        if(*rb_current_slot != -1){
          // add some checks here
          rb_commit_slot(rb_writer_id, *rb_current_slot);
        }
        else
          printf("[ERROR] I should have been committing a dangling slot, but it is -1\n");

        //do_stats with recv_packets -1
        counters->lost_frames = n_packets_per_frame - (counters->recv_packets - 1);
      }
      counters->recv_packets = 1;
    }
    counters->current_frame = bpacket->framenum;
    *rb_current_slot = rb_claim_next_slot(rb_writer_id);
    while(*rb_current_slot == -1){
      *rb_current_slot = rb_claim_next_slot(rb_writer_id);
    }
  }
  return commit_flag;
}

void initialize_rb_header(counter *counters, rb_header *ph, int n_packets_per_frame)
{
  uint64_t ones = ~((uint64_t)0);
  
  if (counters->recv_packets == 1)
  {
    for(int i=0; i < 8; i++) 
    {
      ph->framemetadata[i] = 0;
    } 

    ph->framemetadata[2] = ones >> (64 - n_packets_per_frame);
    
    ph->framemetadata[3] = 0;
    if(n_packets_per_frame > 64)
    {
      ph->framemetadata[3] = ones >> (128 - n_packets_per_frame);
    }
  }
}

void update_rb_header(rb_header * ph, barebone_packet bpacket, int n_packets_per_frame, counter *counters, int mod_number)
{
  ph->framemetadata[0] = bpacket.framenum; // this could be avoided mayne
  ph->framemetadata[1] = n_packets_per_frame - counters->recv_packets;
    
  const uint64_t mask = 1;
  if(bpacket.packetnum < 64){
    ph->framemetadata[2] &= ~(mask << bpacket.packetnum);
  }
  else{
    ph->framemetadata[3] &= ~(mask << (bpacket.packetnum - 64));
  }

  ph->framemetadata[4] = (uint64_t) bpacket.bunchid;
  ph->framemetadata[5] = (uint64_t) bpacket.debug;
  ph->framemetadata[6] = (uint64_t) mod_number;
  ph->framemetadata[7] = (uint64_t) 1;
}


barebone_packet get_put_data(int sock, int rb_hbuffer_id, int *rb_current_slot, int rb_dbuffer_id, int rb_writer_id, uint32_t mod_origin, 
  int mod_number, int n_lines_per_packet, int n_packets_per_frame, counter * counters, detector det, int bit_depth, detector_definition det_definition){

  const char udp_packet[det_definition.udp_packet_bytes];
  const int received_data_len = get_udp_packet(sock, &udp_packet, det_definition.udp_packet_bytes);

  barebone_packet bpacket = det_definition.interpret_udp_packet(udp_packet, received_data_len);

  #ifdef DEBUG
    if(received_data_len > 0){
      printf("[UDPRECEIVER][%d] nbytes %ld framenum: %lu packetnum: %i\n", getpid(), bpacket.data_len, bpacket.framenum, bpacket.packetnum);
    }
  #endif

  // Invalid size/empty packet. received_data_len == 0 in this case.
  if(received_data_len != det_definition.udp_packet_bytes){
    return bpacket;
  }

  counters->recv_packets++;
  bool commit_flag = act_on_new_frame(counters, n_packets_per_frame, &bpacket, rb_current_slot, rb_writer_id);
  
  // Data copy
  // getting the pointers in RB for header and data - must be done after slots are committed / assigned
  rb_header* ph = (rb_header *) rb_get_buffer_slot(rb_hbuffer_id, *rb_current_slot);
  char* ringbuffer_slot_origin = (char *) rb_get_buffer_slot(rb_dbuffer_id, *rb_current_slot);
  // computing the origin and stride of memory locations
  ph += mod_number;

  // Bytes offset in current buffer slot = mod_number * (bytes/pixel)
  ringbuffer_slot_origin += (mod_origin * bit_depth) / 8;

  // initializing - recv_packets already increased above
  if (counters->recv_packets == 1) {
    initialize_rb_header(counters, ph, n_packets_per_frame);
  }

  // assuming packetnum sequence is 0..N-1
  int line_number = n_lines_per_packet * (n_packets_per_frame - bpacket.packetnum - 1);

  det_definition.copy_data(det, line_number, n_lines_per_packet, ringbuffer_slot_origin, bpacket.data, bit_depth);

  // updating counters
  update_rb_header(ph, bpacket, n_packets_per_frame, counters, mod_number);

  // commit the slot if this is the last packet of the frame
  if(commit_flag){
    if(*rb_current_slot != -1){
    // add some checks here
      rb_commit_slot(rb_writer_id, *rb_current_slot);
    }
    else
      printf("[ERROR] I should have been committing a slot, but it is -1\n");
    commit_flag = false;
  }

  return bpacket;
}

int put_data_in_rb(int sock, int bit_depth, int rb_current_slot, int rb_header_id, int rb_hbuffer_id, int rb_dbuffer_id, int rb_writer_id, 
                    int16_t nframes, float timeout, detector det){
  /*!
    Main routine to be called from python. Infinite loop with timeout calling for socket receive and putting data in memory, 
    checking that all packets are acquired.
   */
  
  if (bit_depth != 16 && bit_depth != 32) 
  {
    printf("[UDP_RECEIVER][%d] Please setup bit_depth to 16 or 32.\n", getpid());
    return -1;
  }

  if ((strcmp(det.detector_name, "EIGER") != 0) && (strcmp(det.detector_name, "JUNGFRAU") != 0))
  {
    printf("[UDP_RECEIVER][%d] Please setup detector_name to EIGER or JUNGFRAU.\n", getpid());
    return -1;
  }

  int stat_total_frames = 0;
  int tot_lost_packets = 0;
  
  struct  timeval ti, te; //for timing
  double tdif=-1;

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

  // Timeout for blocking sock recv
  struct timeval tv;
  tv.tv_sec = 0;
  tv.tv_usec = 50;
  setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof(struct timeval));

  // Timeout for receiving packets
  struct timeval tv_start;
  double timeout_i = 0;

  gettimeofday(&tv_start, NULL);

  barebone_packet bpacket;

  counter counters;
  counters.current_frame = 0;
  counters.recv_frames = 0;

  while(true){

    bpacket = get_put_data (
      sock, rb_hbuffer_id, &rb_current_slot, rb_dbuffer_id, rb_writer_id, 
      mod_origin, mod_number, n_lines_per_packet, n_packets_per_frame, 
      &counters, det, bit_depth, det_definition );

    // Not receiving data, and timeout expired.
    if (bpacket.data_len <= 0 && is_timeout_expired(timout, tv_start)) 
    {
      // Flushes the last message, in case the last frame lost packets
      commit_slot(rb_current_slot, rb_writer_id);

      printf("Committed slot %d after timeout in mod_number %d, recv_packets %d\n", rb_current_slot, mod_number, counters.recv_packets);

      break;
    }

    // Acquisition finished.
    if (nframes != -1 && counters.recv_frames >= nframes) 
    {
      // flushes the last message, in case the last frame lost packets
      commit_slot(rb_current_slot, rb_writer_id);

      printf("Committed slot %d in mod_number %d after having received %d frames\n", rb_current_slot, mod_number, counters.recv_frames);

      break;
    }

    // Print statistics every n_frames
    if (counters.recv_frames % PRINT_STATS_N_FRAMES_MODULO == 0 
      && counters.recv_frames != 0 )
    {
      tot_lost_packets += counters.lost_frames;

      // prints out statistics every stats_frames
      int stats_frames = 120;
      stat_total_frames ++;

      if (counters.recv_frames % stats_frames == 0 && counters.recv_frames != 0){
        gettimeofday(&te, NULL);
        tdif = (te.tv_sec - ti.tv_sec) + ((long)(te.tv_usec) - (long)(ti.tv_usec)) / 1e6;
        printf("| %d | %d | %lu | %.2f | %d | %.1f |\n", sched_getcpu(), getpid(), bpacket.framenum, (double) stats_frames / tdif, 
                                                          tot_lost_packets, 100. * (float)tot_lost_packets / (float)(n_packets_per_frame * stat_total_frames));
        //printf("| %d | %lu | %.2f | %d | %.1f |\n", getpid(), framenum_last, (double) stats_frames / tdif, lost_packets, 100. * (float)lost_packets / (float)(128 * stat_total_frames));
        gettimeofday(&ti,NULL);
        stat_total_frames = 0;
      } 
    }

    // Reset timeout timer.
    gettimeofday(&tv_start, NULL);
  } // end while

  return counters.recv_frames;
}
