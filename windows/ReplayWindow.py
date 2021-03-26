import os
import copy
import shutil
import time

from PyQt5 import QtWidgets, QtCore

from windows import ReplayWindowUi
from tools import messages, featureExtraction, clustering


class ReplayWindow(QtWidgets.QDialog):
    clustersSignal = QtCore.pyqtSignal(object)  # results of ONE algorithm, see clustering.ClusteringResult class

    def __init__(self, networks):
        super(ReplayWindow, self).__init__()

        self.networks = networks
        self.path = ""
        self.hostNames = []
        self.modes = []
        self.clusteringResults = []
        self.directories = []

        self.clusteringThread = None

        self.ui = ReplayWindowUi.Ui_TrafficDialog()
        self.ui.setupUi(self)
        self.setFixedSize(self.size())
        self.ui.stackedWidget.setCurrentWidget(self.ui.preparePage)

        for network in networks:
            for host in network.hosts:
                self.hostNames.append(host.name)
                self.ui.comboHost1.addItem(host.name)

        self.ui.loadButton.clicked.connect(self.loadFile)

        self.ui.prepareButtonBox.button(QtWidgets.QDialogButtonBox.Ok).clicked.connect(self.startClusteringThread)
        self.ui.prepareButtonBox.button(QtWidgets.QDialogButtonBox.Cancel).clicked.connect(self.hide)

        self.ui.clusteringButtonBox.button(QtWidgets.QDialogButtonBox.Ok).clicked.connect(self.showResults)
        self.ui.comboClustering.currentIndexChanged.connect(self.changeResultsTable)

        self.ui.resultsButtonBox.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(self.apply)
        self.ui.resultsButtonBox.button(QtWidgets.QDialogButtonBox.Retry).clicked.connect(self.retry)

        self.ui.comboHost1.currentIndexChanged.connect(self.prepareHost2)
        self.prepareHost2()
        self.ui.addPairButton.clicked.connect(self.addPair)
        self.ui.removePairButton.clicked.connect(self.removePair)

    def loadFile(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, caption='Select directory', directory="./traffic")
        self.ui.loadLine.setText(path)

    def prepareHost2(self):
        self.ui.comboHost2.clear()
        host1 = self.ui.comboHost1.currentText()

        for name in self.hostNames:
            if name != host1:
                self.ui.comboHost2.addItem(name)

    def addPair(self):
        host1 = self.ui.comboHost1.currentText()
        host2 = self.ui.comboHost2.currentText()

        text = host1 + " <-> " + host2
        text2 =  host2 + " <-> " + host1
        found = False
        for i in range(self.ui.pairList.count()):
            t = self.ui.pairList.item(i).text()
            if (text == t) or (text2 == t):
                found = True

        if not found:
            self.ui.pairList.addItem(text)

    def removePair(self):
        self.ui.pairList.takeItem(self.ui.pairList.currentRow())

    def startClusteringThread(self):
        self.clusteringThread = ClusteringThread(self.ui)
        self.clusteringThread.resultsSignal.connect(self.receiveResults)
        self.clusteringThread.directoriesSignal.connect(self.receiveDirectories)
        self.clusteringThread.resultsSignal.connect(self.ui.stackedWidget.repaint)
        self.clusteringThread.errorSignal.connect(self.retry)
        self.clusteringThread.start()

    def receiveResults(self, modes, clusteringResults):
        self.modes = modes
        self.clusteringResults = clusteringResults

    def receiveDirectories(self, directories):
        self.directories = directories

    def showResults(self):
        for i in range(len(self.modes)):
            self.ui.comboClustering.addItem(self.modes[i])

            table = QtWidgets.QTableWidget()
            table.setColumnCount(4)
            header_labels = ['Cluster ID', 'Cluster ID\nbefore normalization', 'Host pair', '\".pcap\" file']
            table.setHorizontalHeaderLabels(header_labels)
            header = table.horizontalHeader()
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)

            for result in self.clusteringResults[i]:
                self.addRowToTable(table, result)

            table.setSortingEnabled(True)
            table.sortItems(0, QtCore.Qt.AscendingOrder)
            self.ui.stackedTables.addWidget(table)

        self.ui.stackedWidget.setCurrentWidget(self.ui.resultsPage)
        self.ui.stackedWidget.repaint()

    def addRowToTable(self, table, result):
        rowPosition = table.rowCount()
        table.insertRow(rowPosition)
        table.setItem(rowPosition, 0, QtWidgets.QTableWidgetItem(str(result.cluster)))
        table.setItem(rowPosition, 1, QtWidgets.QTableWidgetItem(str(result.clusterBeforeNormalization)))
        table.setItem(rowPosition, 2, QtWidgets.QTableWidgetItem(str(result.hostPair)))
        table.setItem(rowPosition, 3, QtWidgets.QTableWidgetItem(str(result.pcapPath)))

    def changeResultsTable(self):
        index = self.ui.comboClustering.currentIndex()
        self.ui.stackedTables.setCurrentIndex(index)

    def apply(self):
        self.setEnabled(False)
        self.repaint()
        index = self.ui.comboClustering.currentIndex()
        self.clustersSignal.emit(self.clusteringResults[index])
        self.hide()
        self.setEnabled(True)

    def retry(self):
        self.ui.stackedWidget.setCurrentWidget(self.ui.preparePage)
        self.ui.featureTimeLabel.setText("Time: -")
        self.ui.clusteringTimeLabel.setText("-")
        self.ui.comboClustering.clear()
        self.cleanDirectories()
        for i in reversed(range(self.ui.stackedTables.count())):
            self.ui.stackedTables.widget(i).deleteLater()

    def cleanDirectories(self):
        for dir in self.directories:
            try:
                shutil.rmtree(dir)
            except OSError as e:
                messages.exception(e)
        self.directories.clear()

    def exit(self):
        self.setEnabled(False)
        self.cleanDirectories()
        self.close()

