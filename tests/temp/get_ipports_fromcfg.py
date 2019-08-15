"""

0:rx_tcpport 1991
0:rx_udpport 50011
0:rx_udpport2 50012
0:rx_udpip 10.0.30.210
0:detectorip 10.0.30.100

"""

import subprocess

fname = "/sls/X12SA/data/x12saop/EigerPackage/eiger_9m_10gb_xbl-daq-27_vcons_latesummer_mixip.config"


def get_ips_ports_fromcfg(fname):

    f = open(fname)

    ips = subprocess.check_output(["grep", "rx_udpip", fname])
    ports = subprocess.check_output(["grep", "rx_udpport", fname])

    ips = [i.split(":") for i in ips.replace("rx_udpip ", "").split("\n") if i !=""]
    ips = dict([[int(i[0]), i[1]] for i in ips])

    ports1 = [i.split(":") for i in ports.replace("rx_udpport ", "").split("\n") if i.find("rx_udpport2") == -1 and i != ""]
    ports1 = dict([[int(i[0]), i[1]] for i in ports1])
    ports2 = [i.split(":") for i in ports.replace("rx_udpport2 ", "").split("\n") if i.find("rx_udpport") == -1 and i != ""]
    ports2 = dict([[int(i[0]), i[1]] for i in ports2])

    lips = []
    lports = []

    for i, j in sorted(ips.iteritems()): 
        lips.append(j)
        lips.append(j)

    for i in sorted(ips): 
        lports.append(int(ports1[i]))
        lports.append(int(ports2[i]))

    return lips, lports
