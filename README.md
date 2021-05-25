# SDN-Testbed
*Testbed for SDN networks with distributed network traffic replaying.*

*Created for Master's Thesis on Warsaw University of Technology.*

## About
Modern networks and the complexity of their processes are growing in size. Managing them effectively is becoming more and more difficult. To solve this issue, the **Software-Defined Networking** architecture was introduced. The control plane is separated from the transport layer by introducing a controller that dynamically adjusts the network behavior to the situation. The rules it follows depend solely on its software (hence the term software-defined).

The SDN controller has a unique view of the entire network. It is able to perceive communication moving along independent paths between multiple points. This causes a problem with recreation of the actual traffic when running tests and experiments, as the existing traffic replay engines were not designed to send traffic between multiple nodes. Presented testbed is a new environment for research on SDN networks based on the [Containernet](https://github.com/containernet/containernet) emulator, taking into account multi-point traffic replaying. To make it easier for the user to use PCAP files from various sources, clustering algorithms are used.

Details (only in Polish) can be found in thesis file *"Przemysław Wojsław - Praca magisterska.pdf"*.

## Instalation

Requires **Ubuntu Linux 18.04 LTS**.

```bash
$ git clone https://github.com/PrzemyslawWojslaw/SDN-Testbed.git
$ cd SDN-Testbed
$ sudo ./install_prerequisites.sh
```
It may take a few minutes.

## Usage

Command:
```bash
$ sudo python3 testbed.py
```
starts topology wizard, where network parameters are defined. Finishing in this window will automatically start new one, used for managing the emulation.

The "Load" option requires from file to hava a structure similar to *"topo/topo_exapmle.py"*. it's the same as required by Mininet/Containernet when invoked from terminal (*"sudo mn --custom ./topo/topo_example.py --topo=mytopo"*).

It is possible to create custom predefined scenarios. To do that, edit *"tools/predefinedTopos.py"* and add new class like example ones (remeber to append your class to *"topos"* dictionary at the end of the file).

## Issues

- Inaccurate synchronization caused by the multithreaded nature of the environment often causes the recipient to send back the packet with the RST flag.
- Large packets present in the original file may not be sent by the host if the interface has an MTU value lower than the packet size (default 1500).
- Very high communication rates may not be represented correctly. 
- Embedded terminals in GUI do not display properly (xterm issue), though still are usable.

**Work on the project has been suspended at this point, but may be resumed in the future.**
