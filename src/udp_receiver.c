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
#define BUFFER_LENGTH    4096
// size of the quarter module, in pixels
//#define YSIZE 512
//#define XSIZE 256


// gap pixels between chips and modules. move this to a struct and pass it as argument

/*
#define GAP_PX_CHIPS_X 2
#define GAP_PX_CHIPS_Y 2
#define GAP_PX_MODULES_X 36
#define GAP_PX_MODULES_Y 8
//#define GAP_PX_MODULES_X 8
//#define GAP_PX_MODULES_Y 36
*/

#define GAP_PX_CHIPS_X 0
#define GAP_PX_CHIPS_Y 0
#define GAP_PX_MODULES_X 0
#define GAP_PX_MODULES_Y 0

// only needed for the old UDP eader
#ifdef OLD_HEADER
typedef struct uint48 {
	unsigned long long v:48;
} __attribute__((packed)) uint48;
#endif

// header struct for RB - to be updated to include the framenums of all modules

typedef struct _detector{
  char detector_name[10];
  uint8_t submodule_n;
  int32_t detector_size[2]; 
  int32_t module_size[2]; 
  int32_t submodule_size[2]; 
  int32_t module_idx[2]; 
  int32_t submodule_idx[2];

} detector;

typedef struct _eiger_header{
  // Field 0: frame number
  // Field 1: packets lost
  // Field 2: packets counter 0-63
  // Field 3: packets counter 64-127
  // Field 4: pulse id
  // Field 5: debug (daq_rec) - gain flag
  uint64_t framemetadata[8];
} eiger_header;

/*
typedef struct _eiger_header{
  uint64_t framenum;
  uint16_t packetnum;
  int8_t padding[64 - 8 - 1];
} eiger_header;
*/

#pragma pack(push)
#pragma pack(2)
typedef struct _jungfrau_packet16{
//Jungfrau
  char emptyheader[6];
  uint64_t framenum;
  uint32_t exptime;
  uint32_t packetnum;
  //uint64_t bunchid;
  double bunchid;
  uint64_t timestamp;
  uint16_t moduleID;
  uint16_t xCoord;
  uint16_t yCoord;
  uint16_t zCoord;
  uint32_t debug;
  uint16_t roundRobin;
  uint8_t detectortype;
  uint8_t headerVersion;
  uint16_t data[4096];
} jungfrau_packet16;
#pragma pack(pop)


// various structs for eiger packets, one per bit dept
// 4bits still unsupported!
typedef struct _eiger_packet8{
  uint64_t framenum;
  uint32_t exptime;
  uint32_t packetnum;
  uint64_t bunchid;
  uint64_t timestamp;
  uint16_t moduleID;
  uint16_t xCoord;
  uint16_t yCoord;
  uint16_t zCoord;
  uint32_t debug;
  uint16_t roundRobin;
  uint8_t detectortype;
  uint8_t headerVersion;
  uint8_t data[4096];
} eiger_packet8;

typedef struct _eiger_packet16{
#ifdef OLD_HEADER
  uint32_t subframenum;
  uint16_t internal1;
  uint8_t memaddress;
  uint8_t internal2;
  uint16_t data[2048];
  uint48 framenum2;
  uint16_t packetnum;
  uint64_t framenum;
#endif
#ifndef OLD_HEADER
  uint64_t framenum;
  uint32_t exptime;
  uint32_t packetnum;
  uint64_t bunchid;
  uint64_t timestamp;
  uint16_t moduleID;
  uint16_t xCoord;
  uint16_t yCoord;
  uint16_t zCoord;
  uint32_t debug;
  uint16_t roundRobin;
  uint8_t detectortype;
  uint8_t headerVersion;
  uint16_t data[2048];
#endif
} eiger_packet16;


typedef struct _eiger_packet32{
  uint64_t framenum;
  uint32_t exptime;
  uint32_t packetnum;
  uint64_t bunchid;
  uint64_t timestamp;
  uint16_t moduleID;
  uint16_t xCoord;
  uint16_t yCoord;
  uint16_t zCoord;
  uint32_t debug;
  uint16_t roundRobin;
  uint8_t detectortype;
  uint8_t headerVersion;
  uint32_t data[1024];
} eiger_packet32;

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
    printf("[UDPRECEIVER][%d] framenum: %llu packetnum: %i\n", getpid(), packet->framenum, packet->packetnum);
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

 //#ifdef DEBUG
  if(nbytes > 0){
    printf("[UDPRECEIVER][%d] nbytes %ld framenum: %lu packetnum: %i\n", getpid(), nbytes, packet->framenum, packet->packetnum);
  }
  //#endif

  return nbytes;
}

