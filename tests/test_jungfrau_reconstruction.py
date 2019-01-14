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


def replay_jungfrau(data_dir, n_modules, n_packets=128, skip_module=[]):
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
    
    for mod in skip_module:
        print("Removing module", uri.pop(mod), l.pop(mod))

    p = []
    i = 0
    for ip, port in uri:
        print(i, ip, port)
        # run_replay(filename, ip, port, packet_length, sleep_time=0.01, nframes=100)
        p.append(multiprocessing.Process(target=socket_replay.run_replay, args=(data_dir + l[i], ip, port, packet_length, 0.005, n_packets)))
        i += 1
        p[-1].start()


def recv_array(socket, flags=0, copy=True, track=False, modulo=10):
    """recv a numpy array"""
    md = socket.recv_json(flags=flags)
    #print(md)
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
        self.packets_frame = 128
        self.n_frames = 10
        
    def tearDown(self):
        self.zmq_recv.close()
        self.p.terminate()
        self.p.kill()
        self.p.wait()

    def run_test(self, name, config, n_modules, reference, n_frames=1, n_packets=128, start_backend=True):
        data_dir = "../data/" + name + "/"
        if start_backend:
            self.p = subprocess.Popen(shlex.split("mpirun -n %d mpi-dafld --config-file %s" % (n_modules + 3, config)))

        sleep(2)
        while self.client.state is None:
            sleep(1)
            continue
        sleep(2)
        self.assertEqual(self.client.state, "INITIALIZED")

        self.client.configure({"settings": {"bit_depth": 16}})
        sleep(1)
        self.assertEqual(self.client.state, "CONFIGURED")
        self.client.open()
        sleep(1)
        self.assertEqual(self.client.state, "OPEN")

        self.zmq_recv.connect("tcp://127.0.0.1:40000")
        sleep(1)
        replay_jungfrau(data_dir, n_modules, n_packets=n_packets * n_frames)
        md_data = [[], []]
        for i in range(n_frames):
            md, data = recv_array(self.zmq_recv)
            md_data[0].append(md)
            md_data[1].append(data)
            # print(md_data[-1])
        self.client.reset()
        self.assertEqual(self.client.state, "INITIALIZED")
        return md_data

    def return_test(self, name, md_data, reference):
        np.save("result_%s.npy" % name, md_data)
        reference_data = np.load(reference, encoding="bytes")
        # TODO save new headers
        #self.assertTrue((md_data[0] == reference_data[0]).all())
        for i in range(self.n_frames):
            for k, v in reference_data[0][i].items():
                self.assertEqual(v, md_data[0][i][k])
                
        self.assertTrue((np.array([x for x in md_data[1]]) == np.array([x for  x in reference_data[1]])).all())

    def test_reco4p5M(self, start_backend=True):
        # self.data_dir = "../data/jungfrau_alvra_4p5/"
        name = "jungfrau_alvra_4p5"
        reference = "../data/jungfrau_alvra_4p5_reference.npy"
        n_modules = 9
        # maybe use picke.dump here
        md_data = self.run_test(name=name, n_modules=n_modules,
                      config="../configs/config_jf_4.5_local.py", reference=reference, n_frames=self.n_frames, start_backend=start_backend)
        np.save("result_%s.npy" % name, md_data)
        self.return_test(name, md_data, reference)
        
    def test_reco0p5M(self):
        # self.data_dir = "../data/jungfrau_alvra_4p5/"
        name = "jungfrau_alvra_4p5"
        reference = "../data/jungfrau_alvra_0p5_reference.npy"
        n_modules = 1
        # maybe use picke.dump here
        md_data = self.run_test(name=name, n_modules=n_modules,
                      config="../configs/config_jf_0.5_local.py", reference=reference, n_frames=self.n_frames)
        np.save("result_%s.npy" % name, md_data)
        self.return_test(name, md_data, reference)

    def test_multiple_runs(self):
        first_run = True
        for i in range(3):
            self.test_reco4p5M(start_backend=first_run)
            first_run = False

    def test_packetloss(self, ):
        name = "jf_testbed_15_newfw"
        reference = "../data/jf_testbed_15_newfw_reference.npy"
        n_modules = 3
        config = "../configs/config_jf_1.5_local.py"
        md_data = self.run_test(name=name, n_modules=n_modules,
                                 config=config, reference=reference, n_packets=127, n_frames=1)
        np.save("result_%s.npy" % name, md_data)
        self.assertEqual([bin(i) for i in md_data[0][0]["missing_packets_1"]], n_modules * ['0b0', ])
        self.assertEqual([bin(i) for i in md_data[0][0]["missing_packets_2"]], n_modules * ['0b1' + 63 * '0', ])

    def test_moduleloss(self, ):
        name = "jungfrau_alvra_4p5"
        #name = "jf_testbed_15_newfw"
        reference = "../data/jungfrau_alvra_4p5_reference_missingmodule.npy"
        n_modules = 9
        config = "../configs/config_jf_4.5_local_missingmodule.py"

        data_dir = "../data/" + name + "/"

        self.p = subprocess.Popen(shlex.split("mpirun -n %d mpi-dafld --config-file %s" % (n_modules + 3, config)))

        sleep(2)
        while self.client.state is None:
            sleep(1)
            continue
        sleep(1)
        self.assertEqual(self.client.state, "INITIALIZED")

        self.client.configure({"settings": {}})
        sleep(1)
        self.assertEqual(self.client.state, "CONFIGURED")
        self.client.open()
        sleep(1)
        self.assertEqual(self.client.state, "OPEN")

        self.zmq_recv.connect("tcp://127.0.0.1:40000")
        sleep(1)
        replay_jungfrau(data_dir, n_modules, skip_module=[2,], n_packets=self.n_frames * 128)

        md_data = [[], []]
        for i in range(self.n_frames):
            md, data = recv_array(self.zmq_recv)
            md_data[0].append(md)
            md_data[1].append(data)

        np.save("result_%s.npy" % name, md_data)
        self.return_test(name, md_data, reference)

if __name__ == "__main__":
    unittest.main()
