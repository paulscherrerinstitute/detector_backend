
RINGBUFFER=$(PWD)/../../../

CC=gcc

LIBDIR=$(RINGBUFFER)/ringbuffer/ringbuffer/lib/
CFLAGS=-I$(RINGBUFFER)/ringbuffer/src/ -L$(LIBDIR) -lringbuffer -Wl,-rpath $(LIBDIR) -Wall -fno-inline
CFLAGS+=-Wfatal-errors
DEBUG_FLAGS=-g -O0 

build: debug_single_module.c generate_module_eiger.c
	@if [ -z $(DETECTOR) ]; then echo "DETECTOR variable is not set"; exit 1; fi;	
	
	@echo "-------------------------------"
	@echo "Building debug module for $(DETECTOR)"
	@echo "-------------------------------"

	$(CC) --std=c99 -D$(DETECTOR) $(DEBUG_FLAGS) $(CFLAGS) -o debug_single_module debug_single_module.c -lm -lringbuffer 
	$(CC) --std=c99 $(DEBUG_FLAGS) $(CFLAGS) -o generate_module_eiger generate_module_eiger.c

perf: DEBUG_FLAGS=-p -g -O3
perf: build

clean: 
	rm -f $(LIBNAME)
