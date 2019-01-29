
RINGBUFFER=$(PWD)/../../../

CC=gcc

LIBNAME=debug_single_module
LIBDIR=$(RINGBUFFER)/ringbuffer/ringbuffer/lib/
CFLAGS=-I$(RINGBUFFER)/ringbuffer/src/ -L$(LIBDIR) -lringbuffer -Wl,-rpath=$(LIBDIR) -Wall -fno-inline
CFLAGS+=-Wfatal-errors

debug: debug_single_module.c
	$(CC) --std=c99 -g -O0 $(CFLAGS) -o $(LIBNAME) $? -lm -lringbuffer 

clean: 
	rm -f $(LIBNAME)
