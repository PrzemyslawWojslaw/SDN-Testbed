import os
import re

from PyQt5 import QtWidgets, QtCore, QtGui
from mininet.node import Docker
from mininet.term import makeTerms
from mininet.log import output
from subprocess import Popen, PIPE

from tools import replay
from windows import ManagerWindowUi


class ManagerWindow(QtWidgets.QMainWindow):

    prepareReplaySignal = QtCore.pyqtSignal(object)
    exitTestbedSignal = QtCore.pyqtSignal()

    def __init__(self, networks, logger, controllerName):
        super(ManagerWindow, self).__init__()

        self.controllerName = controllerName
        self.network = networks[0]
        if len(networks) >= 2:
            self.networkAdv = networks[1]
        else:
            self.networkAdv = None

        self.networkStopped = False

        self.replayData = None
        self.replayEngine = replay.ReplayEngine(self.network)

        self.terminalPalette = self.__prepareTerminalPalette()

        self.ui = ManagerWindowUi.Ui_mainWindow()
        self.ui.setupUi(self)
        self.ui.stackedWidget.setCurrentIndex(0)

        self.stopButton = None
        self.mininetLogger = None
        self.__prepareMininetLogger(logger)
        self.__prepareTerminals(self.network, self.ui.hostPage)

        if self.networkAdv:
            self.__prepareTerminals(self.networkAdv, self.ui.advPage)
            self.ui.actionAdversary.triggered.connect(lambda: self.ui.stackedWidget.setCurrentWidget(self.ui.advPage))
        else:
            self.ui.actionAdversary.deleteLater()

        self.ui.actionMininet.triggered.connect(lambda: self.ui.stackedWidget.setCurrentWidget(self.ui.mininetPage))
        self.ui.actionHosts.triggered.connect(lambda: self.ui.stackedWidget.setCurrentWidget(self.ui.hostPage))

        # mininet commands
        self.ui.actionPingAll.triggered.connect(lambda: self.network.pingAll())
        self.ui.actionInfoDump.triggered.connect(self.__infoDump)
        self.ui.actionStartXterms.triggered.connect(lambda: self.startXterms())
        # host commands
        self.ui.actionCtrl_C.triggered.connect(lambda: self.cmdStandard("C-c"))
        self.ui.actionListFiles.triggered.connect(lambda: self.cmdStandard("ls"))
        self.ui.actionIfconifg.triggered.connect(lambda: self.cmdStandard("ifconfig"))
        self.ui.actionTshark.triggered.connect(self.cmdTshark)

        self.ui.actionPrepare.triggered.connect(self.prepareReplay)
        self.ui.actionStart.triggered.connect(self.startReplay)
        self.ui.actionStop.triggered.connect(self.stopReplay)
        self.ui.actionStart.setEnabled(False)
        self.ui.actionStop.setEnabled(False)

    def __prepareTerminals(self, net, page, columns=2):
        scrollAreaContents = QtWidgets.QWidget()

        layoutScroll = QtWidgets.QGridLayout(scrollAreaContents)

        row = 0
        column = 0
        for node in self.network.hosts:
            terminal = EmbeddedTerminal(net, node)
            layoutScroll.addWidget(terminal, row, column)
            column += 1
            if column >= columns:
                column = 0
                row += 1
        scrollAreaContents.setMinimumSize(columns * 400, row * 300)

        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidgetResizable(True)

        scrollArea.setWidget(scrollAreaContents)

        layout = QtWidgets.QGridLayout()
        layout.addWidget(scrollArea)
        page.setLayout(layout)

    def __prepareMininetLogger(self, logger):
        layout = QtWidgets.QVBoxLayout()

        self.mininetLogger = logger
        self.mininetLogger.widget.setPalette(self.terminalPalette)
        layout.addWidget(self.mininetLogger.widget)

        self.stopButton = QtWidgets.QPushButton("STOP NETWORK")
        self.stopButton.clicked.connect(self.stopNetworks)
        layout.addWidget(self.stopButton)

        self.ui.mininetPage.setLayout(layout)

    def __prepareTerminalPalette(self):
        lettersColor = (255, 255, 255)
        disabledLettersColor = (190, 190, 190)
        backgroundColor = (0, 44, 65)
        disabledBackgroundColor = (239, 235, 231)

        palette = QtGui.QPalette()
        brush = QtGui.QBrush(QtGui.QColor(*lettersColor))  # operator * expands a tuple
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Text, brush)
        brush = QtGui.QBrush(QtGui.QColor(*backgroundColor))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Base, brush)
        brush = QtGui.QBrush(QtGui.QColor(*lettersColor))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Text, brush)
        brush = QtGui.QBrush(QtGui.QColor(*backgroundColor))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Base, brush)
        brush = QtGui.QBrush(QtGui.QColor(*disabledLettersColor))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Text, brush)
        brush = QtGui.QBrush(QtGui.QColor(*disabledBackgroundColor))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Base, brush)
        return palette

    def infoDump(self):
        output("*** INFO DUMP\n")

        output("--- Controllers ---\n")
        for controller in self.network.controllers:
            output("   *  Controller " + controller.name + " | IP: " + controller.ip +
                   " | Port: " + str(controller.port) + "\n")

        output("--- Switches ---\n")
        for switch in self.network.switches:
            dpid = ":".join(re.findall("....", switch.dpid))
            output("   *  Switch " + switch.name + " | DPID: " + dpid + "\n")

        output("--- Hosts ---\n")
        for host in self.network.hosts:
            if isinstance(host, Docker):
                image = " | Image: \"" + host.dimage + "\""
            else:
                image = " | Not a Docker container"
            output("   *  Host " + host.name + " | IP: " + host.IP() + " | MAC: " + host.MAC() + image + "\n")

        output("--- Links ---\n")
        for link in self.network.links:
            output("   *  " + link.intf1.node.name + ":" + link.intf1.name +
                   " <-> " + link.intf2.node.name + ":" + link.intf2.name +
                   " | Status: " + link.status() + "\n")

    def startXterms(self):
        self.network.terms += makeTerms( self.network.hosts, 'host' )

    def cmdStandard(self, cmd):
        hosts = getattr(self.network, "hosts")
        for node in hosts:
            if isinstance(node, Docker):
                Popen(['docker', 'exec', '-it', node.dnameprefix + '.' + node.name,
                       'tmux', 'send-keys', '-t', "mn_" + node.name + ':0',
                       cmd, 'ENTER'],
                      stdout=PIPE, stderr=PIPE)
            else:
                Popen(['tmux', 'send-keys', '-t', "mn_" + node.name + ':0',
                       cmd, 'ENTER'],
                      stdout=PIPE, stderr=PIPE)

    def cmdTshark(self):
        hosts = getattr(self.network, "hosts")
        for node in hosts:
            if isinstance(node, Docker):
                Popen(['docker', 'exec', '-it', node.dnameprefix + '.' + node.name, 'tmux', 'send-keys', '-t', "mn_" + node.name + ':0',
                       'tshark -P -i ' + str(node.defaultIntf()), 'ENTER'],
                      stdout=PIPE, stderr=PIPE)
            else:
                Popen(['tmux', 'send-keys', '-t', "mn_" + node.name + ':0',
                       'tshark -P -i ' + str(node.defaultIntf()), 'ENTER'],
                      stdout=PIPE, stderr=PIPE)

    def updateReplayData(self, replayData):
        self.setEnabled(False)
        self.repaint()
        self.replayData = replayData
        for scenario in replayData:
            self.replayEngine.prepare(scenario.pcapPath, scenario.hostPair[0], scenario.hostPair[1])
        self.setEnabled(True)
        self.ui.actionStart.setEnabled(True)

    def prepareReplay(self):
        self.prepareReplaySignal.emit(self.network)

    def startReplay(self):
        self.setEnabled(False)
        self.replayEngine.start()
        self.setEnabled(True)
        self.ui.actionStart.setEnabled(False)
        self.ui.actionStop.setEnabled(True)

    def stopReplay(self):
        self.setEnabled(False)
        self.replayEngine.stop()
        self.setEnabled(True)
        self.ui.actionStart.setEnabled(True)
        self.ui.actionStop.setEnabled(False)

    def stopNetworks(self):
        self.stopButton.setEnabled(False)
        if not self.networkStopped:
            self.networkStopped = True
            self.network.stop()
            if self.networkAdv:
                self.networkAdv.stop()

    def closeEvent(self, event):
        """Generate 'question' dialog on clicking 'X' button in title bar.
        Reimplement the closeEvent() event handler to include a 'Question'
        dialog with options on how to proceed
        """
        self.setEnabled(False)

        reply = QtWidgets.QMessageBox.question(
            self, "Message",
            "Are you sure you want to quit the emulation?\nAll data on hosts will be lost.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.Yes:
            self.replayEngine.clean()
            os.system("sudo docker rm -f " + self.controllerName + " >/dev/null")
            self.stopNetworks()
            self.exitTestbedSignal.emit()
            event.accept()
        else:
            self.setEnabled(True)
            event.ignore()

class EmbeddedTerminal(QtWidgets.QWidget):

    def __init__(self, network, node):
        super().__init__()
        self.node = node
        self.network = network
        layout = QtWidgets.QVBoxLayout(self)
        self.button = QtWidgets.QPushButton(self.node.name)
        self.button.clicked.connect(self.showTerminal)
        layout.addWidget(self.button)
        self.terminal = QtWidgets.QTextBrowser()
        self.terminal.setFrameStyle(QtWidgets.QTextEdit.DrawWindowBackground)  # to show where xterm should be (if is not)
        layout.addWidget(self.terminal)

        self.network.terms += self.makeMyTerms()

        self.setLayout(layout)
        self.setMinimumSize(200, 50)

    def showTerminal(self):
        self.network.terms += makeTerms([self.node], self.node.name)

    def makeMyTerms(self):
        terms = []
        terms += self.makeMyTerm()
        return terms

    def makeMyTerm(self, title='Node', term='xterm', display=None):
        # from mininet.term modified for embedding of terminal (xterm)
        from mininet.log import error
        from mininet.term import tunnelX11

        cmd = 'tmux new -s mn_' + self.node.name
        title = '"%s: %s"' % (title, self.node.name)
        if not self.node.inNamespace:
            title += ' (root)'
        cmds = {
            'xterm': ['xterm', '-title', title, '-into', str(int(self.terminal.winId())), '-display'],
            'gterm': ['gnome-terminal', '--title', title, '--display'],  # no way found to embed
            'urxvt': ['urxvt', '-name', title, '-embed', str(int(self.terminal.winId())), '-fg White -bg Black', '-display']  # not working even for Dockers
        }
        if term not in cmds:
            error('invalid terminal type: %s' % term)
            return
        # Docker Hosts don't have DISPLAY. So instead of
        # X11 tunnel, we use terminals from outside Docker
        from mininet.node import Docker
        if isinstance(self.node, Docker):
            if not self.node._is_container_running():
                return []
            if display is None:
                cmds[term] = cmds[term][:-1]
            else:
                cmds[term].append(display)
            cmds[term].append('-e')

            command = ' '.join(cmds[term] +
                        ['env TERM=ansi docker exec -it %s.%s %s' % (
                            self.node.dnameprefix, self.node.name, cmd)])
            print(command)
            term = Popen(cmds[term] +
                        ['env TERM=ansi docker exec -it %s.%s %s' % (
                            self.node.dnameprefix, self.node.name, cmd)],
                         stdout=PIPE, stdin=PIPE, stderr=PIPE)
            if term:
                return [term]
            return []
        display, tunnel = tunnelX11(self.node, display)
        if display is None:
            return []

        cmds[term] = cmds[term][:-1]
        term = Popen(cmds[term] + ['-e', 'env TERM=ansi %s' % cmd],
                     stdout=PIPE, stdin=PIPE, stderr=PIPE)

        return [tunnel, term] if tunnel else [term]
