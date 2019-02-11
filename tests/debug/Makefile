
RINGBUFFER=$(PWD)/../../../

CC=gcc

LIBNAME=debug_single_module
LIBDIR=$(RINGBUFFER)/ringbuffer/ringbuffer/lib/
CFLAGS=-I$(RINGBUFFER)/ringbuffer/src/ -L$(LIBDIR) -lringbuffer -Wl,-rpath=$(LIBDIR) -Wall -fno-inline
CFLAGS+=-Wfatal-errors
DEBUG_FLAGS=-g -O0 

build: debug_single_module.c
	@if [ -z $(DETECTOR) ]; then echo "DETECTOR variable is not set"; exit 1; fi;	
	
	@echo "-------------------------------"
	@echo "Building debug module for $(DETECTOR)"
	@echo "-------------------------------"

	$(CC) --std=c99 -D$(DETECTOR) $(DEBUG_FLAGS) $(CFLAGS) -o $(LIBNAME) $? -lm -lringbuffer 

perf: DEBUG_FLAGS+=-p
perf: debug

clean: 
	rm -f $(LIBNAME)
