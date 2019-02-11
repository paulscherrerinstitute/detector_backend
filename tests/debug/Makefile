
RINGBUFFER=$(PWD)/../../../

CC=gcc

LIBNAME=debug_single_module
LIBDIR=$(RINGBUFFER)/ringbuffer/ringbuffer/lib/
CFLAGS=-I$(RINGBUFFER)/ringbuffer/src/ -L$(LIBDIR) -lringbuffer -Wl,-rpath=$(LIBDIR) -Wall -fno-inline
CFLAGS+=-Wfatal-errors
DEBUG_FLAGS=-g -O0 

debug: debug_single_module.c
	$(CC) --std=c99 $(DEBUG_FLAGS) $(CFLAGS) -o $(LIBNAME) $? -lm -lringbuffer 

perf: DEBUG_FLAGS+=-p
perf: debug

clean: 
	rm -f $(LIBNAME)
