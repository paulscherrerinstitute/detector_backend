#include <string.h>
#include "detectors.h"

#define EIGER_BYTES_PER_PACKET 4144
#define EIGER_DATA_BYTES_PER_PACKET 4096
#define EIGER_MIN_VALID_PACKET_SIZE 41

// 48 bytes + 4096 bytes = 4144 bytes.
typedef struct _eiger_packet {
  detector_common_packet metadata;
  char data[EIGER_DATA_BYTES_PER_PACKET];
} eiger_packet;

barebone_packet interpret_udp_packet (
  const char* udp_packet, const int received_packet_len ) 
{
  eiger_packet* packet = (eiger_packet*) udp_packet;

  barebone_packet bpacket;
  bpacket.data = packet->data;
  bpacket.data_len = received_packet_len;
  bpacket.framenum = packet->metadata.framenum;
  bpacket.packetnum = packet->metadata.packetnum;
  bpacket.is_valid = received_packet_len >= EIGER_MIN_VALID_PACKET_SIZE;

  return bpacket;
}
