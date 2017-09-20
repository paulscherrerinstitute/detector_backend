#include <stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <sys/time.h>

// for uint64 printing
#include <inttypes.h>

#include <ring_buffer.h>
// for serveraddr
#include <arpa/inet.h>

#define BUFFER_LENGTH    4096
#define YSIZE 1024
#define XSIZE 512

#define SERVER_PORT    50004
#define SERVER_IP    "10.30.10.2"

//Jungfrau

// header struct for RB
typedef struct _jungfrau_header{
  uint8_t n_modules;
  uint64_t framenum[32];
  uint64_t recorded_packets1;
  uint64_t recorded_packets2;
  int8_t padding[320 - 1 - 34 * 8];
} jungfrau_header;

/*
typedef struct _jungfrau_header{
  uint64_t framenum;
  uint8_t packetnum;
  int8_t padding[64 - 2 - 1];
} jungfrau_header;
*/

//Memory packing (see: https://msdn.microsoft.com/en-us/library/2e70t5y1.aspx)
#pragma pack(push)
#pragma pack(2)
typedef struct _jungfraujtb_packet{
    char emptyheader[6]; //was 2
    uint64_t framenum;
    uint64_t packetnum;
    uint16_t data[BUFFER_LENGTH];
  } jungfraujtb_packet;
#pragma pack(pop)

//Jungfrau
/*
#pragma pack(push)
#pragma pack(2)
typedef struct _jungfrau_packet{
  char emptyheader[6];
  uint32_t reserved;
  char packetnum2;
  char framenum2[3];
  uint64_t bunchid;
  uint16_t data[BUFFER_LENGTH];
  uint64_t framenum;
  uint8_t packetnum;
} jungfrau_packet;
#pragma pack(pop)
*/
#pragma pack(push)
#pragma pack(2)
typedef struct _jungfrau_packet{
  char emptyheader[6];
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
  uint16_t data[BUFFER_LENGTH];
} jungfrau_packet;
#pragma pack(pop)

//simple routine to get data from UDP socket
int get_message(int sd, jungfrau_packet * packet){
    struct sockaddr_in clientaddr;
    socklen_t clientaddrlen = sizeof(clientaddr);

    //ssize_t nbytes = recvfrom(sd, packet, sizeof(*packet), MSG_DONTWAIT, (struct sockaddr *)&clientaddr, &clientaddrlen);
    ssize_t nbytes = recvfrom(sd, packet, sizeof(*packet), 0, (struct sockaddr *)&clientaddr, &clientaddrlen);
    
    #ifdef DEBUG
    if(nbytes >= 0){
      printf("+ PID %d ", getpid());
      //printf("-%6c-\t", packet->emptyheader);
      printf("frame %lu ", packet->framenum);
      printf("packet %u ", packet->packetnum);
      printf("data0 %hu ", packet->data[0]);
      printf("datalast %hu \n", packet->data[BUFFER_LENGTH - 1]);
    }
    #endif
    
  return nbytes;
}


