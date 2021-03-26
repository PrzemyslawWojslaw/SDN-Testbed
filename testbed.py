#!/usr/bin/python3

import sys

from PyQt5 import QtWidgets

from windows import WizardWindow, ManagerWindow, ReplayWindow


class Testbed:

    def __init__(self):
        self.wizardWindow = None
        self.managerWindow = None
        self.replayWindow = None

    def showWizardWindow(self):
        self.wizardWindow = WizardWindow.WizardWindow()
        self.wizardWindow.switchToManager.connect(self.showManagerWindow)  # signal passes list of networks, mininet logger and name of controller container (Floodlight)
        self.wizardWindow.show()

    def showManagerWindow(self, networks, logger, controllerName):
        self.managerWindow = ManagerWindow.ManagerWindow(networks, logger, controllerName)
        self.replayWindow = ReplayWindow.ReplayWindow(networks)

        self.managerWindow.prepareReplaySignal.connect(self.showReplayWindow)
        self.managerWindow.exitTestbedSignal.connect(self.replayWindow.exit)

        self.replayWindow.clustersSignal.connect(self.managerWindow.updateReplayData)

        self.wizardWindow.close()
        self.managerWindow.show()

    def showReplayWindow(self):
        self.replayWindow.show()


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    testbed = Testbed()
    testbed.showWizardWindow()
    sys.exit(app.exec())