int get_message32(int sd, eiger_packet32 * packet){
  ssize_t nbytes = recv(sd, packet, sizeof(*packet), 0);
  if(nbytes != PACKET_LENGTH && nbytes != HEADER_PACKET_SIZE)
    return 0;
    
#ifdef DEBUG
  if(nbytes > HEADER_PACKET_SIZE){
    printf("[UDPRECEIVER][%d] framenum: %llu packetnum: %i\n", getpid(), packet->framenum, packet->packetnum);
  }
#endif
  return nbytes;
}


barebone_packet get_put_data8(int sock, int rb_hbuffer_id, int *rb_current_slot, int rb_dbuffer_id, int rb_writer_id, uint32_t mod_origin,int lines_per_packet, int packets_frame, int32_t *det_size, int32_t *submod_size, int32_t *submod_idx){
  /*!
    gets the packet data and put it in the correct memory place in the RingBuffer
   */
  eiger_packet8 packet;
  eiger_header * ph;
  eiger_header header;

  uint8_t * p1;
  int data_len;
  int int_line = 0;
  int line_number;
  int i;

  barebone_packet bpacket;
  
  data_len = get_message8(sock, &packet);
  bpacket.data_len = data_len;

  if(data_len > HEADER_PACKET_SIZE){
    if(*rb_current_slot == -1)
      while(*rb_current_slot == -1){
	*rb_current_slot = rb_claim_next_slot(rb_writer_id);
	//printf("%d\n", *rb_current_slot);
      }
    bpacket.framenum = packet.framenum;
    bpacket.packetnum = packet.packetnum;

    // Data copy
    // getting the pointers in RB for header and data
    ph = (eiger_header *) rb_get_buffer_slot(rb_hbuffer_id, *rb_current_slot);
    p1 = (uint8_t *) rb_get_buffer_slot(rb_dbuffer_id, *rb_current_slot);

    // computing the origin and stride of memory locations
    p1 += mod_origin;
    // assuming packetnum sequence is 1..N
    // assuming packetnum sequence is 0..N-1
    line_number = lines_per_packet * (packets_frame - packet.packetnum - 1);

    // First half (up)
    if((submod_idx[0] == 0 && submod_idx[1] == 0) ||
       (submod_idx[0] == 0 && submod_idx[1] == 1)){
      for(i=line_number + lines_per_packet - 1; i >= line_number; i--){
	//printf("bottom1: %d\n", i * det_size[1]);
	memcpy(p1 + i * det_size[1],
	       packet.data + int_line * submod_size[1],
	       submod_size[1] * sizeof(int8_t) / 2);

	//printf("bottom2: %d\n", i * det_size[1] + GAP_PX_CHIPS_Y + submod_size[1] / 2);
	memcpy(p1 + i * det_size[1] + GAP_PX_CHIPS_Y + submod_size[1] / 2,
	       packet.data + int_line * submod_size[1] + submod_size[1] / 2,
	       submod_size[1] * sizeof(int8_t) / 2);
	int_line ++;
      }
    }
    // the other half
    else{
      for(i=line_number + lines_per_packet - 1; i >= line_number; i--){
	//printf("up1 %d %d %d %d %d\n", (255 - i) * det_size[1], i, det_size[1], line_number, lines_per_packet);

	// TODO remove the hardcoded 255
	memcpy(p1 + (255 - i) * det_size[1],
	       packet.data + int_line * submod_size[1],
	       submod_size[1] * sizeof(int8_t) / 2);
	//printf("up2 %d\n", (255 - i) * det_size[1] + GAP_PX_CHIPS_Y + submod_size[1] / 2);
	memcpy(p1 + (255 - i) * det_size[1] + GAP_PX_CHIPS_Y + submod_size[1] / 2,
	       packet.data + int_line * submod_size[1] + submod_size[1] / 2,
	       submod_size[1] * sizeof(int8_t) / 2);
	int_line ++;
      }
    }

    /*
    header.framenum = packet.framenum;
      
    if(ph->framenum != packet.framenum){
      memcpy(ph, &header, sizeof(header));
    }
    */
  }

  return bpacket;
}



