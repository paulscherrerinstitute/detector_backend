#include <stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>

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
  uint64_t framenum;
  uint8_t packetnum;
  int8_t padding[64 - 2 - 1];
} jungfrau_header;


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

//Gotthard
typedef struct _gotthard_packet1{
    uint32_t framenum;
    uint32_t dummy;
    uint16_t data[639];
  } gotthard_packet1;
typedef struct _gotthard_packet2{
    uint32_t framenum;
    uint16_t data[641];
  } gotthard_packet2;
typedef struct _gotthard_packet{
    uint32_t framenum;
    uint16_t data[1280];
  } gotthard_packet;


//simple routine to get data from UDP socket
int get_message_jtb(int sd, jungfraujtb_packet * packet){
        ssize_t nbytes = recv(sd, packet, sizeof(*packet), MSG_DONTWAIT);

	#ifdef DEBUG
        if(nbytes >= 0){
	  printf("+ C %d ", getpid());
                //printf("-%6c-\t", packet->emptyheader);
                printf("frame %u ", packet->framenum);
                printf("packet %u ", packet->packetnum);
                printf("data0 %hu ", packet->data[0]);
                printf("datalast%hu \n", packet->data[BUFFER_LENGTH - 1]);
        }
	#endif
        return nbytes;
}

//simple routine to get data from UDP socket
int get_message(int sd, jungfrau_packet * packet){
    struct sockaddr_in clientaddr;
    int    clientaddrlen = sizeof(clientaddr);

    /* 
       int packet_size;
       packet_size = sizeof(*packet) - 8 - 1;

     */

    //ssize_t nbytes = recvfrom(sd, packet, sizeof(*packet) - 8 - 1, 0, (struct sockaddr *)&clientaddr, &clientaddrlen);
    ssize_t nbytes = recvfrom(sd, packet, sizeof(*packet), 0, 
			      (struct sockaddr *)&clientaddr, &clientaddrlen);
  

//ssize_t nbytes = recv(sd, packet, sizeof(*packet) - 8 - 1, 0); //, MSG_DONTWAIT);
    packet->framenum = (((int)(packet->framenum2[2])&0xff)<<16) + (((int)(packet->framenum2[1])&0xff)<<8) +((int)(packet->framenum2[0])&0xff);
  
    packet->packetnum =  (uint16_t)((packet->packetnum2));

    
  #ifdef DEBUG
  if(nbytes >= 0){
    printf("+ C %d ", getpid());
    
    //printf("-%6c-\t", packet->emptyheader);
    printf("+ C %d ", getpid());
    //printf("-%6c-\t", packet->emptyheader);
    printf("frame %u ", packet->framenum);
    printf("packet %u ", packet->packetnum);
    printf("data0 %hu ", packet->data[0]);
    printf("datalast %hu \n", packet->data[BUFFER_LENGTH - 1]);
  }
  #endif
    
  return nbytes;
}


//untested
int get_message_gotthard(int sd, gotthard_packet * packet){
	gotthard_packet1 packet1;
	gotthard_packet2 packet2;
		
	ssize_t nbytes1 = recv(sd, &packet1, sizeof(packet1), MSG_DONTWAIT);
	ssize_t nbytes2 = recv(sd, &packet2, sizeof(packet2), MSG_DONTWAIT);

	packet->framenum = packet1.framenum;
	memcpy(packet->data, packet1.data, 641 * sizeof(uint16_t));
	memcpy(packet->data + 641, packet2.data, 639 * sizeof(uint16_t));
	
	//#ifdef DEBUG
	if(nbytes1 >= 0){
		printf("+ C ");
		//printf("-%6c-\t", packet->emptyheader);
		printf("%u\t", packet->framenum);
		printf("%hu\t", packet->data[0]);
		printf("%hu\t", packet->data[4095]);
		printf("%hu\t\n", packet->data[4099]);

	}
	//#endif
	return nbytes1 + nbytes2;
}


int put_data_in_memory(int sd, jungfrau_packet * packet, int n_entries, uint16_t * p1, jungfrau_header * ph, int32_t * idx){
  int i, data_len;
  jungfrau_header header;
  int packets_frame;

  data_len = get_message(sd, packet);
  //return data_len;
  packets_frame = 127;

  if(data_len > 0){
    for(i=0; i < (sizeof(packet->data) / sizeof(uint16_t)); i++){
      	p1[idx[i + n_entries * (packets_frame - packet->packetnum)]] = packet->data[i];
    }

    if(packet->packetnum == 127){
      header.framenum = packet->framenum;
      //if(ph->framenum != packet->framenum){
      	memcpy(ph, &header, sizeof(header));
      printf("DONE\n");
      //}
    }
  }
  /*
  else{
    packet->framenum = 65535;
  }
  */
  return data_len;
}