class ClusteringThread(QtCore.QThread):
    resultsSignal = QtCore.pyqtSignal(object, object)  # modes, clusteringResults
    directoriesSignal = QtCore.pyqtSignal(object)  # list of directories
    repaintSignal = QtCore.pyqtSignal()
    errorSignal = QtCore.pyqtSignal()

    def __init__(self, ui):
        super(ClusteringThread, self).__init__()
        self.ui = ui
        self.featureExtractor = featureExtraction.FeatureExtractor()
        self.clusteringEngine = clustering.ClusteringEngine()

        self.modes = []
        self.clusteringResults = []

    def run(self):
        path = self.ui.loadLine.text()
        if os.path.isdir(path):
            self.ui.pathLabel.setText(path)
        else:
            messages.error("Selected directory\n   " + path + "\ndoes not exist.")
            return

        file_number = 0
        for filename in os.listdir(path):
            if filename.endswith(".pcap"):
                file_number += 1
        if not file_number:  # file_number == 0
            messages.error("Selected directory\n   " + path + "\ndoes not contain any \".pcap\" files.")
            self.errorSignal.emit()
            return
        else:
            self.ui.loadFilesLabel.setText("Number of files found: " + str(file_number))

        hostPairs = {}
        if not self.ui.pairList.count():
            messages.error("No host pair selected.")
            return
        for i in range(self.ui.pairList.count()):
            host_text = self.ui.pairList.item(i).text()
            host1 = host_text.split(" <-> ")[0]
            host2 = host_text.split(" <-> ")[1]
            hostPairs[len(hostPairs)] = (host1, host2)
        self.clusteringEngine.updateHostPairs(hostPairs)

        split = False  # split pcap files...
        flows = False  # ... into flows (False - into host pairs)
        if self.ui.splitNotButton.isChecked():
            split = False
        elif self.ui.splitPairsButton.isChecked():
            split = True
            flows = False
        elif self.ui.splitFlowsButton.isChecked():
            split = True
            flows = True

        self.modes.clear()
        if self.ui.clusterKmeansButton.isChecked():
            self.modes.append("K-means")
        if self.ui.clusterSpectralButton.isChecked():
            self.modes.append("Spectral clustering")
        if self.ui.clusterDBSCANButton.isChecked():
            self.modes.append("DBSCAN")
        if self.ui.clusterOPTICSButton.isChecked():
            self.modes.append("OPTICS")
        if self.ui.clusterAffinityButton.isChecked():
            self.modes.append("Affinity propagation")
        if self.ui.clusterBirchButton.isChecked():
            self.modes.append("Birch")

        if not self.modes:
            messages.error("No clustering algorithm selected.")
            return

        self.ui.clusteringButtonBox.setEnabled(False)

        if split:
            split_text = "Split files: yes, due to "
            if flows:
                split_text += " IP and ports"
            else:
                split_text += " IP"
        else:
            split_text = "Split files: no"
        self.ui.splitLabel.setText(split_text)

        self.ui.statusLabel.setText("FEATURE EXTRACTION IN PROGRESS ...")

        self.ui.stackedWidget.setCurrentWidget(self.ui.clusteringPage)
        self.repaintSignal.emit()

        start_time = time.time()
        for filename in os.listdir(path):
            if filename.endswith(".pcap"):
                p_path = os.path.join(path, filename)
                try:
                    self.featureExtractor.deepExtract(p_path, split=split, flows=flows)
                except BaseException as e:
                    messages.exception(e)

                    return
                direcotires = self.featureExtractor.getDirectories()
                self.directoriesSignal.emit(direcotires)
        passed_time = time.time() - start_time
        self.createdDirectories = self.featureExtractor.getDirectories()

        self.ui.featureTimeLabel.setText("Time: " + str(passed_time) + " sec.")
        self.ui.statusLabel.setText("CLUSTERING IN PROGRESS ...")
        self.repaintSignal.emit()

        self.clusteringEngine.updateFeatures(self.featureExtractor.getAll())

        self.clusteringResults.clear()
        clusteringTimeText = ""
        self.ui.clusteringTimeLabel.setText(clusteringTimeText)
        for mode in self.modes:
            start_time = time.time()
            results = copy.deepcopy(self.clusteringEngine.start(mode=mode, restart=True))
            passed_time = time.time() - start_time
            clusteringTimeText = self.ui.clusteringTimeLabel.text() + \
                                 "- " + mode + " = " + str(passed_time) + " sec.\n"
            self.ui.clusteringTimeLabel.setText(clusteringTimeText)
            time.sleep(0.3)
            self.repaintSignal.emit()
            self.clusteringResults.append(results)

        self.ui.statusLabel.setText("CLUSTERING COMPLETE\nPress OK to see results")
        self.repaintSignal.emit()

        self.resultsSignal.emit(self.modes, self.clusteringResults)

        self.ui.clusteringButtonBox.setEnabled(True)