barebone_packet get_put_data16(int sock, int rb_hbuffer_id, int *rb_current_slot, int rb_dbuffer_id, int rb_writer_id, uint32_t mod_origin, 
  int mod_number, int lines_per_packet, int packets_frame, counter * counters, detector det, void * packet){
  /*!
    gets the packet data and put it in the correct memory place in the RingBuffer
   */
  //jungfrau_packet16 packet;
  //void * packet;
  eiger_header * ph;
  //eiger_header header;

  uint16_t * p1;
  int data_len = 0;
  int int_line = 0;
  int line_number;
  int i;
  bool commit_flag = false;

  // can pass a void pointer, and dereference in the memory copy - useful?
  uint16_t * data;
  
  barebone_packet bpacket;
  uint64_t ones = ~((uint64_t)0);
  
  if (strcmp(det.detector_name, "JUNGFRAU") == 0){
    data_len = jungfrau_get_message16(sock, (jungfrau_packet16*)packet);
    bpacket.data_len = data_len;
    bpacket.framenum = ((jungfrau_packet16 *) packet)->framenum;
    bpacket.packetnum = ((jungfrau_packet16 *) packet)->packetnum;
    data = (uint16_t *)((jungfrau_packet16 *) packet)->data;
  }
  else{
    printf("No detector selected\n");
  }
  // ignoring the special eiger initial packet
  if(data_len <= HEADER_PACKET_SIZE){
    return bpacket;
  }

  counters->recv_packets++;

  // this fails in case frame number is not updated by the detector (or its simulation)
  if(counters->recv_packets == packets_frame && bpacket.framenum == counters->current_frame){
    //this is the last packet of the frame
#ifdef DEBUG
    printf("[UDPRECV] Frame complete, got packet %d  #%d of %d frame %lu / %lu\n", bpacket.packetnum, counters->recv_packets, 
                                                                    packets_frame, bpacket.framenum, counters->current_frame);
#endif

    counters->recv_frames++;
    //counters->recv_packets = 0;
    counters->current_frame = 0; // this will cause getting a new slot afterwards
    commit_flag = true; // for committing the slot later
    counters->lost_frames = 0;
  }
  // this means we are in a new frame
  else if (counters->current_frame != bpacket.framenum){        
    if(counters->recv_packets != packets_frame && counters->recv_packets != 1){
      // this means we lost some packets before, 
      // and we have a dangling slot. Current frame is set to 0 when a complete frame is
      // committed
      if(counters->current_frame != 0){
        if(*rb_current_slot != -1){
          // add some checks here
          rb_commit_slot(rb_writer_id, *rb_current_slot);
        }
        else
          printf("[ERROR] I should have been committing a dangling slot, but it is -1\n");

        //do_stats with recv_packets -1
        counters->lost_frames = packets_frame - (counters->recv_packets - 1);
#ifdef DEBUG
        printf("[UDPRECV][%d] %d %d %d\n", getpid(), packets_frame, counters->recv_packets, counters->lost_frames);
#endif
      }
      counters->recv_packets = 1;
    }
    counters->current_frame = bpacket.framenum;
    *rb_current_slot = rb_claim_next_slot(rb_writer_id);
    while(*rb_current_slot == -1){
      *rb_current_slot = rb_claim_next_slot(rb_writer_id);
    }
  }

  // Data copy
  // getting the pointers in RB for header and data - must be done after slots are committed / assigned
  ph = (eiger_header *) rb_get_buffer_slot(rb_hbuffer_id, *rb_current_slot);
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
  if (counters->recv_packets == 1){
    for(i=0; i < 8; i++)
      ph->framemetadata[i] = 0;

    ph->framemetadata[2] = ones >> (64 - packets_frame);
    ph->framemetadata[3] = 0;

    if(packets_frame > 64)
      ph->framemetadata[3] = ones >> (128 - packets_frame);
  }
    
  // First half (up)
  if((det.submodule_idx[0] == 0 && det.submodule_idx[1] == 0) ||
      (det.submodule_idx[0] == 0 && det.submodule_idx[1] == 1)){

        if(det.submodule_n == 4){
          for(i=line_number + lines_per_packet - 1; i >= line_number; i--){
            memcpy(p1 + i * det.detector_size[1],
              data + int_line * det.submodule_size[1],
              det.submodule_size[1] * sizeof(int16_t) / 2);

            memcpy(p1 + i * det.detector_size[1] + GAP_PX_CHIPS_Y + det.submodule_size[1] / 2,
              data + int_line * det.submodule_size[1] + det.submodule_size[1] / 2,
              det.submodule_size[1] * sizeof(int16_t) / 2);
            int_line ++;
            }
        }
        else{
          for(i=line_number + lines_per_packet - 1; i >= line_number; i--){
            memcpy(p1 + (det.submodule_size[0] - 1 - i) * det.detector_size[1],
                  data + int_line * det.submodule_size[1],
                  det.submodule_size[1] * sizeof(uint16_t));
            int_line ++;
        }
      }      
    }
    // the other half
  else{
    for(i=line_number + lines_per_packet - 1; i >= line_number; i--){
      memcpy(p1 + (det.submodule_size[0] - 1 - i) * det.detector_size[1],
        data + int_line * det.submodule_size[1],
        det.submodule_size[1] * sizeof(int16_t) / 2);
      memcpy(p1 + (det.submodule_size[0] - 1 - i) * det.detector_size[1] + GAP_PX_CHIPS_Y + det.submodule_size[1] / 2,
        data + int_line * det.submodule_size[1] + det.submodule_size[1] / 2,
        det.submodule_size[1] * sizeof(int16_t) / 2);
      int_line ++;
    }
  }

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


barebone_packet get_put_data32(int sock, int rb_hbuffer_id, int *rb_current_slot, int rb_dbuffer_id, int rb_writer_id, 
                                uint32_t mod_origin,int lines_per_packet, int packets_frame, int32_t *det_size, 
                                int32_t *submod_size, int32_t *submod_idx){
  /*!
    gets the packet data and put it in the correct memory place in the RingBuffer
   */
  eiger_packet32 packet;
  eiger_header * ph;
  eiger_header header;

  uint32_t * p1;
  int data_len;
  int int_line = 0;
  int line_number;
  int i;
  
  
  barebone_packet bpacket;
  
  data_len = get_message32(sock, &packet);
  bpacket.data_len = data_len;

  if(data_len > HEADER_PACKET_SIZE){
    if(*rb_current_slot == -1)
      while(*rb_current_slot == -1){
	*rb_current_slot = rb_claim_next_slot(rb_writer_id);
      }
    bpacket.framenum = packet.framenum;
    bpacket.packetnum = packet.packetnum;

    // Data copy
    // getting the pointers in RB for header and data
    ph = (eiger_header *) rb_get_buffer_slot(rb_hbuffer_id, *rb_current_slot);
    p1 = (uint32_t *) rb_get_buffer_slot(rb_dbuffer_id, *rb_current_slot);

    // computing the origin and stride of memory locations
    p1 += mod_origin;
    // assuming packetnum sequence is 0..N-1
    line_number = lines_per_packet * (packets_frame - packet.packetnum - 1);

    // First half (up)
    //TODO: try ask HC, or do loops in an inlined function
    if((submod_idx[0] == 0 && submod_idx[1] == 0) ||
       (submod_idx[0] == 0 && submod_idx[1] == 1)){
      for(i=line_number + lines_per_packet - 1; i >= line_number; i--){
	//printf("bottom1: %d\n", i * det_size[1]);
	memcpy(p1 + i * det_size[1],
	       packet.data + int_line * submod_size[1],
	       submod_size[1] * sizeof(int32_t) / 2);

	//printf("bottom2: %d\n", i * det_size[1] + GAP_PX_CHIPS_Y + submod_size[1] / 2);
	memcpy(p1 + i * det_size[1] + GAP_PX_CHIPS_Y + submod_size[1] / 2,
	       packet.data + int_line * submod_size[1] + submod_size[1] / 2,
	       submod_size[1] * sizeof(int32_t) / 2);
	int_line ++;
      }
    }
    // the other half
    else{
      for(i=line_number + lines_per_packet - 1; i >= line_number; i--){
	//printf("up1 %d %d %d %d %d\n", (255 - i) * det_size[1], i, det_size[1], line_number, lines_per_packet);

	// TODO remove the hardcoded 255
	memcpy(p1 + (255 - i) * det_size[1],
	       packet.data + int_line * submod_size[1],
	       submod_size[1] * sizeof(int32_t) / 2);
	//printf("up2 %d\n", (255 - i) * det_size[1] + GAP_PX_CHIPS_Y + submod_size[1] / 2);
	memcpy(p1 + (255 - i) * det_size[1] + GAP_PX_CHIPS_Y + submod_size[1] / 2,
	       packet.data + int_line * submod_size[1] + submod_size[1] / 2,
	       submod_size[1] * sizeof(int32_t) / 2);
	int_line ++;
      }
    }
    /*
    header.framenum = packet.framenum;
      
    if(ph->framenum != packet.framenum){
      memcpy(ph, &header, sizeof(header));
    }
    */
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
  
  //int lines_per_packet = 8 * BUFFER_LENGTH / (bit_depth * submod_size[1]);
  int lines_per_packet = BUFFER_LENGTH / det.module_size[1];

  counter counters;

  counters.current_frame = 0;
  counters.recv_frames = 0;

  // Origin of the module within the detector, (0, 0) is bottom left
  uint32_t mod_origin = det.detector_size[1] * det.module_idx[0] * det.module_size[0] + det.module_idx[1] * det.module_size[1];
  mod_origin += det.module_idx[1] * (3 * GAP_PX_CHIPS_Y + GAP_PX_MODULES_Y); // inter_chip gaps plus inter_module gap
  mod_origin += det.module_idx[0] * (GAP_PX_CHIPS_X + GAP_PX_MODULES_X)* det.detector_size[1] ; // inter_chip gaps plus inter_module gap

  // Origin of the submodule within the detector, relative to module origin
  mod_origin += det.detector_size[1] * det.submodule_idx[0] * det.submodule_size[0] + det.submodule_idx[1] * det.submodule_size[1];
  if(det.submodule_idx[1] != 0)
    mod_origin += 2 * GAP_PX_CHIPS_Y;  // 2* because there is the inter-quartermodule chip gap //GAP_PX_CHIPS_Y * submod_idx[1]; // the last takes into account extra space for chip gap within quarter module
  if(det.submodule_idx[0] != 0)
    mod_origin += det.submodule_idx[0] * det.detector_size[1] * GAP_PX_CHIPS_X;

  int mod_number = det.submodule_idx[1] + det.submodule_idx[0] * 2 +
    det.submodule_n * (det.module_idx[1] + det.module_idx[0] * det.detector_size[1] / det.module_size[1]); //numbering inside the detctor, growing over the x-axis

  //JF
  //int mod_number = det.module_idx[0] + det.module_idx[1] + det.module_idx[0] * ((det.detector_size[1] / det.module_size[1]) -1); //numbering inside the detctor, growing over the x-axis
  //mod_origin = det_size[1] * mod_idx[0] * mod_size[0] + mod_idx[1] * mod_size[1];
  //

  packets_frame = 128;//submod_size[0] * submod_size[1] / (8 * BUFFER_LENGTH / bit_depth);
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

  printf("[UDPRECEIVER][%d] entered at %.3f s\n", getpid(), (double)(tv_start.tv_usec) / 1e6 + (double)(tv_start.tv_sec));
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
    jungfrau_packet16 packet;
    uint16_t *data;
      bpacket = get_put_data16(sock, rb_hbuffer_id, &rb_current_slot, rb_dbuffer_id, rb_writer_id, mod_origin, mod_number,
			       lines_per_packet, packets_frame, /*det_size, submod_size, submod_idx,*/ &counters, det, &packet);
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
        printf("breaking timeout after %f ms\n", timeout_i);
        printf("[UDPRECEIVER][%d] left at %.3f s\n", getpid(), (double)(tv_end.tv_usec) / 1e6 + (double)(tv_end.tv_sec));

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
