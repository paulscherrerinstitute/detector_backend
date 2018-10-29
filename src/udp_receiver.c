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


// uncomment if you want to acquire data with the old UDP header
//#define OLD_HEADER 1

// unused atm
//#define SERVER_PORT 50001
//#define SERVER_IP "127.0.0.1"
//#define SOCKET_BUFFER_SIZE 4096

// Foreseen packet sizes
#ifdef OLD_HEADER
#define HEADER_PACKET_SIZE 48
#define PACKET_LENGTH 4112
#endif
#ifndef OLD_HEADER
#define HEADER_PACKET_SIZE 40
#define PACKET_LENGTH 4144
#endif

// size of the data buffer, in bytes
#define BUFFER_LENGTH    8192

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
// only needed for the old UDP eader
#ifdef OLD_HEADER
typedef struct uint48 {
	unsigned long long v:48;
} __attribute__((packed)) uint48;
#endif


// the essential info needed for a packet
typedef struct _barebone_packet{
  int data_len;
#ifdef OLD_HEADER
  uint16_t packetnum;
#endif
#ifndef OLD_HEADER
  uint32_t packetnum;
#endif
  uint64_t framenum;
  double bunchid;
  uint32_t debug;
} barebone_packet;


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


void initialize_counters(counter *counters, rb_header *ph, int packets_frame){
  uint64_t ones = ~((uint64_t)0);

  if (counters->recv_packets == 1){
    for(int i=0; i < 8; i++) ph->framemetadata[i] = 0;

    ph->framemetadata[2] = ones >> (64 - packets_frame);
    ph->framemetadata[3] = 0;
    if(packets_frame > 64)
      ph->framemetadata[3] = ones >> (128 - packets_frame);
  }
}

int jungfrau_get_message16(int sd, jungfrau_packet16 * packet){
  //jungfrau_packet16 * tp = (jungfrau_packet16*) packet;
  ssize_t nbytes = recv(sd, packet, sizeof(*packet), 0); //MSG_DONTWAIT);

  //printf("%ld %ld\n", nbytes, sizeof(*(jungfrau_packet16*)packet));
 #ifdef DEBUG
  if(nbytes > 0){
    printf("[UDPRECEIVER][%d] nbytes %ld framenum: %lu packetnum: %i\n", getpid(), nbytes, ((jungfrau_packet16*)packet)->framenum, ((jungfrau_packet16*)packet)->packetnum);
  }
  #endif

  return nbytes;
}


//simple routines to get data from UDP socket
int get_message8(int sd, eiger_packet8 * packet){
  ssize_t nbytes = recv(sd, packet, sizeof(*packet), 0);
  if(nbytes != PACKET_LENGTH && nbytes != HEADER_PACKET_SIZE)
    return 0;
  
#ifdef DEBUG
  if(nbytes > HEADER_PACKET_SIZE){
    printf("[UDPRECEIVER][%d] framenum: %lu packetnum: %i\n", getpid(), packet->framenum, packet->packetnum);
  }
#endif
  return nbytes;
}

int get_message16(int sd, eiger_packet16 * packet){
  ssize_t nbytes = recv(sd, packet, sizeof(*packet), 0); //MSG_DONTWAIT);

  //discard incomplete data
  //if(nbytes != PACKET_LENGTH && nbytes != HEADER_PACKET_SIZE)
  //  return 0;

#ifdef OLD_HEADER
  packet->framenum = (unsigned long long) packet->framenum2.v;
#endif

 #ifdef DEBUG
  if(nbytes > 0){
    printf("[UDPRECEIVER][%d] nbytes %ld framenum: %lu packetnum: %i\n", getpid(), nbytes, packet->framenum, packet->packetnum);
  }
 #endif

  return nbytes;
}

int get_message32(int sd, eiger_packet32 * packet){
  ssize_t nbytes = recv(sd, packet, sizeof(*packet), 0);
  if(nbytes != PACKET_LENGTH && nbytes != HEADER_PACKET_SIZE)
    return 0;
    
#ifdef DEBUG
  if(nbytes > HEADER_PACKET_SIZE){
    printf("[UDPRECEIVER][%d] framenum: %lu packetnum: %i\n", getpid(), packet->framenum, packet->packetnum);
  }
#endif
  return nbytes;
}


