import os
import logging
import importlib.util

from mininet.net import Containernet
from mininet.node import Controller, RemoteController, Docker
from mininet.link import TCLink
from mininet.log import lg
from PyQt5 import QtWidgets, QtGui

from tools import predefinedTopos

class TopoMaker():

    def __init__(self):
        self.options = None

    def createTopology(self, topoOptions):
        self.options = topoOptions
        networks = []
        mininet_logger = MyMininetLogger()
        lg.handlers.pop()  # remove default <StreamHandlerNoNewline <stderr> (Level 25)>
        lg.addHandler(mininet_logger)
        lg.setLevel(logging.INFO)

        if self.options["controllerType"] == "local" or self.options["controllerType"] == "remote" \
                or self.options["controllerType"] == "none":
            pass
        elif self.options["controllerType"] == "floodlight":
            os.system('sudo docker run -d -p ' + str(self.options["controllerPort"]) + ':6653 -p '
                      + str(self.options["controllerWebGui"]) + ':8080 --name='
                      + self.options["controllerName"] + ' glefevre/floodlight >/dev/null')
        else:
            raise ValueError("Unknown controller option", self.options["controllerType"])

        if self.options["method"] == "load":
            networks.extend(self.__createTopologyFromFile())
        elif self.options["method"] == "predefined":
            predefinedTopo = predefinedTopos.topos[self.options["path"]]
            if not issubclass(predefinedTopo, predefinedTopos.IPredefinedTopology):
                raise ValueError("Predefined topology \"" + self.options["path"] +
                                 "\" does NOT inherit a proper interface (\"IPredefinedTopology\".")
            else:
                net = predefinedTopo.getNetwork()
                if type(net) is list:
                    networks.extend(net)
                else:
                    networks.append(net)
        elif self.options["method"] == "custom":
            net = Containernet(controller=Controller, ipBase=self.options[
                "ipBase"])

            delay = str(self.options["linkDelay"]) + "ms"
            volumePath = self.options["volumeMachine"] + ":" + self.options["volumeHost"]
            gatewayIp = self.options["ipBase"].split('/')[0]
            gatewayIp = gatewayIp.split('.')
            gatewayIp = '.'.join([gatewayIp[0], gatewayIp[1], gatewayIp[2], '1'])
            gateway = net.addNAT('gw0', ip=gatewayIp, connect=False,
                                 inNamespace=(not self.options["NAT"]))


            general_parameters = (net, gateway, gatewayIp, delay, volumePath)

            if self.options["topoStyle"] == "linear":
                self.__createCustomLinear(*general_parameters, *self.options["topoSpecific"])
            elif self.options["topoStyle"] == "tree":
                self.__createCustomTree(*general_parameters, *self.options["topoSpecific"])
            elif self.options["topoStyle"] == "torus":
                self.__createCustomTorus(*general_parameters, *self.options["topoSpecific"])
            else:
                raise ValueError("Unknown custom topology style (\""
                                 + self.options["topoStyle"] + "\").")
            networks.append(net)
        else:
            raise ValueError("Unknown creation method \"" + self.options["method"] + "\".")

        local_controller = None
        for net in networks:
            if not net.controllers:
                if self.options["controllerType"] == "none":
                    pass
                elif self.options["controllerType"] == "local":
                    if local_controller is None:
                        local_controller = net.addController(name='con0')
                    else:
                        net.addController(local_controller)
                else:
                    net.addController(name='con0', controller=RemoteController,
                                      ip=self.options["controllerIp"],
                                      port=self.options["controllerPort"])
            net.start()

        return networks, mininet_logger

    def __createTopologyFromFile(self):  # file existence and topo class has been checked in Wizard
        spec = importlib.util.spec_from_file_location("topo", self.options["path"])
        topoModule = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(topoModule)

        networks = []
        for topoClass in topoModule.topos.values():
            topo = topoClass()
            if self.options["controllerType"] == "local":
                network = Containernet(topo=topo, controller=Controller)
            else:
                network = Containernet(topo=topo, controller=RemoteController)

            networks.append(network)

        return networks

    def __createCustomLinear(self, network, gateway, gatewayIp, delay, volumePath,
                             k=2, n=1):
        """k: number of switches
           n: number of hosts per switch"""

        if n == 1:
            genHostName = lambda i, j: 'h%s' % i
        else:
            genHostName = lambda i, j: 'h%ss%d' % (j, i)

        lastSwitch = None
        for i in range(1, k + 1):
            # Add switch
            switch = network.addSwitch( 's%s' % i )
            # Add hosts to switch
            for j in range(1, n + 1):
                host = network.addHost(genHostName(i, j), cls=Docker,
                                       dimage=self.options["hostImage"],
                                       defaultRoute='via ' + gatewayIp,
                                       ports=[self.options["portHost"]],
                                       port_bindings={
                                           self.options["portHost"]:
                                               self.options["portMachine"] + 100*j + i},
                                       publish_all_ports=True, volumes=[volumePath])
                network.addLink(host, switch, cls=TCLink, delay=delay,
                                bw=self.options["linkBandwidth"])
            # Connect switch to previous
            if lastSwitch:
                network.addLink(switch, lastSwitch, cls=TCLink, delay=delay,
                                bw=self.options["linkBandwidth"])
            lastSwitch = switch

        network.addLink(network.switches[0], gateway, cls=TCLink, delay=delay,
                        bw=self.options["linkBandwidth"],
                        intfName2='gw0-eth1', params2={'ip': self.options["ipBase"]})
        return network

    def __createCustomTree(self, network, gateway, gatewayIp, delay, volumePath,
                           depth=1, fanout=2):

        network.hostNum = 1
        network.switchNum = 1

        self.__addTree(network, delay, gatewayIp, volumePath, depth, fanout)
        network.addLink(network.switches[0], gateway, cls=TCLink, delay=delay,
                        bw=self.options["linkBandwidth"],
                        intfName2='gw0-eth1', params2={'ip': self.options["ipBase"]})

        return network

    def __addTree(self, network, delay, gatewayIp, volumePath, depth=1, fanout=2):
        isSwitch = depth > 0
        if isSwitch:
            node = network.addSwitch('s%s' % network.switchNum)
            network.switchNum += 1
            for _ in range(fanout):
                child = self.__addTree(network, delay, gatewayIp, volumePath, depth - 1, fanout)
                network.addLink(node, child,  cls=TCLink, delay=delay,
                                bw=self.options["linkBandwidth"])
        else:
            node = network.addHost('h%s' % network.hostNum,
                                   cls=Docker,
                                   dimage=self.options["hostImage"],
                                   defaultRoute='via ' + gatewayIp,
                                   ports=[self.options["portHost"]],
                                   port_bindings={self.options["portHost"]:
                                                      self.options["portMachine"]
                                                      + network.hostNum},
                                   publish_all_ports=True, volumes=[volumePath])
            network.hostNum += 1
        return node

    def __createCustomTorus(self, network, gateway, gatewayIp, delay, volumePath, x, y, n=1):
        """ x: dimension of torus in x-direction
            y: dimension of torus in y-direction
            n: number of hosts per switch"""
        # if x < 3 or y < 3:
        #     raise Exception( 'Please use 3x3 or greater for compatibility '
        #                      'with 2.1' )

        if n == 1:
            genHostName = lambda loc, k: 'h%s' % (loc)
        else:
            genHostName = lambda loc, k: 'h%sx%d' % (loc, k)

        hosts, switches, dpid = {}, {}, 0
        # Create and wire interior
        for i in range(x):
            for j in range(y):
                loc = '%dx%d' % (i + 1, j + 1)
                # dpid cannot be zero for OVS
                dpid = (i + 1) * 256 + (j + 1)
                switch = switches[ i, j ] = network.addSwitch(
                    's' + loc, dpid='%x' % dpid)
                for k in range(n):
                    host = hosts[i, j, k] = network.addHost(genHostName(loc, k + 1), cls=Docker,
                                                            dimage=self.options["hostImage"],
                                                            defaultRoute='via ' + gatewayIp,
                                                            ports=[self.options["portHost"]],
                                                            port_bindings={
                                                                self.options["portHost"]:
                                                                    self.options["portMachine"]
                                                                    + 100 * i + j},
                                                            publish_all_ports=True,
                                                            volumes=[volumePath])
                    network.addLink( host, switch,  cls=TCLink, delay=delay,
                                     bw=self.options["linkBandwidth"])
        # Connect switches
        for i in range(x):
            for j in range(y):
                sw1 = switches[i, j]
                sw2 = switches[i, (j + 1) % y]
                sw3 = switches[ (i + 1) % x, j]
                network.addLink(sw1, sw2,  cls=TCLink, delay=delay,
                                bw=self.options["linkBandwidth"])
                network.addLink(sw1, sw3,  cls=TCLink, delay=delay,
                                bw=self.options["linkBandwidth"])

        network.addLink(switches[0, 0], gateway, cls=TCLink, delay=delay,
                        bw=self.options["linkBandwidth"],
                        intfName2='gw0-eth1', params2={'ip': self.options["ipBase"]})

        return network


class MyMininetLogger(logging.Handler):

    def __init__(self):
        super().__init__()
        self.widget = QtWidgets.QPlainTextEdit()
        self.widget.setReadOnly(True)
        self.widget.setObjectName("plainTextLogger")

    def emit(self, record):
        msg = self.format(record)
        self.widget.moveCursor(QtGui.QTextCursor.End)
        self.widget.insertPlainText(msg)
        self.widget.moveCursor(QtGui.QTextCursor.End)