// generic routine to save data from UDP socket in Ringbuffer
int put_udp_in_rb(int sock, int bit_depth, int rb_current_slot, int rb_header_id, int rb_hbuffer_id, int rb_dbuffer_id, int rb_writer_id, int32_t * idx, uint16_t * framenum){

  int data_len;
  int i, j;
  jungfrau_header * ph;
  int n_entries;
  //int rb_current_slot;
  jungfrau_packet packet;
  uint16_t * p1;
  jungfrau_header header;
  int packets_frame;
  int *ret;

  //printf("PID %d ID %d\n", getpid(), rb_writer_id);

  n_entries = BUFFER_LENGTH; // / (bit_depth / 8);
  //data_len = put_data_in_memory(sock, &packetb, n_entries, p1, ph, idx);

  data_len = get_message(sock, &packet);
  packets_frame = 127;

  if(data_len > 0){
    printf("%d packet num %d\n", getpid(), packet.packetnum);
    printf("PID %d ID %d\n", getpid(), rb_writer_id);
    printf("PID %d %d %d\n", getpid(), rb_header_id, rb_hbuffer_id);

    if(packet.packetnum == 127 || packet.framenum != *framenum){
      //this means a new frame
      if(rb_current_slot != -1)
	rb_commit_slot(rb_writer_id, rb_current_slot);
      rb_current_slot = rb_claim_next_slot(rb_writer_id);
      while(rb_current_slot == -1)
	rb_current_slot = rb_claim_next_slot(rb_writer_id);
      //printf("%d\n", rb_current_slot);
    }

    rb_set_buffer_stride_in_byte(rb_dbuffer_id, 2 * 512 * 3 * 1024);
    rb_adjust_nslots(rb_header_id);

    
    ph = (jungfrau_header *) rb_get_buffer_slot(rb_hbuffer_id, rb_current_slot);
    p1 = (uint16_t *) rb_get_buffer_slot(rb_dbuffer_id, rb_current_slot);
    
    for(i=0; i < (sizeof(packet.data) / sizeof(uint16_t)); i++){
      p1[idx[i + n_entries * (packets_frame - packet.packetnum)]] = packet.data[i];
    }
    
    header.framenum = packet.framenum;
    printf("A\n");
    printf("%d\n", *framenum);
    *framenum = header.framenum;

    if(ph->framenum != packet.framenum){
      memcpy(ph, &header, sizeof(header));
    }

    return rb_current_slot;
  }
  else
    return -1;
  //ret[0] = rb_current_slot;
  //ret[1] = packet.framenum;
  
}