void copy_data(detector det, int line_number, int lines_per_packet, void * p1, void * data, int bit_depth, int reverse){
  int int_line = 0;
  int data_len = 0;
  int reverse_factor = 0;

  if(reverse == -1)
    reverse_factor = det.submodule_size[0] - 1;

  if (bit_depth == 16) {
    data_len = det.submodule_size[1] * sizeof(int16_t);

    if(det.submodule_n == 4){
      for(int i=line_number + lines_per_packet - 1; i >= line_number; i--){

        memcpy((uint16_t *) p1 + (reverse_factor + reverse * i) * det.detector_size[1],
          (uint16_t *) data + int_line * det.submodule_size[1], data_len / 2);
        memcpy((uint16_t *)p1 + (reverse_factor + reverse * i) * det.detector_size[1] + det.gap_px_chips[1] + det.submodule_size[1] / 2,
          (uint16_t *)data + int_line * det.submodule_size[1] + det.submodule_size[1] / 2, data_len / 2);
        int_line ++;
        }
    }
    else{
      for(int i=line_number + lines_per_packet - 1; i >= line_number; i--){
        memcpy(
              ((uint16_t *)p1) + (reverse_factor + reverse * i) * det.detector_size[1],
          //FIXME: would it make sense to do this? Performances issues?
              /*p1 + i * det.detector_size[1],*/
              ((uint16_t *)data) + int_line * det.submodule_size[1], data_len);
        int_line ++;
      }
    } // end submodule
  }// end bit_length
}


