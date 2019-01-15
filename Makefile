
RINGBUFFER=$(PWD)/..

CC=gcc

LIBNAME=libudpreceiver
LIBDIR=$(RINGBUFFER)/ringbuffer/ringbuffer/lib/
CFLAGS=-I$(RINGBUFFER)/ringbuffer/src/ -L$(LIBDIR) -lringbuffer -Wl,-rpath=$(LIBDIR) -Wall
CFLAGS+=-Wfatal-errors
CFLAGS+= -DDEBUG

all: src/udp_receiver.c
	#$(CC) -shared -fPIC -DDEBUG -O3 -o $(LIBNAME).so $?
	#$(CC) -shared -fPIC -O3 $(CFLAGS) -o $(LIBNAME).so $?
	$(CC) --std=c99 -march=core-avx2 -shared -fPIC -O2 $(CFLAGS) -o $(LIBNAME).so $? -lringbuffer 

debug: CFLAGS+= -DDEBUG
debug: all

clean: 
	rm $(LIBNAME).so