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

// for serveraddr
#include <arpa/inet.h>

#define BUFFER_LENGTH    4096
//#define BUFFER_LENGTH    8214

#define YSIZE 1024
#define XSIZE 512

#define SERVER_PORT    50004
#define SERVER_IP    "10.30.10.2"

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


//simple routine to get data from UDP socket
int get_message(int sd, jungfrau_packet * packet){
    struct sockaddr_in clientaddr;
    int    clientaddrlen = sizeof(clientaddr);

    /* 
       int packet_size;
       packet_size = sizeof(*packet) - 8 - 1;

     */

    //ssize_t nbytes = recvfrom(sd, packet, sizeof(*packet) - 8 - 1, 0, (struct sockaddr *)&clientaddr, &clientaddrlen);
    //ssize_t nbytes = recvfrom(sd, packet, sizeof(*packet), 0, 
    //			      (struct sockaddr *)&clientaddr, &clientaddrlen);
  

    ssize_t nbytes = recv(sd, packet, sizeof(*packet) - 8 - 1, 0); //, MSG_DONTWAIT);
    packet->framenum = (((int)(packet->framenum2[2])&0xff)<<16) + (((int)(packet->framenum2[1])&0xff)<<8) +((int)(packet->framenum2[0])&0xff);
  
    packet->packetnum =  (uint16_t)((packet->packetnum2));

    /*
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
    */
  return nbytes;
}



int main(int argc, char *argv[]){
  /*
#pragma pack(push)
#pragma pack(2)
  struct mystruct{
    char emptyheader[6]; 
    uint32_t reserved;
    char packetnum;
    char framenum[3];
    uint64_t bunchid;
    uint16_t data[BUFFER_LENGTH];
  };
  struct mystruct packet;
#pragma pack(pop)
*/
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
  
  int val=2000 * 1024 * 1024;
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

  struct sockaddr_in clientaddr;
  int    clientaddrlen = sizeof(clientaddr);
  ssize_t nbytes;

  while(1==1){
    data_len = get_message(sd, &packet);
    //nbytes = recvfrom(sd, &packet, sizeof(packet), 0, 
    //(struct sockaddr *)&clientaddr, &clientaddrlen);
  

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