int put_data_in_rb(int sock, int bit_depth, int rb_current_slot, int rb_header_id, int rb_hbuffer_id, int rb_dbuffer_id, int rb_writer_id, int16_t nframes, int32_t det_size[2], int32_t *mod_size, int32_t *mod_idx, int timeout){
  
  int n_recv_frames = 0;
  uint64_t framenum_last = 0;
  int total_packets = 0;
  int stat_total_frames = 0;
  int lost_frames = 0;
  int tot_lost_frames = 0;
  int64_t lost_packets = 0;
  int64_t tot_lost_packets = 0;
  time_t timeout_i = 0;

  //int temp = 0;
  
  //begin
  int   data_len;
  int i;
  jungfrau_header * ph;
  //int n_entries;
  //int rb_current_slot;
  jungfrau_packet packet;
  uint16_t * p1;
  jungfrau_header header;
  int packets_frame = 127;
  int last_recorded_packet = -1;

  //end
  //clock_t ti2;  
  
  //int packets_frame_recv[128];

  struct  timeval ti, te; //for timing
  double tdif=-1;
  
  int line_number = 0;
  int int_line = 0;
  int data_size = 0;
  int mod_idx_x = mod_idx[0], mod_idx_j = mod_idx[1];
  int mod_size_x = mod_size[0], mod_size_y = mod_size[1];
  //int det_size_x = det_size[0];
  int det_size_y = det_size[1];
  int lines_per_packet = BUFFER_LENGTH / mod_size_y;
  
  int mod_origin = det_size_y * mod_idx_x * mod_size_x + mod_idx_j * det_size_y;

  data_size = det_size_y * sizeof(uint16_t);
  //do I need this?
  //rb_set_buffer_stride_in_byte(rb_dbuffer_id, 2 * 512 * 3 * 1024);
  //rb_adjust_nslots(rb_header_id);
  
  //for(i=0; i< 128; i++)
  //  packets_frame_recv[i] = 0;
  
  timeout_i = time(NULL);
 
  while(true){
  //printf("A\n");
    if(nframes != -1)
      if(n_recv_frames >= nframes)
	break;
    
    data_len = get_message(sock, &packet);

    // no data? Checks timeout
    if(data_len <= 0){
      if ((int)time(NULL) - (int)timeout_i > timeout){
	//printf("TIMEOUT %d %lu new_frame_num %lu slot %d\n", getpid(), packet.framenum, framenum_last, rb_current_slot);
	
	// flushes the last message
	if(rb_current_slot != -1){
	  rb_commit_slot(rb_writer_id, rb_current_slot);
	  //printf("Committed slot %d\n", rb_current_slot);
	}
	break;
      }
      continue;
    }

    // claim a slot before starting, if data
    if(rb_current_slot == -1){
      rb_current_slot = rb_claim_next_slot(rb_writer_id);
      //printf("Claimed1 slot %d\n", rb_current_slot);
    }
    timeout_i = time(NULL);
    if(last_recorded_packet == -1)
      last_recorded_packet = packet.packetnum;
      
    if(framenum_last == 0)
      framenum_last = packet.framenum;
      
    //packets_frame_recv[packet.packetnum] = packet.packetnum + 1;
                      
    //this means a new frame, assuming frame number is unique in the sequence
    

    if(packet.framenum != framenum_last){
      //printf("%d %lu new_frame_num %lu slot %d\n", getpid(), packet.framenum, framenum_last, rb_current_slot);
          
      if(rb_current_slot != -1)
	rb_commit_slot(rb_writer_id, rb_current_slot);
      rb_current_slot = rb_claim_next_slot(rb_writer_id);
      //printf("Claimed2 slot %d\n", rb_current_slot);

      if(rb_current_slot == -1)
	while(rb_current_slot == -1)
	  rb_current_slot = rb_claim_next_slot(rb_writer_id);

      // still gives me wrong number it seems, +1
      //printf("PID %d frame # %lu last # %lu total_packets %d\n", getpid(), packet.framenum, framenum_last, total_packets);
      if(total_packets != 128){
	//printf("PID %d frame # %lu last # %lu total_packets %d\n", getpid(), packet.framenum, framenum_last, total_packets);
	lost_frames ++;
	tot_lost_frames += 1;
	lost_packets += 128 - total_packets;
	tot_lost_packets += 128 - total_packets;
      }
      //for(i=0; i< 128; i++)
      //packets_frame_recv[i] = 0;
	
      framenum_last = packet.framenum;

      int stats_frames = 1000;

      stat_total_frames ++;
      n_recv_frames ++;
      if (n_recv_frames % stats_frames == 0 && n_recv_frames != 0){
	gettimeofday(&te, NULL);
	if (lost_packets != 0){
	  tdif = (te.tv_sec - ti.tv_sec) + ((long)(te.tv_usec) - (long)(ti.tv_usec)) / 1e6;
	  printf("| %d | %lu | %.2f | %lu | %.1f |\n", getpid(), framenum_last, (double) stats_frames / tdif, lost_packets, 100. * (float)lost_packets / (float)(128 * stat_total_frames));
	}
	gettimeofday(&ti,NULL);
	lost_frames = 0;
	lost_packets = 0;
	stat_total_frames = 0;
      } 

      total_packets = 0;
    } // end new frame if
    // This holds no more, packets are coming not in a sequence
    //else if(packet.packetnum > last_recorded_packet)
    //  printf("[WARNING] Something went wrong, frame number replicated over frames new_packet:%d last_packet:%d\n", packet.packetnum, last_recorded_packet);
      
    last_recorded_packet = packet.packetnum;

    // data copy
    ph = (jungfrau_header *) rb_get_buffer_slot(rb_hbuffer_id, rb_current_slot);
    p1 = (uint16_t *) rb_get_buffer_slot(rb_dbuffer_id, rb_current_slot);
    
    line_number = lines_per_packet * (packets_frame - packet.packetnum);
    int_line = 0;
    
    p1 += mod_origin;
    for(i=line_number; i < line_number + lines_per_packet; i++){
      memcpy(p1 + i * det_size_y,
	     packet.data + int_line * det_size_y,
	     data_size);
      int_line ++;
    }

    header.framenum = packet.framenum;
      
    if(ph->framenum != packet.framenum){
      memcpy(ph, &header, sizeof(header));
    }

    // This should cast an error, or a warning
    if(rb_current_slot == -1)
      continue;
      
    if(tdif < 0){
      //ti2 = clock();
      tdif = 0;
      gettimeofday(&ti, NULL);
    }    

    //last_recorded_packet = packet.packetnum;
    total_packets ++;

  } // end while



  return n_recv_frames;
}





/*
int main(int argc, char *argv[]){
  int ret, sd, rc;
  int data_len;
  struct sockaddr_in serveraddr;	
  jungfrau_packet packet;
  int data[1000];
  int recv_packets;
  int recv_frames;
  int last_frame;
  int lost_packets;

  sd = socket(AF_INET, SOCK_DGRAM, 0);
  printf("SD: %d\n", sd);
  
  int val=1000 * 1024 * 1024;
  setsockopt(sd, SOL_SOCKET, SO_RCVBUF, &val, sizeof(int));
  
  if (sd < 0){
    perror("socket() failed");
    return -1;
  }
  
  memset(&serveraddr, 0, sizeof(serveraddr));
  serveraddr.sin_family      = AF_INET;
  serveraddr.sin_port        = htons(atoi(argv[2]));
  serveraddr.sin_addr.s_addr = inet_addr(argv[1]);
  
  rc = bind(sd, (struct sockaddr *)&serveraddr, sizeof(serveraddr));
  printf("RC bind: %d %s %d \n", rc, "10.30.10.2", atoi(argv[2]));
  
  recv_packets = 0;
  recv_frames = 0;
  last_frame = -1;
  printf("PID Frames Lost Perc\n");
  while(1==1){
    data_len = get_message(sd, &packet);

    if (data_len == 0)
      continue;
    
    if (last_frame == -1)
      last_frame = packet.framenum;

    if (last_frame != packet.framenum){
      recv_frames ++;
      last_frame = packet.framenum;
    }

    if (recv_frames % 1000 == 0 && packet.packetnum == 127 && recv_frames != 0){
      lost_packets = 128 * recv_frames - recv_packets;
      printf("%d %d %d %.1f\n", getpid(), recv_frames, lost_packets, 100. * (float)(lost_packets) / (float)(128 * recv_frames));
    }
    recv_packets ++;

  }
  return 0;
}

*/
