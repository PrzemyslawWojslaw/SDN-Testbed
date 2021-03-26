#!/bin/bash

if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    print_help
    exit 0
fi

if [ "$1" == "--list" ] || [ "$1" == "-l" ]; then
    print_list
    exit 0
fi

# Default variables
verbose=true

# Set user variables
while [ $# != 0 ]
do
    case "$1" in
        -s|--silent) verbose=false; shift ;;
        *) echo "Chosen option doesn't exist!"; print_help; exit 1 ;;
    esac
done

function print_help()
{
    cat <<-END
    Usage: start-hosts.sh [OPTION]
    Install requirements: Docker and Containernet.
    Build default Docker image for hosts in emulation.
    ------
       -h | --help
         Display this help
       -l | --list
         Display list of tools to install
       -s | --silent
         Do not display installation logs (not recommended)
END
}

function print_list()
{
    cat <<-END
    List of tools installed by this script:
       - Python3
       - PyQt5 (for Python3)
       - Containernet
       - tcpreplay
       - Scapy (for Python3)
       - scikit-learn (for Python3)
       - net-tools
       - tmux
       - screen
       - kneed (for Python3)
END
}

function do_install()
{
    echo "+++ Installing Python3... +++"
    sudo apt-get -y install python3.6

    echo "+++ Installing PyQt5... +++"
    sudo apt-get -y install python3-pyqt5

    echo "+++ Installing Containernet... +++"
    if command -v mn >/dev/null 2>&1; then
        echo "+++ Containernet (or Mininet) already installed +++"
    else
        sudo apt-get -y install python3-setuptools ansible aptitude
        git clone https://github.com/containernet/containernet.git ~/containernet
        sudo ansible-playbook -i "localhost," -c local ~/containernet/ansible/install.yml
        # sudo python3 ~/containernet/setup.py install
    fi

    echo "+++ Preparing custom docker images... +++"
    sudo docker pull glefevre/floodlight
    sudo docker build -t testbed:basic -f dockerfiles/Dockerfile.basic dockerfiles/

    echo "+++ Installing Scapy... +++"
    sudo pip3 install scapy

    echo "+++ Installing Tcpreplay... +++"
    sudo apt-get -y install tcpreplay

    echo "+++ Installing scikit-learn... +++"
    sudo pip3 install -U scikit-learn

    echo "+++ Installing additional tools... +++"
    sudo apt-get -y install net-tools tmux screen
    sudo pip3 install kneed
}

echo "+++ Installation started - it may take a while... +++"
if "$verbose" ; then
    do_install
else
    do_install >/dev/null
fi
echo "+++ Installation finished +++"

