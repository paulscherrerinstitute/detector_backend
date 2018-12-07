#ifndef EIGER_H
#define EIGER_H

#include "detectors.h"

// 48 bytes + 4096 bytes = 4144 bytes.
typedef struct _eiger_packet {
  detector_common_packet metadata;
  char data[4096];
} eiger_packet;

#endif