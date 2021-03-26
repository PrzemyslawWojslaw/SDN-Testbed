import os
import importlib.util

from PyQt5 import QtWidgets, QtCore, QtGui
from mininet.topo import Topo

from windows import WizardWindowUi
from tools import topoMaker, messages, predefinedTopos


class WizardWindow(QtWidgets.QWizard):

    switchToManager = QtCore.pyqtSignal(object, object, object)  # (list of networks, mininet logger, name of controller container)

    def __init__(self):
        super(WizardWindow, self).__init__()

        self.topoOptions = {
            "method": None,   # "load", "predefined", "custom"
            "path": "",   # .py path if "load", predefined name if "predefined" - see tools/predefinedTopos.py

            # default custom topology options
            "topoStyle": None,  # type of topology - linear/tree/torus
            "topoSpecific": None,  # parameters for linear/tree/torus shape
            "ipBase": "10.0.0.0/24",
            "NAT": False,  # internet access
            "hostImage": "testbed:basic",
            "portHost": 19999,  # port mapping (default for Netdata)
            "portMachine": 19000,
            "volumeMachine": "default",  # changes later to ~/PROJECT_DIR/traffic/
            "volumeHost": "/root/traffic",
            "linkDelay": 10,  # ms
            "linkBandwidth": 10,  # Mbit/s

            # default controller options
            "controllerType": "local",  # "local" / "floodlight" / "remote"
            "controllerIp": '127.0.0.1',
            "controllerPort": 6653,
            "controllerWebGui": 8080,
            "controllerName": "testbed-floodlight"
        }

        temp_path = os.path.expanduser('~')
        self.topoOptions["volumeMachine"] = temp_path + "/SDN-Testbed/traffic/"

        self.ui = WizardWindowUi.Ui_Wizard()
        self.ui.setupUi(self)
        self.setFixedSize(self.size())

        self.button(QtWidgets.QWizard.FinishButton).clicked.connect(self.startEmulation)

        self.prepareStartPage()
        self.prepareCustomPage()
        self.prepareControllerPage()

        self.loadResultFlag = QtWidgets.QLineEdit()  # workaround for disabling the "Next" button (used in prepareLoadPage)
        self.ui.wizardLoad.registerField("loadResultFlag*", self.loadResultFlag)
        self.methodResultFlag = QtWidgets.QLineEdit()
        self.ui.wizardStart.registerField("methodResultFlag*", self.methodResultFlag)

    def prepareStartPage(self):
        self.ui.loadGroup.setEnabled(False)
        self.ui.predefinedGroup.setEnabled(False)
        self.ui.customGroup.setEnabled(False)

        for name, topoClass in predefinedTopos.topos.items():
            self.ui.predefinedList.addItem(name)

        self.ui.stackedCustom.setCurrentIndex(0)
        self.ui.customCombo.currentIndexChanged.connect(self.changeCustom)
        onlyInt = QtGui.QIntValidator()
        # default linear parameters
        self.ui.linearLine1.setValidator(onlyInt)
        self.ui.linearLine1.setText("4")
        self.ui.linearLine2.setValidator(onlyInt)
        self.ui.linearLine2.setText("1")
        # default tree parameters
        self.ui.treeLine1.setValidator(onlyInt)
        self.ui.treeLine1.setText("2")
        self.ui.treeLine2.setValidator(onlyInt)
        self.ui.treeLine2.setText("2")
        # default torus parameters
        self.ui.torusLine1.setValidator(onlyInt)
        self.ui.torusLine1.setText("3")
        self.ui.torusLine2.setValidator(onlyInt)
        self.ui.torusLine2.setText("3")
        self.ui.torusLine3.setValidator(onlyInt)
        self.ui.torusLine3.setText("1")

        self.ui.loadRadio.clicked.connect(lambda: self.methodClicked("load"))
        self.ui.predefinedRadio.clicked.connect(lambda: self.methodClicked("predefined"))
        self.ui.customRadio.clicked.connect(lambda: self.methodClicked("custom"))

        self.ui.loadLine.textChanged.connect(self.loadPathChanged)
        self.ui.loadButton.clicked.connect(self.loadFile)
        self.ui.predefinedList.itemSelectionChanged.connect(self.changePredefined)

    def loadPathChanged(self):
        self.topoOptions["path"] = self.ui.loadLine.text()

    def loadFile(self):
        path = QtWidgets.QFileDialog.getOpenFileName(self, caption='Select file', directory="./topo", filter='Python Files (*.py)')[0]  # getOpen... returns tuple
        self.ui.loadLine.setText(path)   # emits "self.ui.loadLine.textChanged" !  ->  slot: self.loadPathChanged()

    def methodClicked(self, method):
        self.methodResultFlag.setText("OK")
        if self.topoOptions["method"] == "load":
            self.ui.loadGroup.setEnabled(False)
        elif self.topoOptions["method"] == "predefined":
            self.ui.predefinedGroup.setEnabled(False)
        elif self.topoOptions["method"] == "custom":
            self.ui.customGroup.setEnabled(False)

        self.topoOptions["method"] = method

        if self.topoOptions["method"] == "load":
            self.ui.loadGroup.setEnabled(True)
            self.topoOptions["path"] = self.ui.loadLine.text()
        elif self.topoOptions["method"] == "predefined":
            self.ui.predefinedGroup.setEnabled(True)
            if self.ui.predefinedList.currentRow() < 0:
                self.ui.predefinedList.setCurrentRow(0)
            self.topoOptions["path"] = self.ui.predefinedList.currentItem().text()
        elif self.topoOptions["method"] == "custom":
            self.ui.customGroup.setEnabled(True)

    def changePredefined(self):
        self.topoOptions["path"] = self.ui.predefinedList.currentItem().text()

    def changeCustom(self):
        self.ui.stackedCustom.setCurrentIndex(self.ui.customCombo.currentIndex())

    def prepareLoadPage(self):
        self.ui.loadNumberLabel.setText("Number of topologies: 0")
        self.ui.loadToposLabel.setText("-")
        self.loadResultFlag.clear()
        path = self.topoOptions["path"]
        self.ui.loadPathLabel.setText(path)
        if os.path.isfile(path):
            spec = importlib.util.spec_from_file_location("topo", path)
            topoModule = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(topoModule)
        else:
            self.ui.loadResultLabel.setText("Selected file\nDOES NOT EXIST")
            return

        try:
            self.ui.loadNumberLabel.setText("Number of topologies: " + str(len(topoModule.topos)))
            if len(topoModule.topos) > 0:
                topos_text = ""
                for key, value in topoModule.topos.items():
                    if not issubclass(value, Topo):
                        self.ui.loadResultLabel.setText(
                            "Dicitonary (\"topos\") contains \"" + str(value) + "\" which\nIS NOT A TOPOLOGY")
                        return
                    topos_text += "   \"" + key + "\"  =  " + str(value) + "\n"
                self.ui.loadToposLabel.setText(topos_text)
                self.ui.loadResultLabel.setText(
                    "Topologies found in dicitionary\nare ready to emulate.")
                self.button(QtWidgets.QWizard.NextButton).setEnabled(True)
                self.loadResultFlag.setText(("OK"))
            else:
                self.ui.loadResultLabel.setText(
                    "Dicitonary containing topoologies (\"topos\")\nIS EMPTY")
        except AttributeError:
            self.ui.loadResultLabel.setText("Dicitonary containing topoologies (\"topos\")\nNOT FOUND")
        except TypeError:
            self.ui.loadResultLabel.setText("Dicitonary contains object that \nIS NOT TOPOLOGY CLASS")

    def preparePredefinedPage(self):
        self.ui.predefinedPathLabel.setText(self.topoOptions["path"])
        temp = predefinedTopos.topos[self.topoOptions["path"]]().getTopology()
        self.ui.predefinedTopoLabel.setText(temp)
        temp = predefinedTopos.topos[self.topoOptions["path"]]().getDescription()
        self.ui.predefinedDescriptionLabel.setText(temp)

    def prepareCustomPage(self):
        onlyInt = QtGui.QIntValidator()
        ip_temp = self.topoOptions["ipBase"].split("/")

        self.ui.ipBaseLine.setText(ip_temp[0])
        self.ui.ipMaskLine.setText(ip_temp[1])
        self.ui.natBox.setChecked(self.topoOptions["NAT"])
        self.ui.imageLine.setText(self.topoOptions["hostImage"])
        self.ui.hostPortLine.setValidator(onlyInt)
        self.ui.hostPortLine.setText(str(self.topoOptions["portHost"]))
        self.ui.machinePortLine.setValidator(onlyInt)
        self.ui.machinePortLine.setText(str(self.topoOptions["portMachine"]))
        self.ui.hostPathLine.setText(self.topoOptions["volumeHost"])
        self.ui.machinePathLine.setText(self.topoOptions["volumeMachine"])
        self.ui.delayLine.setValidator(onlyInt)
        self.ui.delayLine.setText(str(self.topoOptions["linkDelay"]))
        self.ui.bandwithLine.setValidator(onlyInt)
        self.ui.bandwithLine.setText(str(self.topoOptions["linkBandwidth"]))

    def prepareControllerPage(self):
        self.ui.floodlightGroup.setEnabled(False)
        self.ui.remoteGroup.setEnabled(False)

        onlyInt = QtGui.QIntValidator()

        self.ui.localRadio.clicked.connect(lambda: self.controllerClicked("local"))
        self.ui.floodlightRadio.clicked.connect(lambda: self.controllerClicked("floodlight"))
        self.ui.remoteRadio.clicked.connect(lambda: self.controllerClicked("remote"))

        self.ui.dockerNameLine.setText(self.topoOptions["controllerName"])
        self.ui.dockerSwitchLine.setValidator(onlyInt)
        self.ui.dockerSwitchLine.setText(str(self.topoOptions["controllerPort"]))
        self.ui.dockerWebLine.setValidator(onlyInt)
        self.ui.dockerWebLine.setText(str(self.topoOptions["controllerWebGui"]))
        self.ui.controllerIpLine.setText(self.topoOptions["controllerIp"])
        self.ui.controllerPortLine.setValidator(onlyInt)
        self.ui.controllerPortLine.setText(str(self.topoOptions["controllerPort"]))

        if self.topoOptions["controllerType"] == "local":
            self.ui.localRadio.click()
        elif self.topoOptions["controllerType"] == "floodlight":
            self.ui.floodlightRadio.click()
        elif self.topoOptions["controllerType"] == "remote":
            self.ui.remoteRadio.click()

    def controllerClicked(self, contrType):
        if self.topoOptions["controllerType"] == "local":
            pass
        elif self.topoOptions["controllerType"] == "floodlight":
            self.ui.floodlightGroup.setEnabled(False)
        elif self.topoOptions["controllerType"] == "remote":
            self.ui.remoteGroup.setEnabled(False)

        self.topoOptions["controllerType"] = contrType

        if self.topoOptions["controllerType"] == "local":
            pass
        elif self.topoOptions["controllerType"] == "floodlight":
            self.ui.floodlightGroup.setEnabled(True)
        elif self.topoOptions["controllerType"] == "remote":
            self.ui.remoteGroup.setEnabled(True)

    def nextId(self):  # order of pages
        if self.currentId() == 0:  # introduction page
            return 1
        elif self.currentId() == 1:  # start page
            if self.topoOptions["method"] == "load":
                self.prepareLoadPage()
                return 2  # load page
            elif self.topoOptions["method"] == "predefined":
                self.preparePredefinedPage()
                return 3  # predefined page
            elif self.topoOptions["method"] == "custom":
                return 4   # custom page
            else:
                return self.currentId()
        elif self.currentId() == 2:  # load page
            if self.topoOptions["controllerType"] == "none":
                return 6  # finish page
            else:
                return 5  # controller page
        elif self.currentId() == 5:  # load or controller page
            return 6  # finish page
        elif self.currentId() == 3 or self.currentId() == 4:  # predefined or custom page
            return 5  # controller page
        else:  # finish page
            return -1

    def startEmulation(self):
        if self.topoOptions["method"] is None:
            messages.message("WARNING", "Topology creation method not chosen.")
            return
        elif self.topoOptions["method"] == "load":
            self.topoOptions["path"] = self.ui.loadLine.text()
        elif self.topoOptions["method"] == "predefined":
            self.topoOptions["path"] = self.ui.predefinedList.currentItem().text()  # in fact not a path, but a name
        elif self.topoOptions["method"] == "custom":
            if self.ui.customCombo.currentIndex() == 0:
                self.topoOptions["topoStyle"] = "linear"
                self.topoOptions["topoSpecific"] = (int(self.ui.linearLine1.text()),
                                                    int(self.ui.linearLine2.text()))
            elif self.ui.customCombo.currentIndex() == 1:
                self.topoOptions["topoStyle"] = "tree"
                self.topoOptions["topoSpecific"] = (int(self.ui.treeLine1.text()),
                                                    int(self.ui.treeLine2.text()))
            elif self.ui.customCombo.currentIndex() == 2:
                self.topoOptions["topoStyle"] = "torus"
                self.topoOptions["topoSpecific"] = (int(self.ui.torusLine1.text()),
                                                    int(self.ui.torusLine2.text()),
                                                    int(self.ui.torusLine3.text()))
            self.topoOptions["ipBase"] = self.ui.ipBaseLine.text() + "/" + self.ui.ipMaskLine.text()
            self.topoOptions["NAT"] = self.ui.natBox.isChecked()
            self.topoOptions["hostImage"] = self.ui.imageLine.text()
            self.topoOptions["portHost"] = int(self.ui.hostPortLine.text())
            self.topoOptions["portMachine"] = int(self.ui.machinePortLine.text())
            self.topoOptions["volumeHost"] = self.ui.hostPathLine.text()
            self.topoOptions["volumeMachine"] = self.ui.machinePathLine.text()
            self.topoOptions["linkDelay"] = int(self.ui.delayLine.text())
            self.topoOptions["linkBandwidth"] = int(self.ui.bandwithLine.text())
        else:
            messages.message("ERROR", "Unknown creation method: " + self.topoOptions["method"])

        if self.topoOptions["controllerType"] == "local":
            pass
        elif self.topoOptions["controllerType"] == "floodlight":
            self.topoOptions["controllerName"] = self.ui.dockerNameLine.text()
            self.topoOptions["controllerPort"] = int(self.ui.dockerSwitchLine.text())
            self.topoOptions["controllerWebGui"] = int(self.ui.dockerWebLine.text())
        elif self.topoOptions["controllerType"] == "remote":
            self.topoOptions["controllerIp"] = int(self.ui.controllerIpLine.text())
            self.topoOptions["controllerPort"] = int(self.ui.controllerPortLine.text())
        else:
            messages.message("ERROR", "Unknown controller option" + self.topoOptions["controllerType"])

        try:
            tmaker = topoMaker.TopoMaker()
            networks, logger = tmaker.createTopology(self.topoOptions)
        except BaseException as e:
            messages.exception(e)
            print("+++ Mininet cleaning after unsuccessful topology creation... +++")
            os.system("sudo docker rm -f " + self.topoOptions["controllerName"] + " >/dev/null")
            os.system("sudo mn -c >/dev/null")
            return

        if not networks:
            messages.error("Topology has NOT been created.")
            return

        self.switchToManager.emit(networks, logger, self.topoOptions["controllerName"])
