//gcc -o test_cache -I ../ringbuffer/src/ -L ../ringbuffer/ringbuffer/lib/ -lringbuffer test_cache.c  -lringbuffer -lm


#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include "ring_buffer.h"
#include <assert.h>
#include <inttypes.h>


typedef struct _jungfrau_header{
  uint64_t framemetadata[8];
} jungfrau_header;


int main(int argc, char * argv[]){

  int ret, id, lineid;
  rb_slot_id slot;
  jungfrau_header *p1; 

  jungfrau_header headers[100];
  
  if(argc != 3){
    printf("USAGE\n");
    return 1;
  }

  id = atoi(argv[1]);
  lineid = atoi(argv[2]);

    
  if(id == 0){
    printf("id is 0, creating header file\n");
    //ret = rb_create_header_file("header.dat");
    //assert(ret == true);
  }
  //else
  //  sleep(1);

  rb_header_id header_id = rb_open_header_file("header.dat");
  //rb_print_header(header_id);

  rb_client_id writer = rb_create_writer(header_id, id, 0, (int const []) {}); //(int const []) {2});
 
  // connect buffers
  rb_buffer_id buffer_id = rb_attach_buffer_to_header("/dev/shm/eiger/rb_image_header.dat", header_id, 0);
  //set stride to image size
  rb_set_buffer_stride_in_byte(buffer_id, 6400);
  rb_adjust_nslots(header_id);
  //rb_print_header(header_id);

  //slot = rb_claim_next_slot(writer);
  //p1 = (jungfrau_header *) rb_get_buffer_slot(buffer_id, slot);
    
  for(int j=0; j<1000; j++){
    for(int i=0; i<1000000; i++){
      slot = rb_claim_next_slot(writer);
    
      p1 = (jungfrau_header *) rb_get_buffer_slot(buffer_id, slot);
      
      p1[lineid].framemetadata[id] = (uint64_t) id;
      //printf("Got %d slot %d\n", writer, slot);
      rb_commit_slot(writer, slot);
  }
  //for(int i=0; i<10; i++)
   // printf("%lu ", p1[lineid].framemetadata[i]);
  //printf("\n");
  //assert(rb_commit_slot(writer, slot) == true);
  }
  
}
