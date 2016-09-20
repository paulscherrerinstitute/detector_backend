CC=gcc

LIBNAME=libudpreceiver

all: udp_receiver.c
	#$(CC) -shared -fPIC -DDEBUG -O3 -o $(LIBNAME).so $?
	$(CC) -shared -fPIC -O3 -o $(LIBNAME).so $?
