import os

from mininet.net import Containernet
from mininet.node import Controller, Docker
from mininet.link import TCLink

#                                         s1
#                                  ______| |______
#                                 s2              s3
#                             ___| |___       ___| |___
#                           h1        h2     h3       h4

def topo():
    network = Containernet(controller=Controller, ipBase='1.0.0.1/24')

    s1 = network.addSwitch('s1')
    s2 = network.addSwitch('s2')
    s3 = network.addSwitch('s3')

    docker_image = "testbed:basic"
    home_path = os.path.expanduser('~')

    h1 = network.addHost('h1', cls=Docker, ip="1.0.0.101", dimage=docker_image, defaultRoute='via 1.0.0.1',
                        volumes=[home_path + "/SDN-Testbed/traffic/:/root/traffic"])
    h2 = network.addHost('h2', cls=Docker, ip="1.0.0.102", dimage=docker_image, defaultRoute='via 1.0.0.1',
                         volumes=[home_path + "/SDN-Testbed/traffic/:/root/traffic"])
    h3 = network.addHost('h3', cls=Docker, ip="1.0.0.103", dimage=docker_image, defaultRoute='via 1.0.0.1',
                         volumes=[home_path + "/SDN-Testbed/traffic/:/root/traffic"])
    h4 = network.addHost('h4', cls=Docker, ip="1.0.0.104", dimage=docker_image, defaultRoute='via 1.0.0.1',
                         volumes=[home_path + "/SDN-Testbed/traffic/:/root/traffic"])

    network.addLink(s1, s2, cls=TCLink, delay='10ms', bw=10)
    network.addLink(s1, s3, cls=TCLink, delay='15ms', bw=10)

    network.addLink(s2, h1, cls=TCLink, delay='10ms', bw=10)
    network.addLink(s2, h2, cls=TCLink, delay='10ms', bw=10)
    network.addLink(s3, h3, cls=TCLink, delay='20ms', bw=10)
    network.addLink(s3, h4, cls=TCLink, delay='20ms', bw=10)

    return network

