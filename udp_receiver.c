#include <stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

// for uint64 printing
#include <inttypes.h>


#define BUFFER_LENGTH    8214

//Jungfrau
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
  /* uint64_t framenum;   //  modified dec 15 */
  /* uint64_t packetnum;     */
  uint16_t data[BUFFER_LENGTH];
  uint16_t framenum;
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
                printf("+ C ");
                //printf("-%6c-\t", packet->emptyheader);
                printf("%u ", packet->framenum);
                printf("%u ", packet->packetnum);
                printf("%hu ", packet->data[0]);
                printf("%hu ", packet->data[4095]);
                printf("%hu ", packet->data[4096]);
                printf("%hu ", packet->data[BUFFER_LENGTH - 1]);
                printf("%hu \n", packet->data[BUFFER_LENGTH]);
        }
#endif
        return nbytes;
}

//simple routine to get data from UDP socket
int get_message(int sd, jungfrau_packet * packet){
        ssize_t nbytes = recv(sd, packet, sizeof(*packet) - 16 - 8, MSG_DONTWAIT);
        packet->framenum = (((int)(packet->framenum2[2])&0xff)<<16) + (((int)(packet->framenum2[1])&0xff)<<8) +((int)(packet->framenum2[0])&0xff);

        // does not work
        //packet->framenum =  (uint16_t)(packet->framenum2)&0x00ffffff;
        packet->packetnum =  (uint8_t)((packet->packetnum2));

        //if(nbytes >= 0)
        //  printf("%c %d %d\n", packet->packetnum2, packet->packetnum, packet->framenum);


#ifdef DEBUG
        if(nbytes >= 0){
           printf("+ C ");
          //printf("-%6c-\t", packet->emptyheader);
          printf("%u ", packet->framenum);
          printf("%u ", packet->packetnum);
          printf("%hu ", packet->data[0]);
          printf("%hu ", packet->data[4095]);
          printf("%hu ", packet->data[4096]);
          printf("%hu ", packet->data[BUFFER_LENGTH - 1]);
          printf("%hu \n", packet->data[BUFFER_LENGTH]);
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

/*
int main(){
	int ret;

	sd = socket(AF_INET, SOCK_DGRAM, 0);
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
	
	rc = bind(sd, (struct sockaddr *)&serveraddr, sizeof(serveraddr));
	printf("RC bind: %d\n", rc);
	//ret = setsockopt(socket, SOL_SOCKET, SO_RCVBUF, &val, sizeof(int));
	//printf("%d\n", ret);

	while(1)
		get_message(sd);
}
*/
