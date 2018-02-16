import unittest
from detector_replay import socket_replay
import multiprocessing
import subprocess
import shlex
import sys
from time import sleep
import zmq
import numpy as np
import os
sys.path.append("../")
from dafl_client import DaflClient

old_header = False


def replay_jungfrau(data_dir, n_modules, n_packets=128):
    n_submodules = 1
    packet_length = 8246
    receiver_ips = n_submodules * ["127.0.0.1"]
    #receiver_ips = 2 * ["10.0.30.210"] + 2 * ["10.0.40.210"]
    receiver_ips = n_modules * receiver_ips
    # submodule numeration differs from the one in the setup file
    receiver_ports = [10001 + i for i in range(n_modules)]
    
    uri = zip(n_modules * receiver_ips, receiver_ports)
    
    l = os.listdir(data_dir)
    l = sorted(l, key=lambda x: x.split("_")[-1])
    
    p = []
    i = 0
    for ip, port in uri:
        print(i, ip, port)
        # run_replay(filename, ip, port, packet_length, sleep_time=0.01, nframes=100)
        p.append(multiprocessing.Process(target=socket_replay.run_replay, args=(data_dir + l[i], ip, port, packet_length, 0.01, n_packets)))
        i += 1
        p[-1].start()


def recv_array(socket, flags=0, copy=True, track=False, modulo=10):
    """recv a numpy array"""
    md = socket.recv_json(flags=flags)
    print(md)
    msg = socket.recv(copy=copy, track=track)
    buf = buffer(msg)
    A = np.frombuffer(buf, dtype=md['type'])
    return md, A.reshape(md['shape'])


class BaseTests(unittest.TestCase):
    def setUp(self):
        self.data_dir = ""
        self.client = DaflClient("http://localhost:8081/v1")
        self.prepare_rb = subprocess.Popen(shlex.split("sh ../scripts/create_rb_files.sh 100"))
        self.prepare_rb.wait()
        ctx = zmq.Context()
        self.zmq_recv = ctx.socket(zmq.PULL)
        
    def tearDown(self):
        self.zmq_recv.close()
        self.p.terminate()
        self.p.kill()
        self.p.wait()

    def run_test(self, name, config, n_modules, reference, n_packets=128):
        data_dir = "../data/" + name + "/"
        self.p = subprocess.Popen(shlex.split("mpirun -n %d mpi-dafld --config-file %s" % (n_modules + 3, config)))

        while self.client.state is None:
            sleep(2)
            continue
        sleep(2)
        self.assertEqual(self.client.state, "INITIALIZED")

        self.client.configure({"settings": {}})
        sleep(2)
        self.assertEqual(self.client.state, "CONFIGURED")
        self.client.open()
        sleep(2)
        self.assertEqual(self.client.state, "OPEN")

        self.zmq_recv.connect("tcp://127.0.0.1:40000")
        sleep(1)
        replay_jungfrau(data_dir, n_modules, n_packets=n_packets)
        return recv_array(self.zmq_recv)
        
    def test_reco4p5M(self):
        # self.data_dir = "../data/jungfrau_alvra_4p5/"
        name = "jungfrau_alvra_4p5"
        reference = "../data/jungfrau_alvra_4p5_reference.npy"
        n_modules = 9
        md, data = self.run_test(name=name, n_modules=n_modules,
                      config="../configs/config_jf_4.5_local.py", reference=reference)
        np.save("result_%s.npy" % name, data)
        reference_data = np.load(reference)
        self.assertTrue((data == reference_data).all())
        self.assertEqual(md["pulse_id_diff"], n_modules * [0, ])

    def test_reco1p5M_testbed(self):
        # self.data_dir = "../data/jf_testbed_15_newfw/"
        name = "jf_testbed_15_newfw"
        reference = "../data/jf_testbed_15_newfw_reference.npy"
        n_modules = 3
        config = "../configs/config_jf_1.5_local.py"
        md, data = self.run_test(name=name, n_modules=n_modules,
                                 config=config, reference=reference)
        np.save("result_%s.npy" % name, data)
        reference_data = np.load(reference)
        self.assertTrue((data == reference_data).all())
        
    def test_packetloss(self, ):
        name = "jf_testbed_15_newfw"
        reference = "../data/jf_testbed_15_newfw_reference.npy"
        n_modules = 3
        config = "../configs/config_jf_1.5_local.py"
        md, data = self.run_test(name=name, n_modules=n_modules,
                                 config=config, reference=reference, n_packets=127)

        np.save("result_%s.npy" % name, data)
        self.assertEqual([bin(i) for i in md["missing_packets_1"]], n_modules * ['0b0', ])
        self.assertEqual([bin(i) for i in md["missing_packets_2"]], n_modules * ['0b1' + 63 * '0', ])

    def test_moduleloss(self, ):
        name = "jf_testbed_15_newfw"
        reference = "../data/jf_testbed_15_newfw_reference_missingmodule.npy"
        n_modules = 3
        config = "../configs/config_jf_1.5_local_missingmodule.py"

        data_dir = "../data/" + name + "/"
        self.p = subprocess.Popen(shlex.split("mpirun -n %d mpi-dafld --config-file %s" % (n_modules + 3, config)))

        while self.client.state is None:
            sleep(2)
            continue
        sleep(2)
        self.assertEqual(self.client.state, "INITIALIZED")

        self.client.configure({"settings": {}})
        sleep(2)
        self.assertEqual(self.client.state, "CONFIGURED")
        self.client.open()
        sleep(2)
        self.assertEqual(self.client.state, "OPEN")

        self.zmq_recv.connect("tcp://127.0.0.1:40000")
        sleep(1)
        replay_jungfrau(data_dir, n_modules - 1, )
        md, data = recv_array(self.zmq_recv)

        np.save("result_%s.npy" % name, data)
        reference_data = np.load(reference)
        self.assertTrue((data == reference_data).all())
