CC=gcc

RINGBUFFER=..
LIBDIR=$(RINGBUFFER)/ringbuffer/ringbuffer/lib/
CFLAGS=-I$(RINGBUFFER)/ringbuffer/src/ -I${CONDA_PREFIX}/include -L$(LIBDIR) -lringbuffer -Wl,-rpath,$(LIBDIR) -Wall
CFLAGS+= -Wfatal-errors

all: build_assembler build_receiver

build_receiver: src/udp_receiver.c
	@if [ -z $(DETECTOR) ]; then echo "DETECTOR variable is not set"; exit 1; fi;	
	
	@echo "-------------------------------"
	@echo "Building backend for $(DETECTOR)"
	@echo "-------------------------------"
	
	$(CC) --std=c99 -march=core-avx2 -shared -fPIC -O2 -D$(DETECTOR) $(CFLAGS) -o libudpreceiver.so $?

build_assembler: src/image_assembler.c
	@echo "-------------------------------"
	@echo "Building assembler"
	@echo "-------------------------------"

	$(CC) --std=c99 -march=core-avx2 -shared -fPIC -O2 -Wfatal-errors -o libimageassembler.so $?


debug: CFLAGS+= -DDEBUG
debug: build

clean: 
	rm -f libudpreceiver.so
	rm -f libimageassembler.so
