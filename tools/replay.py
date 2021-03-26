import os
import time
import signal
import shutil
from subprocess import Popen

from mininet.log import info, error
from mininet.util import quietRun
from mininet.link import Intf

from PyQt5 import QtCore



def checkIntf(intf):
    config = quietRun('ifconfig %s 2>/dev/null' % intf, shell=True)
    if config:
        error('Error:', intf, 'does already exist!\n')

def addVeth(node, ip, subnet):
    intfNode = node.name + "-veth0"
    intfOut = node.name + "-out0"

    infNodeIp = "4.4." + str(ip) + ".1/24"
    intfOutIp = "4.4." + str(ip) + ".2/24"

    info(
        '*** Checking if chosen virtual ethernet interface pair (' + intfNode + ' and ' + intfOut + ') does not already exist\n')
    checkIntf(intfNode)
    checkIntf(intfOut)

    info('*** Creating virtual ethernet interface pair (' + intfNode + ' and ' + intfOut + ')\n')
    os.system('sudo ip link add ' + intfNode + ' type veth peer name ' + intfOut)
    # os.system('sudo ip link add ' + intfForUser + ' type veth peer name ' + intfForSwitch)  # unnecessary - "RTNETLINK answers: File exists"

    # info('*** Setting IP address ' + intfIp + ' to virtual ethernet interface ' + intfForUser + '\n')
    os.system('sudo ip addr add ' + intfOutIp + ' dev ' + intfOut)

    # os.system('ip link set ' + intfNode + ' up')  # unnecessary (gets up within Intf()? )
    os.system('ip link set ' + intfOut + ' up')

    info('*** Adding virtual ethernet interface ' + intfNode + ' to node ' + node.name + '\n')

    _intf = Intf(intfNode, node=node)
    node.cmd('sudo ip addr add ' + infNodeIp + ' dev ' + intfNode)

    return intfNode, intfOut

class ReplayScenario():
    def __init__(self, intf1, ip1, mac1, intf2, ip2, mac2):
        self.intf1 = intf1
        self.ip1 = ip1
        self.mac1 = mac1
        self.intf2 = intf2
        self.ip2 = ip2
        self.mac2 = mac2
        self.traffic = []  # list of tuples  (pcap_path, cache_path)   <- for tcpreplay

    def appendPcap(self, original_path):
        name = original_path.split('.')[0]
        rewritten_path = name + "_rewritten.pcap"
        cache_path = name + ".cache"
        os.system('tcpprep --auto=bridge --pcap=\"' + original_path + '\" --cachefile=\"' + cache_path + '\"')
        endpoints = self.ip1 + ":" + self.ip2
        mac_1 = self.mac1 + "," + self.mac2
        mac_2 = self.mac2 + "," + self.mac1
        os.system('tcprewrite --fixcsum --endpoints=' + endpoints + ' --cachefile=\"' + cache_path
                  + '\" --enet-dmac=' + mac_2 + ' --enet-smac=' + mac_1
                  + ' --infile=\"' + original_path + '\" --outfile=\"' + rewritten_path + '\"')
        self.traffic.append((rewritten_path, cache_path))

