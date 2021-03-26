import abc
import os
from typing import Union, List

from mininet.topo import Topo
from mininet.link import TCLink


class IPredefinedTopology(abc.ABC):
    @staticmethod
    @abc.abstractmethod
    def getTopology() -> str:
        pass

    @staticmethod
    @abc.abstractmethod
    def getDescription() -> str:
        pass

    @staticmethod
    @abc.abstractmethod
    def getNetwork() -> Union[None, Topo, List[Topo]]:
        pass


class SmallWithAdversary(IPredefinedTopology):
    @staticmethod
    def getTopology():
        t =   "     User defined Controller                                Mininet local controller\n" \
            + "                                                    gw0\n"\
            + "                       ____________________| |__________________\n"\
            + "                     s1                                                         s_adv1\n"\
            + "            ______| |______                                          ______| |______\n"\
            + "           s2                s3                                 h_adv1              h_adv2\n"\
            + "      ___| |___       ___| |___\n"\
            + "    h1        h2     h3       h4"
        return t

    @staticmethod
    def getDescription():
        d = """Simple tree topology representing benign network connected to gateway.
        To the same gateway another network is connected, with seperate controller and IP base (44.44.44.1/24), representing adversary, hacker network.
        """
        return d

    @staticmethod
    def getNetwork() -> Union[None, Topo, List[Topo]]:
        from topo.predefined import small
        from topo.predefined import adversary

        network = small.topo()

        networkAdv = adversary.topo()
        networkAdv.addController(name='c1a', port=6639)

        switch1 = network.getNodeByName('s1')
        switch2 = networkAdv.getNodeByName('s_adv1')

        gateway = network.addNAT('gw0', ip='1.0.0.1/24', connect=False,
                                 inNamespace=False)  # inNamespace=False -> internet access
        network.addLink(switch1, gateway, cls=TCLink, delay='22ms', bw=10,
                        intfName2='gw0-eth1', params2={'ip': '1.0.0.1/24'})
        networkAdv.addLink(switch2, gateway, cls=TCLink, delay='33ms', bw=10,
                           intfName2='gw0-eth2', params2={'ip': '44.44.44.1/24'})


        gateway.cmd('ip route add default dev gw0-eth2')

        return [network, networkAdv]


class NetdataTopology(IPredefinedTopology):
    @staticmethod
    def getTopology():
        t =   "        User defined Controller\n" \
            + "                                                               gw0\n"\
            + "                                                                |\n"\
            + "                                                               s1\n"\
            + "                                               __________| |__________\n"\
            + "                                             s2                               s3\n"\
            + "                                     _____| |_____                _____| |_____\n"\
            + "                                   h1               h2             h3              h4\n"\
            + "  Netdata ports:      (19001)      (19002)     (19003)      (19004)"
        return t

    @staticmethod
    def getDescription():
        d = """Simple tree topology with hosts equipped with Netdata.\nContact monitoring program by visitng
        \"http://localhost:<host-port>>\"\n in Your web browser.
        """
        return d

    @staticmethod
    def getNetwork() -> Union[None, Topo, List[Topo]]:
        from topo.predefined import netdata

        dockerfile_path = "dockerfiles/Dockerfile.netdata"
        if os.path.isfile(dockerfile_path):
            print("+++ Preparing Netada docker image, if it does not exist. It may take a while. +++")
            os.system("sudo docker build -t testbed:netdata -f " + dockerfile_path + " >/dev/null")
        else:
            raise ValueError("Dockerfile for predefined scenario not found\n(\"" + dockerfile_path + "\")")

        network = netdata.topo()

        switch1 = network.getNodeByName('s1')
        gateway = network.addNAT('gw0', ip='1.0.0.1/24', connect=False,
                                 inNamespace=False)  # inNamespace=False -> internet access
        network.addLink(switch1, gateway, cls=TCLink, delay='22ms', bw=10,
                        intfName2='gw0-eth1', params2={'ip': '1.0.0.1/24'})

        # reroute Netdata traffic through additional docker interface, so it does not interfere wit emulated network
        for host in network.hosts:
            if host.name == "gw0":
                pass

            # disable filters for marking
            host.cmd('for i in /proc/sys/net/ipv4/conf/*/rp_filter; do sudo echo 1 > "$i"; done')
            host.cmd('sudo echo 0 > /proc/sys/net/ipv4/conf/all/rp_filter')
            host.cmd('sudo echo 0 > /proc/sys/net/ipv4/conf/eth0/rp_filter')

            # send 'Netdata' communication through special interface
            host.cmd('echo "201 netdata.out" >> /etc/iproute2/rt_tables')
            host.cmd('ip route add table netdata.out  default via 172.17.0.1 dev eth0')
            host.cmd('iptables -A PREROUTING -t mangle -p tcp --dport 19999 -j MARK --set-mark 1')
            host.cmd('iptables -A OUTPUT -t mangle -p tcp --sport 19999 -j MARK --set-mark 1')
            host.cmd('iptables --table nat -A POSTROUTING -o eth0 -p tcp --dport 19999 -j MASQUERADE')
            host.cmd('ip rule add fwmark 1 table netdata.out')

            # start Netdata
            host.cmd('service netdata start')

        return network

topos = {"Small topology with adversary" : SmallWithAdversary,
         "Hosts with Netdata monitoring" : NetdataTopology}
