// header struct for RB - to be updated to include the framenums of all modules
#include <inttypes.h>


typedef struct _detector{
    char detector_name[10];
    uint8_t submodule_n;
    int32_t detector_size[2]; 
    int32_t module_size[2]; 
    int32_t submodule_size[2]; 
    int32_t module_idx[2]; 
    int32_t submodule_idx[2];
    uint16_t gap_px_chips[2];
    uint16_t gap_px_modules[2];
} detector;

typedef struct _rb_header{
  // Field 0: frame number
  // Field 1: packets lost
  // Field 2: packets counter 0-63
  // Field 3: packets counter 64-127
  // Field 4: pulse id
  // Field 5: debug (daq_rec) - gain flag
  // Field 6: module number
  // Field 7: module enabled

  uint64_t framemetadata[8];
} rb_header;

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
