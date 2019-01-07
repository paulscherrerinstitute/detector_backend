#include <inttypes.h>
#include <stddef.h>
#include <stdbool.h>

#include "detectors.h"

inline uint32_t get_current_module_offset_in_pixels (detector det)
{
  // Origin of the module within the detector, (0, 0) is bottom left
  uint32_t mod_origin = det.detector_size[1] * det.module_idx[0] * det.module_size[0] + det.module_idx[1] * det.module_size[1];
  mod_origin += det.module_idx[1] * ((det.submodule_n - 1) * det.gap_px_chips[1] + det.gap_px_modules[1]); // inter_chip gaps plus inter_module gap
  mod_origin += det.module_idx[0] * (det.gap_px_chips[0] + det.gap_px_modules[0])* det.detector_size[1] ; // inter_chip gaps plus inter_module gap

  // Origin of the submodule within the detector, relative to module origin
  mod_origin += det.detector_size[1] * det.submodule_idx[0] * det.submodule_size[0] + det.submodule_idx[1] * det.submodule_size[1];
  
  if(det.submodule_idx[1] != 0)
  {
    // 2* because there is the inter-quartermodule chip gap
    mod_origin += 2 * det.gap_px_chips[1];   
  }

  // the last takes into account extra space for chip gap within quarter module
  if(det.submodule_idx[0] != 0)
  {
    mod_origin += det.submodule_idx[0] * det.detector_size[1] * det.gap_px_chips[0];
  }

  return mod_origin;
}

inline int get_current_module_index (detector det)
{
  //numbering inside the detctor, growing over the x-axiss
  int mod_number = det.submodule_idx[0] * 2 + det.submodule_idx[1] + 
    det.submodule_n * (det.module_idx[1] + det.module_idx[0] * det.detector_size[1] / det.module_size[1]); 

  return mod_number;
}

inline int get_n_packets_per_frame (detector det, size_t data_bytes_per_packet, int bit_depth)
{
  // (Pixels in submodule) * (bytes per pixel) / (bytes per packet)
  return det.submodule_size[0] * det.submodule_size[1] / (8 * data_bytes_per_packet / bit_depth);
}

inline int get_n_lines_per_packet (detector det, size_t data_bytes_per_packet, int bit_depth)
{
  // (Bytes in packet) / (Bytes in submodule line)
  return 8 * data_bytes_per_packet / (bit_depth * det.submodule_size[1]);
}

inline bool is_timeout_expired (double timeout, struct timeval timeout_start_time)
{
  struct timeval current_time;
  gettimeofday(&current_time, NULL);

  double timeout_i = (double)(current_time.tv_usec - timeout_start_time.tv_usec) / 1e6 
    + (double)(current_time.tv_sec - timeout_start_time.tv_sec);

  return timeout_i > timeout;
}

inline int get_udp_packet (int socket_fd, void* buffer, size_t buffer_len) 
{
  size_t n_bytes = recv(socket_fd, buffer, buffer_len, 0);

  // Did not receive a valid frame packet.
  if (n_bytes != buffer_len) {
    return 0;
  }

  return n_bytes;
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

inline void initialize_rb_header (rb_header *ph, int n_packets_per_frame)
{
  uint64_t ones = ~((uint64_t)0);
  
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

inline void update_rb_header (
  rb_header * ph, 
  barebone_packet bpacket, 
  int n_packets_per_frame, 
  counter *counters, 
  int mod_number )
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

inline void print_statistics (counter* counters, struct timeval last_stats_print_time)
{
  struct timeval current_time;
  gettimeofday(&current_time, NULL);

  double elapsed_seconds = (current_time.tv_sec - last_stats_print_time.tv_sec) + 
    ((long)(current_time.tv_usec) - (long)(last_stats_print_time.tv_usec)) / 1e6;

  double frame_rate = (double) PRINT_STATS_N_FRAMES_MODULO / elapsed_seconds;

  float percentage_lost_packets = 100. * (float)counters->total_lost_packets / 
    (float)(counters->total_recv_packets);

  // CPU | pid | framenum | frame_rate | tot_lost_packets | % lost packets |
  printf(
    "| %d | %d | %lu | %.2f | %lu | %.1f |\n", 
    sched_getcpu(), getpid(), counters->current_frame, frame_rate, 
    counters->total_lost_packets, percentage_lost_packets
  );
}