//int put_data_in_rb(int sock, int bit_depth, int rb_current_slot, int rb_header_id, int rb_hbuffer_id, int rb_dbuffer_id, int rb_writer_id, int32_t * idx, int16_t nframes){
int put_data_in_rb(int sock, int bit_depth, int rb_current_slot, int rb_header_id, int rb_hbuffer_id, int rb_dbuffer_id, int rb_writer_id, int16_t nframes, int32_t det_size[2], int32_t *mod_size, int32_t *mod_idx){
  
  int n_recv_frames = 0;
  uint64_t framenum_last = 0;
  uint64_t framenum = 0;
  int total_packets = 0;
  int stat_total_frames = 0;
  int lost_frames = 0;
  int tot_lost_frames = 0;
  int64_t lost_packets = 0;
  int64_t tot_lost_packets = 0;
  //time_t ti = 0;

  int temp = 0;
  
  //begin
  int   data_len;
  int i, j;
  jungfrau_header * ph;
  int n_entries;
  //int rb_current_slot;
  jungfrau_packet packet;
  uint16_t * p1;
  jungfrau_header header;
  int packets_frame;
  int *ret;
  //end
  clock_t ti2;  

  int packets_frame_recv[128];

  struct  timeval ti, te; //for timing
  double tdif=-1;

  printf("DET_SIZE %d %d\n", det_size[0], det_size[1]);
  printf("MOD_SIZE %d %d\n", mod_size[0], mod_size[1]);
  printf("MOD_IDX %d %d\n", mod_idx[0], mod_idx[1]);

  //sleep(10);

  int line_number = 0;
  int int_line = 0;
  int data_size = 0;
  int mod_idx_x = mod_idx[0], mod_idx_j = mod_idx[1];
  int mod_size_x = mod_size[0], mod_size_y = mod_size[1];
  int det_size_x = det_size[0], det_size_y = det_size[1];
  int lines_per_packet = BUFFER_LENGTH / mod_size_y;
  
  int mod_origin = det_size_y * mod_idx_x * mod_size_x + mod_idx_j * det_size_y;

  rb_set_buffer_stride_in_byte(rb_dbuffer_id, 2 * 512 * 3 * 1024);
  rb_adjust_nslots(rb_header_id);
  
  printf("| PID | cur_frame | Hz | Lost packets | \% lost packets |\n");
  
  for(i=0; i< 128; i++)
    packets_frame_recv[i] = 0;

  // claim a slot before starting
  rb_current_slot = rb_claim_next_slot(rb_writer_id);

  while(true){
    //printf("A\n");
    if(nframes != -1)
      if(n_recv_frames >= nframes)
	break;
        
    n_entries = BUFFER_LENGTH; // / (bit_depth / 8);
    //data_len = put_data_in_memory(sock, &packetb, n_entries, p1, ph, idx);
    
    data_len = get_message(sock, &packet);
    packets_frame = 127;

    if(data_len > 0){
      
      if(framenum == 0)
	framenum = packet.framenum;

      if(framenum_last == 0)
	framenum_last = framenum;
      
      packets_frame_recv[packet.packetnum] = packet.packetnum + 1;
      
      
      //printf("%d %d packet num %d\n", getpid(), packet.framenum, packet.packetnum);
      //printf("PID %d ID %d\n", getpid(), rb_writer_id);
      //printf("PID %d %d %d\n", getpid(), rb_header_id, rb_hbuffer_id);
      

      //this means a new frame
      if(framenum != framenum_last ){
	if(rb_current_slot != -1)
	  rb_commit_slot(rb_writer_id, rb_current_slot);
	rb_current_slot = rb_claim_next_slot(rb_writer_id);
	
	if(rb_current_slot == -1)
	  while(rb_current_slot == -1)
	    rb_current_slot = rb_claim_next_slot(rb_writer_id);

	// still gives me wrong number it seems, +1
	if(total_packets != 128){
	  //printf("total_packets %d\n", total_packets);
	  lost_frames ++;
	  tot_lost_frames += 1;
	  lost_packets += 128 - total_packets;
	  tot_lost_packets += 128 - total_packets;
	}
	for(i=0; i< 128; i++)
	  packets_frame_recv[i] = 0;
	
	framenum_last = framenum;
	stat_total_frames ++;
	n_recv_frames ++;
	
	if (n_recv_frames % 5000 == 0){
	  gettimeofday(&te, NULL);
	  tdif = (1e6 * (te.tv_sec - ti.tv_sec) + (long)(te.tv_usec) - (long)(ti.tv_usec)) / 1e6;
	  //printf("%f %d %d", tdif, te.tv_sec, ti.tv_sec);
	  printf("| %d | %d | %.2f | %d | %.1f |\n",
		 getpid(), framenum_last, (double) 5000. / tdif, lost_packets, 
		 100. * (float)lost_packets / (float)(128 * stat_total_frames)
		 );
	  //ti = time(NULL);
	  gettimeofday(&ti,NULL);
	  //ti2 = clock();
	  lost_frames = 0;
	  lost_packets = 0;
	  stat_total_frames = 0;
	}
	total_packets = 0;
      } // end new frame if
    
      ph = (jungfrau_header *) rb_get_buffer_slot(rb_hbuffer_id, rb_current_slot);
      p1 = (uint16_t *) rb_get_buffer_slot(rb_dbuffer_id, rb_current_slot);
    

      line_number = lines_per_packet * (packets_frame - packet.packetnum);
      int_line = 0;
      data_size = det_size_y * sizeof(uint16_t);
      p1 += mod_origin;
      for(i=line_number; i < line_number + lines_per_packet; i++){
	//printf("n %d a %d, b %d \n", line_number, mod_origin + int_line * det_size_y,i * det_size_y );
	memcpy(p1 + i * det_size_y,
	       packet.data + int_line * det_size_y,
	       data_size);
	int_line ++;
      }

      header.framenum = packet.framenum;
      framenum = header.framenum;
      
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
      
      total_packets ++;
    } // end data if
  }

  return 0;
}



