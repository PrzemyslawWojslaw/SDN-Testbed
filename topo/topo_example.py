from mininet.topo import Topo
from mininet.node import Docker
from mininet.link import TCLink

#                                         s1
#                                  ______| |_______________
#                                 s2                      s3
#                             ___| |___               ___| |___
#                           h1        h2             |         |
#                                              h3---s4        s5---h4
#                                                    |___   __|
#                                                        | |
#                                                        s6
#                                                        |
#                                                       h5

class MyTopo(Topo):
    """Example topology"""
    def __init__(self):
        Topo.__init__(self)

        ip_list = ['10.0.0.11',
                   '10.0.0.22',
                   '10.0.0.33',
                   '10.0.0.44',
                   '10.0.0.55']

        for i in range(len(ip_list)):
            h = self.addHost('h' + str(i + 1), cls=Docker, ip=ip_list[i], dimage="testbed:basic")

        for i in range(6):
            s = self.addSwitch('s' + str(i + 1))

        hosts = self.hosts()
        switches = self.switches()
        self.addLink(switches[0], switches[1], cls=TCLink, delay='10ms', bw=10)
        self.addLink(switches[0], switches[2], cls=TCLink, delay='10ms', bw=10)
        self.addLink(switches[2], switches[3], cls=TCLink, delay='10ms', bw=10)
        self.addLink(switches[2], switches[4], cls=TCLink, delay='10ms', bw=10)
        self.addLink(switches[3], switches[5], cls=TCLink, delay='10ms', bw=10)
        self.addLink(switches[4], switches[5], cls=TCLink, delay='10ms', bw=10)

        self.addLink(hosts[0], switches[1], cls=TCLink, delay='20ms', bw=10)
        self.addLink(hosts[1], switches[1], cls=TCLink, delay='20ms', bw=10)
        self.addLink(hosts[2], switches[3], cls=TCLink, delay='20ms', bw=10)
        self.addLink(hosts[3], switches[4], cls=TCLink, delay='20ms', bw=10)
        self.addLink(hosts[4], switches[5], cls=TCLink, delay='20ms', bw=10)

topos = {'mytopo': MyTopo}  # terminal version: "sudo mn --custom ./topo/topo_example.py --topo=mytopo"
