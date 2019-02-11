
RINGBUFFER=$(PWD)/..

CC=gcc

LIBNAME=libudpreceiver
LIBDIR=$(RINGBUFFER)/ringbuffer/ringbuffer/lib/
CFLAGS=-I$(RINGBUFFER)/ringbuffer/src/ -L$(LIBDIR) -lringbuffer -Wl,-rpath=$(LIBDIR) -Wall
CFLAGS+=-Wfatal-errors


build: src/udp_receiver.c
	@if [ -z $(DETECTOR) ]; then echo "DETECTOR variable is not set"; exit 1; fi;	
	
	@echo "-------------------------------"
	@echo "Building backend for $(DETECTOR)"
	@echo "-------------------------------"
	
	$(CC) --std=c99 -march=core-avx2 -shared -fPIC -O2 -D$(DETECTOR) $(CFLAGS) -o $(LIBNAME).so $? -lringbuffer 


debug: CFLAGS+= -DDEBUG
debug: build

clean: 
	rm -f $(LIBNAME).so
