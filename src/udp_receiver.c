#define _GNU_SOURCE
#include <stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <inttypes.h>
#include <sys/time.h>
#include <ring_buffer.h>
// for uint64 printing
#include <inttypes.h>
// for serveraddr
#include <arpa/inet.h>
#include <sched.h>

#include "detectors.h"
#include "jungfrau.c"
#include "eiger.c"

  /*
  Logic:
    recv_packets ++
    if got_pkg == pred_pkg && last_frame == packet.frame:
      //this is the last packet of the frame
      tot_frames++
      recv_packets = 0
      last_frame = 0 // this will cause getting a new slot afterwards
      commit_flag = true // for committing the slot later

    else if last_frame != packet frame:
      // this means a new frame arrived
      if last_frame == 0:
        // this means prev frame was ok, and no dangling slot exists
        
      else:
        // this means we lost some packets before
        commit dangling slot
        do_stats with recv_packets -1
        recv_packets = 1

      last_frame = packet_frame
      get new slot
    move p1, ph accordingly
    copy to memory
    update counters 

    if commit_flag:
      // this commits the slot when the frame has been succesfully received

      commit slot
      commit_flag = false
commit_flag
  Cases:
    first packet arrives:
      recv_packets ++
      last_frame is 0, it is updated
      new slot is allocated
      data is copied
    last packet arrives, no packets loss:
      recv_packets ++
      tot_frames++
      counters resetted
      last_frame to 0
      data is copied
      slot is committed
    last packet arrives, packets lost:
      case 2: previous slot is committed, stats updated
      last frame updated
      new slot allocated
      data is copied
  */


// unused atm
//#define SERVER_PORT 50001
//#define SERVER_IP "127.0.0.1"
//#define SOCKET_BUFFER_SIZE 4096


// Size of data bytes received in each UDP packet.
#define DATA_BYTES_PER_PACKET    8192

// gap pixels between chips and modules. move this to a struct and pass it as argument

/*
#define GAP_PX_CHIPS_X 2
#define GAP_PX_CHIPS_Y 2
#define GAP_PX_MODULES_X 36
#define GAP_PX_MODULES_Y 8
//#define GAP_PX_MODULES_X 8
//#define GAP_PX_MODULES_Y 36
*/

/*
#define GAP_PX_CHIPS_X 0
#define GAP_PX_CHIPS_Y 0
#define GAP_PX_MODULES_X 0
#define GAP_PX_MODULES_Y 0
*/


// Signature: detector det, int line_number, int n_lines_per_packet, void * p1, void * data, int bit_depth
typedef void (*copy_data_function)(detector, int, int, void*, void*, int);

typedef struct Counter{
  /*
  int total_packets;
  uint64_t framenum_last;
  int total_frames;
  */
  int recv_packets;
  uint64_t current_frame;
  int recv_frames;
  int lost_frames;
} counter;


void initialize_counters(counter *counters, rb_header *ph, int n_packets_per_frame){
  uint64_t ones = ~((uint64_t)0);
  
  if (counters->recv_packets == 1){
    for(int i=0; i < 8; i++) ph->framemetadata[i] = 0;

    ph->framemetadata[2] = ones >> (64 - n_packets_per_frame);
    ph->framemetadata[3] = 0;
    if(n_packets_per_frame > 64)
      ph->framemetadata[3] = ones >> (128 - n_packets_per_frame);
  }
}

int get_udp_packet(int socket_fd, void* buffer, size_t buffer_len) {
  size_t n_bytes = recv(socket_fd, buffer, buffer_len, 0);

  // Did not receive a valid frame packet.
  if (n_bytes != buffer_len) {
    return 0;
  }

  return n_bytes;
}

void copy_data_jungfrau(detector det, int line_number, int n_lines_per_packet, void * p1, void * data, int bit_depth){
  
  int reverse = -1;
  int reverse_factor = det.submodule_size[0] - 1;

  int submodule_line_data_len = (8 * det.submodule_size[1]) / bit_depth;

  int int_line = 0;
  for (int i=line_number + n_lines_per_packet - 1; i >= line_number; i--) {

    long destination_offset = (8 * (reverse_factor + reverse * i) * det.detector_size[1]) / bit_depth;
    long source_offset = (8 * int_line * det.submodule_size[1]) / bit_depth;
    
    //FIXME: would it make sense to do this? Performances issues?
    /*p1 + i * det.detector_size[1],*/
    memcpy((char*)p1 + destination_offset, (char*)data + source_offset, submodule_line_data_len);
                
    int_line++;
  }
}


