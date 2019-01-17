import unittest
from detector_replay import eiger_replay
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


def replay_eiger(data_dir, n_modules, start_from_file=0, frames=1, n_packets=64):
    receiver_ips = 4 * ["127.0.0.1"]
    #receiver_ips = 2 * ["10.0.30.210"] + 2 * ["10.0.40.210"]
    receiver_ips = n_modules * receiver_ips
    # submodule numeration differs from the one in the setup file
    receiver_ports = [50011 + i for i in range(4)]

    for m in range(1, n_modules):
        receiver_ports += [i + m * 4 for i in receiver_ports[:4]]

    uri = zip(n_modules * receiver_ips, receiver_ports)

    l = os.listdir(data_dir)
    l = sorted(l, key=lambda x: x.split("_")[-1])
    print(l)
    p = []
    i = start_from_file
    for ip, port in uri:
        if old_header:
            p.append(multiprocessing.Process(target=eiger_replay.run_replay, args=(data_dir + l[i], ip, port, 4112, 0.1, frames, 
                    48, n_packets)))
        else:
            p.append(multiprocessing.Process(target=eiger_replay.run_replay, args=(data_dir + l[i], ip, port, 4144, 0.1, frames, 
                    40, n_packets)))
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
        self.data_dir = "../data/eiger9M_hv1_test_16b/"
        self.client = DaflClient("http://localhost:8080/v1")
        self.prepare_rb = subprocess.Popen(shlex.split("sh ../scripts/create_rb_files.sh 100"))
        self.prepare_rb.wait()
        ctx = zmq.Context()
        self.zmq_recv = ctx.socket(zmq.PULL)
        
    def tearDown(self):
        self.zmq_recv.close()
        self.p.terminate()
        self.p.kill()
        self.p.wait()

    def run_test(self, name, config, n_modules, reference, n_frames=1, n_packets=64, start_backend=True, bit_depth=16):
        data_dir = "../data/" + name + "/"
        if start_backend:
            self.p = subprocess.Popen(shlex.split("mpirun -n %d mpi-dafld --config-file %s" % (4 * n_modules + 3, config)))

        sleep(2)
        while self.client.state is None:
            sleep(2)
            continue
        sleep(n_modules / 2)
        self.assertEqual(self.client.state, "INITIALIZED")

        self.client.configure({"settings": {"bit_depth": bit_depth}})
        sleep(2)
        self.assertEqual(self.client.state, "CONFIGURED")
        self.client.open()
        sleep(2)
        self.assertEqual(self.client.state, "OPEN")

        self.zmq_recv.connect("tcp://127.0.0.1:40000")
        sleep(1)
        replay_eiger(data_dir, n_modules, n_packets=n_packets * n_frames)
        md_data = [[], []]
        for i in range(n_frames):
            md, data = recv_array(self.zmq_recv)
            md_data[0].append(md)
            md_data[1].append(data)
            print("BBBBBBBBBBBBBBBBBB", md_data[-1])
        self.client.reset()
        self.assertEqual(self.client.state, "INITIALIZED")
        return md_data

    def return_test(self, name, md_data, reference):
        np.save("result_%s.npy" % name, md_data)
        reference_data = np.load(reference, encoding="bytes")
        # TODO save new headers
        #self.assertTrue((md_data[0] == reference_data[0]).all())
        #for i in range(self.n_frames):
        if len(reference_data.shape) == 2:
            acquired_data = np.array(md_data[1])
            comparison_data = np.array(reference_data)

            np.testing.assert_array_equal(acquired_data, comparison_data)
        else:
            acquired_data = np.array(md_data[1])
            comparison_data = np.array(reference_data[1])

            np.testing.assert_array_equal(acquired_data, comparison_data)

    def test_reco05M_16b(self):
        name = "eiger9M_hv1_test_16b"
        self.data_dir = "../data/%s/" % name
        if old_header:
            self.data_dir = "../data/eiger_9m_grid/"

        reference = "../data/%s.npy" % name
        n_modules = 18
        md_data = self.run_test(name=name, n_modules=n_modules,
                      config="../configs/config_eiger_local.py", reference=reference, n_frames=1, n_packets=64)
        np.save("result.npy", md_data)
        self.return_test(name, md_data, reference)

    def test_reco9M_16b(self):
        name = "eiger9M_hv1_test_16b"
        self.data_dir = "../data/%s/" % name
        if old_header:
            self.data_dir = "../data/eiger_9m_grid/"

        reference = "../data/%s.npy" % name
        n_modules = 18
        md_data = self.run_test(name=name, n_modules=n_modules,
                      config="../configs/config_eiger9M_local.py", reference=reference, n_frames=1, n_packets=64)
        np.save("result_%s.npy" % name, md_data)
        self.return_test(name, md_data, reference)

    def test_reco9M_8b(self):
        name = "eiger9M_hv1_test_8b"
        self.data_dir = "../data/%s/" % name
        if old_header:
            self.data_dir = "../data/eiger_9m_grid/"

        reference = "../data/%s.npy" % name
        n_modules = 2 * 9
        md_data = self.run_test(name=name, n_modules=n_modules,
                      config="../configs/config_eiger9M_local.py", reference=reference, n_frames=1, n_packets=32, bit_depth=8)
        np.save("result_%s.npy" % name, md_data)
        self.return_test(name, md_data, reference)

    def test_reco9M_32b(self):
        name = "eiger9M_hv1_test_32b"
        self.data_dir = "../data/%s/" % name
        if old_header:
            self.data_dir = "../data/eiger_9m_grid/"

        reference = "../data/%s.npy" % name
        n_modules = 2 * 9
        md_data = self.run_test(name=name, n_modules=n_modules,
                      config="../configs/config_eiger9M_local.py", reference=reference, n_frames=1, n_packets=128, bit_depth=32)
        np.save("result_%s.npy" % name, md_data)
        self.return_test(name, md_data, reference)

    def test_packetloss(self, ):
        name = "eiger9M_hv1_test_16b"
        reference = "../data/jf_testbed_15_newfw_reference.npy"
        n_modules = 2 * 9
        config = "../configs/config_eiger9M_local.py"
        md_data = self.run_test(name=name, n_modules=n_modules,
                                 config=config, reference=reference, n_packets=63, n_frames=1, bit_depth=16)
        np.save("result_%s.npy" % name, md_data)
        print(md_data[0])
        self.assertEqual([bin(i) for i in md_data[0][0]["missing_packets_1"]], n_modules * ['0b0', ])
        self.assertEqual([bin(i) for i in md_data[0][0]["missing_packets_2"]], n_modules * ['0b1' + 63 * '0', ])

if __name__ == "__main__":
    unittest.main()