class ReplayEngine(QtCore.QObject):
    replayersStartSignal = QtCore.pyqtSignal()
    replayersStopSignal = QtCore.pyqtSignal()

    def __init__(self, network):
        super(ReplayEngine, self).__init__()
        self.network = network
        self.trafficScenarios = []
        self.ipIntfMap = {}  # dictionary to map IP from pcap to emulated network
        self.threads = []
        self.replayerThreads = []

    def prepare(self, traffic_path, host1, host2):
        veth1, ip1, mac1 = self.prepareHost(host1)
        veth2, ip2, mac2 = self.prepareHost(host2)

        for scenario in self.trafficScenarios:
            if (scenario.intf1 == veth1 and scenario.intf2 == veth2) or (scenario.intf1 == veth2 and scenario.intf2 == veth1):
                scenario.appendPcap(traffic_path)
                return scenario

        # scenario not found - create new one
        scenario = ReplayScenario(veth1, ip1, mac1, veth2, ip2, mac2)
        scenario.appendPcap(traffic_path)
        self.trafficScenarios.append(scenario)
        return scenario

    def start(self, *chosen_scenarios):
        scenarios = []
        if len(chosen_scenarios) == 0:
            scenarios = self.trafficScenarios
        else:
            for number in chosen_scenarios:
                scenarios.append(self.trafficScenarios[number - 1])

        for scenario in scenarios:
            thread = QtCore.QThread()
            thread.start()
            replayer = ScenarioReplayer(scenario)
            replayer.moveToThread(thread)
            self.replayerThreads.append((thread, replayer))

            self.replayersStartSignal.connect(replayer.start)
            self.replayersStopSignal.connect(replayer.stop)
            self.replayerThreads.append((thread, replayer))

        self.replayersStartSignal.emit()

    def stop(self):
        self.replayersStopSignal.emit()
        for thread, replayer in self.replayerThreads:
            replayer.stop()
            thread.quit()
            thread.wait()
        self.replayerThreads.clear()

    def prepareHost(self, host_name):
        host = self.network.getNodeByName(host_name)
        ip = host.IP()
        mac = host.MAC()
        vethIp = len(self.ipIntfMap)
        if ip not in self.ipIntfMap:
            inside_intf, outside_intf = addVeth(host, vethIp, self.network.ipBase)
            network_interface = host.name + "-eth0"

            # mirror veth to network interface
            # ingress
            host.cmd("tc qdisc add dev " + inside_intf + " ingress")
            host.cmd("tc filter add dev " + inside_intf + " parent ffff: "
                        "protocol all u32 match u8 0 0 action mirred egress mirror dev " + network_interface)
            host.cmd("sudo tc filter add dev " + inside_intf + " parent ffff: protocol 0x8942 u32 match u8 0 0 action drop")
            host.cmd('iptables -t nat -A POSTROUTING -o ' + network_interface + ' MASQUERADE')

            os.system("ifconfig " + outside_intf + " mtu " + str(65535) + " up")  # for tcpreplay to not crush on too big packets

            self.ipIntfMap[ip] = outside_intf
        else:
            outside_intf = self.ipIntfMap[ip]
        return outside_intf, ip, mac

    def clean(self):
        self.stop()
        info('*** Removing virtual ethernet pairs')
        self.cleanVethPairs()

    def cleanVethPairs(self):
        for intf in self.ipIntfMap.values():
            os.system('ip link del ' + intf + ' type veth')
            # os.system('ip link del ' + intf2 + ' type veth')  # unnecessary - Cannot find device "xxx" (one del removes veth pair)


class ScenarioReplayer(QtCore.QObject):

    def __init__(self, scenario):
        super(ScenarioReplayer, self).__init__()
        self.scenario = scenario
        self._isRunning = False

    def start(self):
        self._isRunning = True
        while self._isRunning:
            for pcap, cache in self.scenario.traffic:
                # popen.terminate and popen.kill do not work correctly, as popen.pid is the pid of the spawned shell and not of the actual process.
                # BUT ONLY IF POPEN(SHELL = TRUE)
                # so full path to tcreplay is required
                tcpreplay_path = shutil.which("tcpreplay")
                comm = ' '.join([tcpreplay_path, '--quiet',
                                 '--intf1=' + self.scenario.intf1,
                                 '--intf2=' + self.scenario.intf2,
                                 '--cachefile=' + cache,
                                 pcap,
                                 '>/dev/null'])
                print(comm)
                process = Popen(args=['sudo', tcpreplay_path, '--quiet',
                                 '--intf1=' + self.scenario.intf1,
                                 '--intf2=' + self.scenario.intf2,
                                 '--cachefile=' + cache,
                                 pcap,
                                 '>/dev/null'])
                process_running = True
                while process_running:
                    time.sleep(1)
                    process_running = process.poll() is None
                    if not self._isRunning:

                        os.kill(process.pid, signal.SIGTERM)
                        # process.terminate()
                        # os.system("kill -9 " + str(process.pid))
                        os.kill(process.pid, signal.SIGTERM)
                        process_running = False
                if not self._isRunning:
                    break

    def stop(self):
        self._isRunning = False