bool act_on_new_frame(counter *counters, int n_packets_per_frame, barebone_packet *bpacket, 
                      int *rb_current_slot, int rb_writer_id){

  bool commit_flag=false;

    // this fails in case frame number is not updated by the detector (or its simulation)
  if(counters->recv_packets == n_packets_per_frame && bpacket->framenum == counters->current_frame){
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


void update_counters(rb_header * ph, barebone_packet bpacket, int n_packets_per_frame, counter *counters, int mod_number){
  // updating counters
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
  int mod_number, int n_lines_per_packet, int n_packets_per_frame, counter * counters, detector det, int bit_depth, copy_data_function copy_data){

  eiger_packet packet;
  size_t expected_packet_length = sizeof(packet);

  char[expected_packet_length] udp_packet;
  int received_data_len = get_udp_packet(sock, &packet, expected_packet_length);

  #ifdef DEBUG
    if(received_data_len > 0){
      printf("[UDPRECEIVER][%d] nbytes %ld framenum: %lu packetnum: %i\n", getpid(), nbytes, packet->framenum, packet->packetnum);
    }
  #endif

  barebone_packet bpacket = interpret_udp_packet_eiger(&udp_packet, received_data_len)

  // ignoring the special eiger initial packet
  if(received_data_len != expected_packet_length){
    return bpacket;
  }

  counters->recv_packets++;
  bool commit_flag = act_on_new_frame(counters, n_packets_per_frame, &bpacket, rb_current_slot, rb_writer_id);
  
  // Data copy
  // getting the pointers in RB for header and data - must be done after slots are committed / assigned
  rb_header* ph = (rb_header *) rb_get_buffer_slot(rb_hbuffer_id, *rb_current_slot);
  char* p1 = (char *) rb_get_buffer_slot(rb_dbuffer_id, *rb_current_slot);
  // computing the origin and stride of memory locations
  ph += mod_number;

  // Bytes offset in current buffer slot = mod_number * (bytes/pixel)
  p1 += (mod_origin * bit_depth) / 8;

  // initializing - recv_packets already increased above
  if (counters->recv_packets == 1) {
    initialize_counters(counters, ph, n_packets_per_frame);
  }

  // assuming packetnum sequence is 0..N-1
  int line_number = n_lines_per_packet * (n_packets_per_frame - bpacket.packetnum - 1);

  copy_data(det, line_number, n_lines_per_packet, p1, packet.data, bit_depth);

  // updating counters
  update_counters(ph, bpacket, n_packets_per_frame, counters, mod_number);

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

barebone_packet get_put_data_jungfrau(int sock, int rb_hbuffer_id, int *rb_current_slot, int rb_dbuffer_id, int rb_writer_id, uint32_t mod_origin, 
  int mod_number, int n_lines_per_packet, int n_packets_per_frame, counter * counters, detector det, int bit_depth){

  jungfrau_packet packet;
  size_t expected_packet_length = sizeof(packet);
  int data_len = get_udp_packet(sock, &packet, expected_packet_length);

#ifdef DEBUG
  if(data_len > 0){
    printf("[UDPRECEIVER][%d] nbytes %ld framenum: %lu packetnum: %i\n", getpid(), data_len, packet.framenum, packet.packetnum);
  }
#endif

  barebone_packet bpacket;
  bpacket.data_len = data_len;
  bpacket.framenum = packet.metadata.framenum;
  bpacket.packetnum = packet.metadata.packetnum;
  bpacket.bunchid = packet.metadata.bunchid;
  bpacket.debug = packet.metadata.debug;

  // ignoring the special eiger initial packet
  if(data_len != expected_packet_length){
    return bpacket;
  }

  counters->recv_packets++;
  bool commit_flag = act_on_new_frame(counters, n_packets_per_frame, &bpacket, rb_current_slot, rb_writer_id);
  
  // Data copy
  // getting the pointers in RB for header and data - must be done after slots are committed / assigned
  rb_header* ph = (rb_header *) rb_get_buffer_slot(rb_hbuffer_id, *rb_current_slot);
  char* p1 = (char *) rb_get_buffer_slot(rb_dbuffer_id, *rb_current_slot);
  // computing the origin and stride of memory locations
  ph += mod_number;

  // Bytes offset in current buffer slot = mod_number * (bytes/pixel)
  p1 += (mod_origin * bit_depth) / 8;

  // initializing - recv_packets already increased above
  if (counters->recv_packets == 1) {
    initialize_counters(counters, ph, n_packets_per_frame);
  }

  // assuming packetnum sequence is 0..N-1
  int line_number = n_lines_per_packet * (n_packets_per_frame - bpacket.packetnum - 1);
  
  copy_data_jungfrau(det, line_number, n_lines_per_packet, p1, packet.data, bit_depth);
  
  // updating counters
  update_counters(ph, bpacket, n_packets_per_frame, counters, mod_number);

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
  
  //printf("%s %d\n", det.detector_name, det.detector_size[0]);

  int stat_total_frames = 0;
  int tot_lost_packets = 0;
  
  barebone_packet bpacket;
  
  struct  timeval ti, te; //for timing
  double tdif=-1;

  int data_bytes_per_packet = DATA_BYTES_PER_PACKET;

  if(strcmp(det.detector_name, "EIGER") == 0){
    data_bytes_per_packet = DATA_BYTES_PER_PACKET / 2;
  }

  // (Bytes in packet) / (Bytes in submodule line)
  int n_lines_per_packet = 8 * data_bytes_per_packet / (bit_depth * det.submodule_size[1]);

  counter counters;

  counters.current_frame = 0;
  counters.recv_frames = 0;

  // Origin of the module within the detector, (0, 0) is bottom left
  uint32_t mod_origin = det.detector_size[1] * det.module_idx[0] * det.module_size[0] + det.module_idx[1] * det.module_size[1];
  mod_origin += det.module_idx[1] * ((det.submodule_n - 1) * det.gap_px_chips[1] + det.gap_px_modules[1]); // inter_chip gaps plus inter_module gap
  mod_origin += det.module_idx[0] * (det.gap_px_chips[0] + det.gap_px_modules[0])* det.detector_size[1] ; // inter_chip gaps plus inter_module gap

  // Origin of the submodule within the detector, relative to module origin
  mod_origin += det.detector_size[1] * det.submodule_idx[0] * det.submodule_size[0] + det.submodule_idx[1] * det.submodule_size[1];
  if(det.submodule_idx[1] != 0)
    mod_origin += 2 * det.gap_px_chips[1];  // 2* because there is the inter-quartermodule chip gap //GAP_PX_CHIPS_Y * submod_idx[1]; // the last takes into account extra space for chip gap within quarter module
  if(det.submodule_idx[0] != 0)
    mod_origin += det.submodule_idx[0] * det.detector_size[1] * det.gap_px_chips[0];

  int mod_number = det.submodule_idx[0] * 2 + det.submodule_idx[1] + 
    det.submodule_n * (det.module_idx[1] + det.module_idx[0] * det.detector_size[1] / det.module_size[1]); //numbering inside the detctor, growing over the x-axis

  // (Pixels in submodule) * (bytes per pixel) / (bytes per packet)
  int n_packets_per_frame = det.submodule_size[0] * det.submodule_size[1] / (8 * data_bytes_per_packet / bit_depth);
  bpacket.data_len = 0;

  // Timeout for blocking sock recv
  struct timeval tv;
  tv.tv_sec = 0;
  tv.tv_usec = 50;
  setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof(struct timeval));

  // Timeout for receiving packets
  struct timeval tv_start, tv_end;
  double timeout_i = 0;

  gettimeofday(&tv_start, NULL);

  //printf("[UDPRECEIVER][%d] entered at %.3f s slot %d\n", getpid(), (double)(tv_start.tv_usec) / 1e6 + (double)(tv_start.tv_sec), rb_current_slot);
  // infinite loop, with timeout

  
  while(true){

    if(nframes != -1)
      if(counters.recv_frames >= nframes){
        // not clear if this is needed
        // flushes the last message, in case the last frame lost packets
        if(rb_current_slot != -1){
          rb_commit_slot(rb_writer_id, rb_current_slot);
          printf("Committed slot %d in mod_number %d after having received %d frames\n", rb_current_slot, mod_number, counters.recv_frames);
        }
      return counters.recv_frames;
      }

    if (bit_depth != 16 && bit_depth != 32) {
      printf("[UDP_RECEIVER][%d] Please setup bit_depth to 16 or 32.\n", getpid());
      return counters.recv_frames;
    }
   
    // get data and copy to RB
    if (strcmp(det.detector_name, "EIGER") == 0) {

      bpacket = get_put_data(sock, rb_hbuffer_id, &rb_current_slot, rb_dbuffer_id, rb_writer_id, mod_origin, mod_number,
			  n_lines_per_packet, n_packets_per_frame, &counters, det, bit_depth, copy_data_eiger);

    } else if (strcmp(det.detector_name, "JUNGFRAU") == 0) {
      bpacket = get_put_data_jungfrau(sock, rb_hbuffer_id, &rb_current_slot, rb_dbuffer_id, rb_writer_id, mod_origin, mod_number,
        n_lines_per_packet, n_packets_per_frame, &counters, det, bit_depth);

    } else {
      printf("[UDP_RECEIVER][%d] Please setup detector_name to EIGER or JUNGFRAU.\n", getpid());
      return counters.recv_frames;
    }
    
    // no data? Checks timeout
    if(bpacket.data_len <= 0){
      gettimeofday(&tv_end, NULL);
      timeout_i = (double)(tv_end.tv_usec - tv_start.tv_usec) / 1e6 + (double)(tv_end.tv_sec - tv_start.tv_sec);

      if (timeout_i > (double)timeout){
        // flushes the last message, in case the last frame lost packets
        //printf("breaking timeout after %f ms\n", timeout_i);
        #ifdef DEBUG
          printf("[UDPRECEIVER][%d] left at %.3f s slot %d for mod_number %d\n", getpid(), (double)(tv_end.tv_usec) / 1e6 + (double)(tv_end.tv_sec), rb_current_slot, mod_number);
        #endif
        if(rb_current_slot != -1){
          rb_commit_slot(rb_writer_id, rb_current_slot);
          printf("Committed slot %d after timeout in mod_number %d, recv_packets %d\n", rb_current_slot, mod_number, counters.recv_packets);
        }
        return counters.recv_frames;
      }
      continue;
    }

    gettimeofday(&tv_start, NULL);

    //this means a new frame, but only for Eiger. Possibly it will be removed
    if(counters.current_frame == 0 && bpacket.data_len > 0){
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
    } // end new frame if
      
  } // end while
  return counters.recv_frames;
}



//test function
/*
int main(){
	int ret;
	struct sockaddr_in serveraddr;
	int sd = socket(AF_INET, SOCK_DGRAM, 0);
	printf("SD: %d\n", sd);

	int   val=SOCKET_BUFFER_SIZE;
	setsockopt(sd, SOL_SOCKET, SO_RCVBUF, &val, sizeof(int));
	
	if (sd < 0){
	  perror("socket() failed");
	  return -1;
	}
	
	memset(&serveraddr, 0, sizeof(serveraddr));
	serveraddr.sin_family      = AF_INET;
	serveraddr.sin_port        = htons(SERVER_PORT);
	serveraddr.sin_addr.s_addr = inet_addr(SERVER_IP);
	
	int rc = bind(sd, (struct sockaddr *)&serveraddr, sizeof(serveraddr));
	printf("RC bind: %d\n", rc);
	//ret = setsockopt(socket, SOL_SOCKET, SO_RCVBUF, &val, sizeof(int));
	//printf("%d\n", ret);

	int32_t idx[256*256];
	int i;
	for(i=0; i<256*256; i++)
	  idx[i] = i;
	//eiger_packet16 packet;
	void * packet;
	while(1)
	  put_udp_in_rb(sd, 16, 0, 0, 0, 0, 0, idx);
			//get_message16(sd, &packet);
}

*/
