CC=gcc

LIBNAME=libudpreceiver
#LIBDIR=/home/dbe/ringbuffer/ringbuffer/lib/
LIBDIR=/home/l_det/Work/ringbuffer/ringbuffer/lib/
#LIBDIR=/home/sala/Work/GIT/psi/HPDI/ringbuffer/ringbuffer/lib/
CFLAGS=-I../ringbuffer/src/ -L$(LIBDIR) -lringbuffer -Wl,-rpath=$(LIBDIR) -Wall

all: udp_receiver.c
	#$(CC) -shared -fPIC -DDEBUG -O3 -o $(LIBNAME).so $?
	#$(CC) -shared -fPIC -O3 $(CFLAGS) -o $(LIBNAME).so $?
	$(CC) -march=core-avx2 -shared -fPIC -O2 $(CFLAGS) -o $(LIBNAME).so $? -lringbuffer