bool act_on_new_frame(counter *counters, int packets_frame, barebone_packet *bpacket, 
                      int *rb_current_slot, int rb_writer_id){

  bool commit_flag=false;

    // this fails in case frame number is not updated by the detector (or its simulation)
  if(counters->recv_packets == packets_frame && bpacket->framenum == counters->current_frame){
    //this is the last packet of the frame
#ifdef DEBUG
    printf("[UDPRECV] Frame complete, got packet %d  #%d of %d frame %lu / %lu\n", bpacket->packetnum, counters->recv_packets, 
                                                                    packets_frame, bpacket->framenum, counters->current_frame);
#endif

    counters->recv_frames++;
    //counters->recv_packets = 0;
    counters->current_frame = 0; // this will cause getting a new slot afterwards
    commit_flag = true; // for committing the slot later
    counters->lost_frames = 0;
  }
  // this means we are in a new frame (first one included)
  else if (counters->current_frame != bpacket->framenum){        
    if(counters->recv_packets != packets_frame && counters->recv_packets != 1){
      // this means we lost some packets before, and we have a dangling slot. Current frame is set to 0 when a complete frame is committed
      if(counters->current_frame != 0){
        if(*rb_current_slot != -1){
          // add some checks here
          rb_commit_slot(rb_writer_id, *rb_current_slot);
        }
        else
          printf("[ERROR] I should have been committing a dangling slot, but it is -1\n");

        //do_stats with recv_packets -1
        counters->lost_frames = packets_frame - (counters->recv_packets - 1);
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


void update_counters(rb_header * ph, barebone_packet bpacket, int packets_frame, counter *counters, int mod_number){
  // updating counters
  ph->framemetadata[0] = bpacket.framenum; // this could be avoided mayne
  ph->framemetadata[1] = packets_frame - counters->recv_packets;
    
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


barebone_packet get_put_data_eiger16(int sock, int rb_hbuffer_id, int *rb_current_slot, int rb_dbuffer_id, int rb_writer_id, uint32_t mod_origin, 
  int mod_number, int lines_per_packet, int packets_frame, counter * counters, detector det){
  // if less than this, drop the packet
  int packet_length = 4144;
  /*!
    gets the packet data and put it in the correct memory place in the RingBuffer
   */
  rb_header * ph;

  uint16_t * p1;
  int data_len = 0;
  int line_number;
  bool commit_flag = false;

  // can pass a void pointer, and dereference in the memory copy - useful?
  uint16_t * data;
  barebone_packet bpacket;
  eiger_packet16 packet_eiger;

  data_len = get_message16(sock, &packet_eiger);
  bpacket.data_len = data_len;
  bpacket.framenum = packet_eiger.framenum;
  bpacket.packetnum = packet_eiger.packetnum;
  // the following two are not needed for Eiger
  //bpacket.bunchid = packet_eiger.bunchid;
  //bpacket.debug = packet_eiger.debug;  
  data = (uint16_t *)packet_eiger.data;

  // ignoring the special eiger initial packet
  if(data_len != packet_length){
    return bpacket;
  }

  counters->recv_packets++;
  commit_flag = act_on_new_frame(counters, packets_frame, &bpacket, rb_current_slot, rb_writer_id);
  // Data copy
  // getting the pointers in RB for header and data - must be done after slots are committed / assigned
  ph = (rb_header *) rb_get_buffer_slot(rb_hbuffer_id, *rb_current_slot);
  p1 = (uint16_t *) rb_get_buffer_slot(rb_dbuffer_id, *rb_current_slot);
  // computing the origin and stride of memory locations
  ph += mod_number;
  p1 += mod_origin;

    // assuming packetnum sequence is 1..N
#ifdef OLD_HEADER
  line_number = lines_per_packet * (packets_frame - packet.packetnum);
#endif
#ifndef OLD_HEADER
  // assuming packetnum sequence is 0..N-1
  line_number = lines_per_packet * (packets_frame - bpacket.packetnum - 1);
#endif

  // initializing - recv_packets already increased above
  initialize_counters(counters, ph, packets_frame);
  
  // First half (up)
  // notice this is reversed wrt jungfrau
  if((det.submodule_idx[0] == 0 && det.submodule_idx[1] == 0) ||
      (det.submodule_idx[0] == 0 && det.submodule_idx[1] == 1)){
      copy_data(det, line_number, lines_per_packet, p1, data, 16, 1);
  }
  // the other half
  else{
      copy_data(det, line_number, lines_per_packet, p1, data, 16, -1);
  }

  // updating counters
  update_counters(ph, bpacket, packets_frame, counters, mod_number);

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


barebone_packet get_put_data_jf16(int sock, int rb_hbuffer_id, int *rb_current_slot, int rb_dbuffer_id, int rb_writer_id, uint32_t mod_origin, 
  int mod_number, int lines_per_packet, int packets_frame, counter * counters, detector det){
  /*!
    gets the packet data and put it in the correct memory place in the RingBuffer
   */
  rb_header * ph;

  uint16_t * p1;
  int data_len = 0;
  int line_number;
  bool commit_flag = false;
  //int packet_length = 8246;

  // can pass a void pointer, and dereference in the memory copy - useful?
  uint16_t * data;
  barebone_packet bpacket;
  jungfrau_packet16 packet_jungfrau;

  data_len = jungfrau_get_message16(sock, &packet_jungfrau);
  bpacket.data_len = data_len;
  bpacket.framenum = packet_jungfrau.framenum;
  bpacket.packetnum = packet_jungfrau.packetnum;
  bpacket.bunchid = packet_jungfrau.bunchid;
  bpacket.debug = packet_jungfrau.debug;
  data = (uint16_t *)packet_jungfrau.data;

  // ignoring the special eiger initial packet
  if(data_len <= 0){
    return bpacket;
  }

  counters->recv_packets++;
  commit_flag = act_on_new_frame(counters, packets_frame, &bpacket, rb_current_slot, rb_writer_id);
  // Data copy
  // getting the pointers in RB for header and data - must be done after slots are committed / assigned
  ph = (rb_header *) rb_get_buffer_slot(rb_hbuffer_id, *rb_current_slot);
  p1 = (uint16_t *) rb_get_buffer_slot(rb_dbuffer_id, *rb_current_slot);
  // computing the origin and stride of memory locations
  ph += mod_number;
  p1 += mod_origin;

    // assuming packetnum sequence is 1..N
#ifdef OLD_HEADER
  line_number = lines_per_packet * (packets_frame - packet.packetnum);
#endif
#ifndef OLD_HEADER
  // assuming packetnum sequence is 0..N-1
  line_number = lines_per_packet * (packets_frame - bpacket.packetnum - 1);
#endif

  // initializing - recv_packets already increased above
  initialize_counters(counters, ph, packets_frame);
  copy_data(det, line_number, lines_per_packet, p1, data, 16, -1);
  
  // updating counters
  update_counters(ph, bpacket, packets_frame, counters, mod_number);

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
  int packets_frame;
  
  struct  timeval ti, te; //for timing
  double tdif=-1;

  int buffer_length = BUFFER_LENGTH;

  if(strcmp(det.detector_name, "EIGER") == 0){
    buffer_length = BUFFER_LENGTH / 2;
  }


  int lines_per_packet = 8 * buffer_length / (bit_depth * det.submodule_size[1]);
  //int lines_per_packet = BUFFER_LENGTH / det.module_size[1];

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

  packets_frame = det.submodule_size[0] * det.submodule_size[1] / (8 * buffer_length / bit_depth);
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

  printf("[UDPRECEIVER][%d] entered at %.3f s slot %d\n", getpid(), (double)(tv_start.tv_usec) / 1e6 + (double)(tv_start.tv_sec), rb_current_slot);
  // infinite loop, with timeout

  
  while(true){

    if(nframes != -1)
      if(counters.recv_frames >= nframes){
        // not clear if this is needed
        // flushes the last message, in case the last frame lost packets
        if(rb_current_slot != -1){
          rb_commit_slot(rb_writer_id, rb_current_slot);
          printf("Committed slot %d after having received %d frames\n", rb_current_slot, counters.recv_frames);
        }
      return counters.recv_frames;
      }
   
    // get data and copy to RB
  /*
    if(bit_depth == 8)
      bpacket = get_put_data8(sock, rb_hbuffer_id, &rb_current_slot, rb_dbuffer_id, rb_writer_id, mod_origin,
			     lines_per_packet, packets_frame, det_size, submod_size, submod_idx);
    else if(bit_depth == 16){
      */
     if (strcmp(det.detector_name, "JUNGFRAU") == 0)
        bpacket = get_put_data_jf16(sock, rb_hbuffer_id, &rb_current_slot, rb_dbuffer_id, rb_writer_id, mod_origin, mod_number,
			       lines_per_packet, packets_frame, &counters, det);
     else if (strcmp(det.detector_name, "EIGER") == 0){
        bpacket = get_put_data_eiger16(sock, rb_hbuffer_id, &rb_current_slot, rb_dbuffer_id, rb_writer_id, mod_origin, mod_number,
			       lines_per_packet, packets_frame, &counters, det);
     }
  /*}
    else if(bit_depth == 32)
      bpacket = get_put_data32(sock, rb_hbuffer_id, &rb_current_slot, rb_dbuffer_id, rb_writer_id, mod_origin,
			     lines_per_packet, packets_frame, det_size, submod_size, submod_idx);
    else{
      printf("[UDP_RECEIVER][%d] please set up a bit_depth", getpid());
      return counters.recv_frames;
    }
*/
    // no data? Checks timeout
    if(bpacket.data_len <= 0){
      gettimeofday(&tv_end, NULL);
      timeout_i = (double)(tv_end.tv_usec - tv_start.tv_usec) / 1e6 + (double)(tv_end.tv_sec - tv_start.tv_sec);

      if (timeout_i > (double)timeout){
        // flushes the last message, in case the last frame lost packets
        //printf("breaking timeout after %f ms\n", timeout_i);
        printf("[UDPRECEIVER][%d] left at %.3f s slot %d\n", getpid(), (double)(tv_end.tv_usec) / 1e6 + (double)(tv_end.tv_sec), 
                                                            rb_current_slot);

        if(rb_current_slot != -1){
          rb_commit_slot(rb_writer_id, rb_current_slot);
          printf("Committed slot %d after timeout\n", rb_current_slot);
        }
        return counters.recv_frames;
      }
      continue;
    }

    gettimeofday(&tv_start, NULL);

    //this means a new frame, but only for Eiger. Possibly it will be removed
    if(counters.current_frame == 0 && bpacket.data_len != HEADER_PACKET_SIZE){
      tot_lost_packets += counters.lost_frames;
      // prints out statistics every stats_frames
      int stats_frames = 100;
      stat_total_frames ++;

      if (counters.recv_frames % stats_frames == 0 && counters.recv_frames != 0){
        gettimeofday(&te, NULL);
        tdif = (te.tv_sec - ti.tv_sec) + ((long)(te.tv_usec) - (long)(ti.tv_usec)) / 1e6;
        printf("| %d | %d | %lu | %.2f | %d | %.1f |\n", sched_getcpu(), getpid(), bpacket.framenum, (double) stats_frames / tdif, 
                                                          tot_lost_packets, 100. * (float)tot_lost_packets / (float)(packets_frame * stat_total_frames));
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
