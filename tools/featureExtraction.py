import shutil

from scapy.all import *
from scapy.layers.http import *

from tools import messages

class FeatureExtractor():

    def __init__(self):
        self.pcapsFeatures = {}  # dictionary { "pcap_path" : dict{pcap_features} } - features listed in self.extract()
        self.directoryList = []  # list of created directories with split pcaps (for cleaning later)

    def getAll(self):
        return self.pcapsFeatures

    def getAllPaths(self):
        return list(self.pcapsFeatures.keys())

    def getDirectories(self):
        return self.directoryList

    def get(self, pcap_path):
        if pcap_path in self.pcapsFeatures:
            return self.pcapsFeatures[pcap_path]
        else:
            return None

    def deepExtract(self, pcap_path, split=True, flows = False, file_limit = 0, packet_limit = 0):
        #dir = self.splitWithScapy(pcap_path, flows, file_limit)
        dir = pcap_path.split(".")[0] + "_processed"

        if dir in self.directoryList:
            raise ValueError("PCAP file\n   " + pcap_path + "\nalready has a \"processed\" directory.\n"
                                                            "Remove it before retrying feature extraction.")

        self.directoryList.append(dir)
        try:
            os.mkdir(dir)
        except OSError:
            raise

        if flows:
            method = "\"connection\""
        else:
            method = "\"ip-src-dst\""

        if file_limit != 0:
            method += " -p " + str(file_limit)

        if split:
            os.system("tools/PcapSplitter -f " + pcap_path + " -o " + dir + " -m " + method)
        else:
            file_name = pcap_path.split("/")[-1]
            shutil.copy(pcap_path, dir + "/" + file_name)

        for filename in os.listdir(dir):
            if filename.endswith(".pcap"):
                p_path = os.path.join(dir, filename)
                self.extract(p_path, packet_limit)

    def extract(self, pcap_path, packet_limit = 0):
        if pcap_path in self.pcapsFeatures:
            return self.pcapsFeatures[pcap_path]

        features = {
            # number of packets in pcap
            "packet_count" : 0,
            # TCP flags
            "FIN" : 0,
            "SYN" : 0,
            "RST" : 0,
            "PSH" : 0,
            "ACK" : 0,
            "URG" : 0,
            "ECE" : 0,
            "CWR" : 0,
            "NS" : 0,
            # protocols
            "TCP" : 0,
            "UDP": 0,
            "ICMP": 0,
            "DNS" : 0,
            "HTTP": 0,
            # TCP / UDP ports
            "port_21" : 0,     #  FTP
            "port_22" : 0,     #  SSH
            "port_23" : 0,     #  Telnet
            "port_25" : 0,     #  SMTP
            "port_53" : 0,     #  DNS
            "port_80" : 0,     #  HTTP
            "port_110" : 0,    #  POP3
            "port_111" : 0,    #  ONC RPC
            "port_135" : 0,    #  Microsoft EPMAP (RPC)
            "port_139" : 0,    #  NetBIOS Session Service
            "port_143" : 0,    #  IMAP
            "port_443" : 0,    #  HTTPS
            "port_445" : 0,    #  Microsoft-DS
            "port_993" : 0,    #  IMAPS
            "port_995" : 0,    #  POP3S
            "port_1723" : 0,   #  PPTP
            "port_3306" : 0,   #  MySQL
            "port_3389" : 0,   #  Microsoft Windows Based Terminal (WBT)
            "port_5900" : 0,   #  VNC
            "port_8080" : 0,   #  HTTP (proxy)
            # general parameters (average)
            "Avg_delta_time" : 0.0,
            "Avg_packet_length": 0.0,
            "Avg_TCP_payload_length": 0.0
        }

        self.__extractWithScapy(features, pcap_path, packet_limit)

        self.pcapsFeatures[pcap_path] = features
        return features

    def __extractWithScapy(self, features, pcap_path, packet_limit = 0):
        pkts = PcapReader(pcap_path)

        # dictionary - faster than list and creating name each time
        port_map = {
            21 : "port_21",
            22 : "port_22",
            23 : "port_23",
            25 : "port_25",
            53 : "port_53",
            80 : "port_80",
            110 : "port_110",
            111 : "port_111",
            135 : "port_135",
            139 : "port_139",
            143 : "port_143",
            443 : "port_443",
            445 : "port_445",
            993 : "port_993",
            995 : "port_995",
            1723 : "port_1723",
            3306 : "port_3306",
            3389 : "port_3389",
            5900 : "port_5900",
            8080 : "port_8080"
        }
        for n, p in port_map.items():
            port_name = "port_" + str(n)
            if port_name != p or p not in features:
                raise KeyError("Port map contains wrong item (\"" + str(n) + "\").")

        previous_time = 0

        for pkt in pkts:
            features["packet_count"] += 1

            port_source = None
            port_destination = None

            #    TCP flags
            #  0000 0000 0001   FIN = 0x001
            #  0000 0000 0010   SYN = 0x002
            #  0000 0000 0100   RST = 0x004
            #  0000 0000 1000   PSH = 0x008
            #  0000 0001 0000   ACK = 0x010
            #  0000 0010 0000   URG = 0x020
            #  0000 0100 0000   ECE = 0x040
            #  0000 1000 0000   CWR = 0x080
            #  0001 0000 0000   NS  = 0x100

            if pkt.haslayer("TCP"):
                features["TCP"] += 1
                features["Avg_TCP_payload_length"] += len(pkt["TCP"].payload)

                port_source = pkt[TCP].sport
                port_destination = pkt[TCP].dport

                flags = pkt["TCP"].flags
                if flags & 0x001:
                    features["FIN"] += 1
                if flags & 0x002:
                    features["SYN"] += 1
                if flags & 0x004:
                    features["RST"] += 1
                if flags & 0x008:
                    features["PSH"] += 1
                if flags & 0x010:
                    features["ACK"] += 1
                if flags & 0x020:
                    features["URG"] += 1
                if flags & 0x040:
                    features["ECE"] += 1
                if flags & 0x080:
                    features["CWR"] += 1
                if flags & 0x100:
                    features["NS"] += 1

            if pkt.haslayer("UDP"):
                features["UDP"] += 1

                port_source = pkt["UDP"].sport
                port_destination = pkt["UDP"].dport

            if port_source is not None:
                if port_source in port_map:
                    features[port_map[port_source]] += 1
                if port_destination in port_map:
                    features[port_map[port_destination]] += 1

            if pkt.haslayer("ICMP"):
                features["ICMP"] += 1

            if pkt.haslayer("DNS"):
                features["DNS"] += 1

            if pkt.haslayer("HTTP"):
                features["HTTP"] += 1

            if previous_time == 0:
                previous_time = pkt.time
            current_time = pkt.time
            features["Avg_delta_time"] += current_time - previous_time
            previous_time = current_time

            features["Avg_packet_length"] += len(pkt)

            if 0 < packet_limit == features["packet_count"]:
                break

        if (features["packet_count"] - 1) != 0:
            features["Avg_delta_time"] = float(features["Avg_delta_time"] / (features["packet_count"] - 1))
        if features["packet_count"] != 0:
            features["Avg_packet_length"] = features["Avg_packet_length"] / features["packet_count"]
        if features["TCP"] != 0:
            features["Avg_TCP_payload_length"] = features["Avg_TCP_payload_length"] / features["TCP"]


    def __splitWithScapy(self, pcap_path, flows = False, file_limit = 100):
        files_map = {}   #  { tuple(src_IP, src_port, dst_IP, dst_port) : pcap_path}   -> if flows=False then only IP

        name = pcap_path.split(".")[0]  # remove pcap extension
        dir_name = name + "_processed"
        if not os.path.exists(dir_name):
            os.mkdir(dir_name)
        else:
            raise ValueError("PCAP file\n   " + pcap_path + "\nalready has a \"processed\" directory.\n"
                             "Remove it before retrying feature extraction.")

        files_map["other"] = dir_name + "/other.pcap"   # packets without IP (or TCP/UDP for flows) layer

        pkts = PcapReader(pcap_path)
        number_of_splits = 0
        for pkt in pkts:
            if flows:
                if pkt.haslayer("TCP"):
                    protocol = "TCP"
                    variant_a = (pkt["IP"].src, pkt[protocol].sport, pkt["IP"].dst, pkt[protocol].dport)
                    variant_b = (pkt["IP"].dst, pkt[protocol].dport, pkt["IP"].src, pkt[protocol].sport)
                    if variant_a in files_map:
                        wrpcap(files_map[variant_a], pkt, append=True)
                    elif variant_b in files_map:
                        wrpcap(files_map[variant_b], pkt, append=True)
                    else:
                        number_of_splits += 1
                        if file_limit != 0:
                            name_number = number_of_splits % file_limit   # append to existing pcap
                        else:
                            name_number = number_of_splits
                        files_map[variant_a] = dir_name + "/" + str(name_number) + ".pcap"
                        wrpcap(files_map[variant_a], pkt, append=True)
                elif pkt.haslayer("UDP"):
                    protocol = "UDP"
                    variant_a = (pkt["IP"].src, pkt[protocol].sport, pkt["IP"].dst, pkt[protocol].dport)
                    variant_b = (pkt["IP"].dst, pkt[protocol].dport, pkt["IP"].src, pkt[protocol].sport)
                    if variant_a in files_map:
                        wrpcap(files_map[variant_a], pkt, append=True)
                    elif variant_b in files_map:
                        wrpcap(files_map[variant_b], pkt, append=True)
                    else:
                        number_of_splits += 1
                        if file_limit != 0:
                            name_number = number_of_splits % file_limit
                        else:
                            name_number = number_of_splits
                        files_map[variant_a] = dir_name + "/" + str(name_number) + ".pcap"
                        wrpcap(files_map[variant_a], pkt, append=True)
                else:
                    wrpcap(files_map["other"], pkt, append=True)
            else:
                if pkt.haslayer("IP"):
                    variant_a = (pkt["IP"].src, pkt["IP"].dst)
                    variant_b = (pkt["IP"].dst, pkt["IP"].src)
                    if variant_a in files_map:
                        wrpcap(files_map[variant_a], pkt, append=True)
                    elif variant_b in files_map:
                        wrpcap(files_map[variant_b], pkt, append=True)
                    else:
                        number_of_splits += 1
                        if file_limit != 0:
                            name_number = number_of_splits % file_limit
                        else:
                            name_number = number_of_splits
                        files_map[variant_a] = dir_name + "/" + str(name_number) + ".pcap"
                        wrpcap(files_map[variant_a], pkt, append=True)
                else:
                    wrpcap(files_map["other"], pkt, append=True)

        return dir_name

    def clear(self):
        self.splitClean()
        self.pcapsFeatures.clear()
        self.directoryList.clear()

    def splitClean(self):
        for dir in self.directoryList:
            try:
                shutil.rmtree(dir)
            except OSError as e:
                messages.exception(e)
