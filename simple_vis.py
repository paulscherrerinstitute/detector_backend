import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import zmq
from time import sleep, time


THR = 70
ACCUMULATE = True


def recv_array(socket, flags=0, copy=True, track=False, modulo=10):
    """recv a numpy array"""
    #print "start recv_arr"
    md = socket.recv_json(flags=flags)
    msg = socket.recv(copy=copy, track=track)
    buf = buffer(msg)
    A = np.frombuffer(buf, dtype=md['type'])
    #print md
    #print "stop recv_arr"
    return md, A.reshape(md['shape'])


#for phase in np.linspace(0, 10*np.pi, 500):
#    line1.set_ydata(np.sin(x + phase))
#    fig.canvas.draw()

#plt.show()

ctx = zmq.Context()
socket = ctx.socket(zmq.SUB)
socket.set_hwm(1)

socket.setsockopt(zmq.SUBSCRIBE, '')
socket.connect("tcp://127.0.0.1:40000")

sleep(2)
print "connected"
md, data = recv_array(socket)  # , copy=False, track=True)
print md

fig = plt.figure(figsize=(10, 10))
ax = fig.add_subplot(111)
line1 = ax.imshow(data, vmax=20000)

plt.ion()
plt.show()

#line1 = ax.imshow(data, vmin=55000, )
plt.colorbar(line1)

prev_data = None

while True:
    md, data = recv_array(socket)
    t_i = time()
    if int(md['frame']) % 10 == 0:
    #if True:
        #line1.set_ydata(data)
        datac = data.copy()
        datac[datac < THR] = 0
        if ACCUMULATE:
            if prev_data is not None:
                datac += prev_data
            prev_data = datac
        line1.set_data(datac)
        plt.title(md['frame'])
        plt.pause(0.01)
