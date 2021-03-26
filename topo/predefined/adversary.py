import os

from mininet.net import Containernet
from mininet.node import Controller, Docker
from mininet.link import TCLink

#                                        s_adv1
#                                  ______| |______
#                             h_adv1            h_adv2

def topo():
    network = Containernet(controller=Controller, ipBase='44.44.44.1/24')

    s_adv1 = network.addSwitch('s_adv1')

    docker_image = "testbed:basic"
    home_path = os.path.expanduser('~')

    h_adv1 = network.addHost('h_adv1', cls=Docker, ip="44.44.44.41", dimage=docker_image, defaultRoute='via 44.44.44.1',
                        volumes=[home_path + "/SDN-Testbed/traffic/:/root/traffic"])
    h_adv2 = network.addHost('h_adv2', cls=Docker, ip="44.44.44.42", dimage=docker_image, defaultRoute='via 44.44.44.1',
                         volumes=[home_path + "/SDN-Testbed/traffic/:/root/traffic"])

    network.addLink(s_adv1, h_adv1, cls=TCLink, delay='10ms', bw=10)
    network.addLink(s_adv1, h_adv2, cls=TCLink, delay='10ms', bw=10)

    return network