int put_data_in_rb_old(int sock, int bit_depth, int rb_current_slot, int rb_header_id, int rb_hbuffer_id, int rb_dbuffer_id, int rb_writer_id, int32_t * idx, int16_t nframes){  
  int n_recv_frames = 0;
  uint64_t framenum_last = 0;
  uint64_t framenum = 0;
  int total_packets = 0;
  int stat_total_frames = 0;
  int lost_frames = 0;
  int tot_lost_frames = 0;
  int64_t lost_packets = 0;
  int64_t tot_lost_packets = 0;
  //time_t ti = 0;

  int temp = 0;
  
  //begin
  int   data_len;
  int i, j;
  jungfrau_header * ph;
  int n_entries;
  //int rb_current_slot;
  jungfrau_packet packet;
  uint16_t * p1;
  jungfrau_header header;
  int packets_frame;
  int *ret;
  //end
  clock_t ti2;  

  int packets_frame_recv[128];

  struct  timeval ti, te; //for timing
  double tdif=-1;

  rb_set_buffer_stride_in_byte(rb_dbuffer_id, 2 * 512 * 3 * 1024);
  rb_adjust_nslots(rb_header_id);
  
  printf("| PID | cur_frame | Hz | Lost packets | \% lost packets |\n");
  
  for(i=0; i< 128; i++)
    packets_frame_recv[i] = 0;

  // claim a slot before starting
  rb_current_slot = rb_claim_next_slot(rb_writer_id);

  while(true){
    //printf("A\n");
    if(nframes != -1)
      if(n_recv_frames >= nframes)
	break;
        
    n_entries = BUFFER_LENGTH; // / (bit_depth / 8);
    //data_len = put_data_in_memory(sock, &packetb, n_entries, p1, ph, idx);
    
    data_len = get_message(sock, &packet);
    //printf("%d %d packet num %d\n", getpid(), packet.framenum, packet.packetnum);

    packets_frame = 127;

    if(data_len > 0){
      
      if(framenum == 0)
	framenum = packet.framenum;

      if(framenum_last == 0)
	framenum_last = framenum;
      
      packets_frame_recv[packet.packetnum] = packet.packetnum + 1;
      
      //this means a new frame
      if(framenum != framenum_last ){
	if(rb_current_slot != -1)
	  rb_commit_slot(rb_writer_id, rb_current_slot);
	rb_current_slot = rb_claim_next_slot(rb_writer_id);
	
	if(rb_current_slot == -1)
	  while(rb_current_slot == -1)
	    rb_current_slot = rb_claim_next_slot(rb_writer_id);

	// still gives me wrong number it seems, +1
	if(total_packets != 128){
	  //printf("total_packets %d\n", total_packets);
	  lost_frames ++;
	  tot_lost_frames += 1;
	  lost_packets += 128 - total_packets;
	  tot_lost_packets += 128 - total_packets;
	  
	  /*
	  for(j=0; j< 128; j++)
	    printf("%d ", packets_frame_recv[j]);
	  printf("\n");
	  */
	  
	}
	for(i=0; i< 128; i++)
	  packets_frame_recv[i] = 0;
	
	framenum_last = framenum;
	stat_total_frames ++;
	n_recv_frames ++;
	
	if (n_recv_frames % 5000 == 0){
	  gettimeofday(&te, NULL);
	  tdif = (1e6 * (te.tv_sec - ti.tv_sec) + (long)(te.tv_usec) - (long)(ti.tv_usec)) / 1e6;
	  //printf("%f %d %d", tdif, te.tv_sec, ti.tv_sec);
	  printf("| %d | %d | %.2f | %d | %.1f |\n",
		 getpid(), framenum_last, (double) 5000. / tdif, lost_packets, 
		 100. * (float)lost_packets / (float)(128 * stat_total_frames)
		 );
	  //ti = time(NULL);
	  gettimeofday(&ti,NULL);
	  //ti2 = clock();
	  lost_frames = 0;
	  lost_packets = 0;
	  stat_total_frames = 0;
	}
	total_packets = 0;
      } // end new frame if
    
      ph = (jungfrau_header *) rb_get_buffer_slot(rb_hbuffer_id, rb_current_slot);
      p1 = (uint16_t *) rb_get_buffer_slot(rb_dbuffer_id, rb_current_slot);
    
      //reference
    
      int shift = n_entries * (packets_frame - packet.packetnum);
      for(i=0; i < BUFFER_LENGTH; i++){
      	p1[idx[i + shift]] = packet.data[i];
      }
      
      /*
      for(i=shift; i < BUFFER_LENGTH + shift; i++){
	p1[idx[i]] = packet.data[i % shift];


	//this fast, also with shift
	//p1[i] = packet.data[i];
	//this is slow
	//p1[i + shift] = packet.data[i];
	// this is slow
	//j = idx[i + shift];
	//p1[j] = packet.data[i];
	
      }
      */
      //memcpy(p1, packet.data, 4096*sizeof(uint16_t));
      //memcpy(temp, packet.data, 4096 * sizeof(uint16_t));
      
      header.framenum = packet.framenum;
      framenum = header.framenum;
      
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
      
      total_packets ++;
    } // end data if
  }

  return 0;
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
