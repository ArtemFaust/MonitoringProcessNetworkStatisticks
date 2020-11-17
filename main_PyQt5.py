#!/usr/bin/env python
from PyQt5 import Qt, QtCore, QtGui, QtSql, QtWidgets, uic
import sys
import psutil, datetime
import subprocess
import time
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from collections import deque
import matplotlib.style as style
style.use('ggplot')

oldSendBytes = 0
oldRecvBytes = 0
plotSend = []
plotRecv = []
itemQW = None # переменная которая хранит значение выбранного item в listWidget

class Widget(QtWidgets.QWidget):
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        self.ui = uic.loadUi('ui/main.ui', self)  # Загружаем дизайн
# Эдементы дочерних окон
        self.showProcessInfoWidget = processInfoWidget()
        self.showProcessInfoWidget.setParent(self, QtCore.Qt.Sheet)

        self.showProcessStatistick = processStatistickWidget()
        self.showProcessStatistick.setParent(self, QtCore.Qt.Sheet)

# Выставляем параметры контекстного меню listWidget_3 и подключаем сигнал клика правой мышки к функции меню
        self.listWidget_3.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.listWidget_3.customContextMenuRequested[QtCore.QPoint].connect(self.listWidget_3ItemRightClicked)

# По срабатыванию таймера очищается tablewidget и снова заполняется
        self.timer = QtCore.QTimer()
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.ontimer)
        self.timer.timeout.connect(self.networkStatisticksProcessForlistWidget_3)
        self.timer.start()

# Таймер для построения графиков
        self.timefForGraph = QtCore.QTimer()
        self.timefForGraph.setInterval(1000)
        self.timefForGraph.timeout.connect(self.graph)

# Вставляем сплиттер и добавляем в него виджеты
        self.splitterH = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.splitterH.addWidget(self.stackedWidget)
        self.splitterH.addWidget(self.tableWidget)
        self.verticalLayout_3.addWidget(self.splitterH)

# Вызов функции программы вывода сетевых интерфейсов в listWodget
        self.interfacesListSet()
        self.networkStatistickProcess()

# Подклбючаем сигналы элементов интерфейса к функциям программы
        self.listWidget.itemClicked.connect(lambda item: self.listWidgetItemOnClick(item))
        self.listWidget_3.itemClicked.connect(lambda item: self.findItemIntableWidget(listWidgetItem=item))
        self.listWidget.itemClicked.connect(lambda item: self.ontimerGraphTimer(listWidgetItem=item))

# График для byte Send and recv
        self.figureSend = plt.figure()
        self.canvasSend = FigureCanvas(self.figureSend)
        self.axSend = self.figureSend.add_subplot(111)
        self.gridLayout.addWidget(self.canvasSend)

# Выводим меню в listWidget_3 и соединяем сигнал клика по меню с соотеветсвующей функцией
    def listWidget_3ItemRightClicked(self,QPos):
        self.listMenu = QtWidgets.QMenu()
        # Элементы меню
        menu_item = self.listMenu.addAction("Show process info")
        menu_item2 = self.listMenu.addAction("Show process statistick")
        # Связывание сигналов
        menu_item.triggered.connect(self.menuItemClicked)
        menu_item2.triggered.connect(self.menuItem2Clicked)

        parentPosition = self.listWidget_3.mapToGlobal(QtCore.QPoint(0, 0))
        self.listMenu.move(parentPosition + QPos)
        self.listMenu.show()

    def menuItem2Clicked(self):
        currentItemName = str(self.listWidget_3.currentItem().text())
        ps = int(currentItemName.split(" Pid:")[1])
        process = psutil.Process(ps)
        self.showProcessStatistick.ps = ps
        self.showProcessStatistick.process = process
        self.showProcessStatistick.timer.start()
        self.showProcessStatistick.show()


    def menuItemClicked(self):
        currentItemName = str(self.listWidget_3.currentItem().text())
        ps = int(currentItemName.split(" Pid:")[1])
        process = psutil.Process(ps)

        # Вставляем значения в элементы модального окна
        self.showProcessInfoWidget.label.setText(currentItemName)
        # cwd
        try:
            self.showProcessInfoWidget.label_9.setText(str(process.cwd()))
        except:
            self.showProcessInfoWidget.label_9.setText("None")
        # Status
        try:
            status = str(process.status())
            if status == "running":
                self.showProcessInfoWidget.label_10.setStyleSheet("color: green")
            else:
                self.showProcessInfoWidget.label_10.setStyleSheet("color: red")
            self.showProcessInfoWidget.label_10.setText(status)
        except:
            self.showProcessInfoWidget.label_10.setText("None")
        # exe
        try:
            self.showProcessInfoWidget.label_11.setText(str(process.exe()))
        except:
            self.showProcessInfoWidget.label_11.setText("None")
        # cmdline
        try:
            self.showProcessInfoWidget.label_12.setText(str(process.cmdline()))
        except:
            self.showProcessInfoWidget.label_12.setText("None")
        # create time
        try:
            self.showProcessInfoWidget.label_13.setText(str(process.create_time()))
        except:
            self.showProcessInfoWidget.label_13.setText("None")
        # parent
        try:
            self.showProcessInfoWidget.label_14.setText(str(process.parent()))
        except:
            self.showProcessInfoWidget.label_14.setText("None")

        # выводим список открытых файлов процесом
        #self.showProcessInfoWidget.listWidget
        self.showProcessInfoWidget.listWidget.clear()
        for i in process.open_files():
            item = QtWidgets.QListWidgetItem()
            item.setText(str(i[0]))
            self.showProcessInfoWidget.listWidget.addItem(item)

        # Show widget
        self.showProcessInfoWidget.show()

    # Функция вызываемая по клику на item listWidget (выводит графики)
    def listWidgetItemOnClick(self,item):
        global oldRecvBytes, oldSendBytes
        # Очистка listWidget_2 и вставляем информацию по интерфейсу item ами в listWidget_2
        color = 0
        self.listWidget_2.clear()
        ipaddressInterface = psutil.net_if_addrs().get(item.text())
        if ipaddressInterface != None and ipaddressInterface[0][1] != None:
            for data in ipaddressInterface[0]:
                try:
                    listWidget_2Item = QtWidgets.QListWidgetItem()
                    listWidget_2Item.setText(str(data))
                    if color == 0:
                        listWidget_2Item.setBackground(QtGui.QColor("white"))
                        color = 1
                    elif color == 1:
                        listWidget_2Item.setBackground(QtGui.QColor("gray"))
                        color = 0
                    self.listWidget_2.addItem(listWidget_2Item)
                except:
                    return
            try:
                listWidget_2Item = QtWidgets.QListWidgetItem()
                listWidget_2Item.setBackground(QtGui.QColor("gray"))
                listWidget_2Item.setText("Duplex: " + str(psutil.net_if_stats().get(item.text())[1]))
                self.listWidget_2.addItem(listWidget_2Item)

                listWidget_2Item = QtWidgets.QListWidgetItem()
                listWidget_2Item.setBackground(QtGui.QColor("white"))
                listWidget_2Item.setText("Speed: " + str(psutil.net_if_stats().get(item.text())[2]))
                self.listWidget_2.addItem(listWidget_2Item)

                listWidget_2Item = QtWidgets.QListWidgetItem()
                listWidget_2Item.setBackground(QtGui.QColor("gray"))
                listWidget_2Item.setText("Mtu: " + str(psutil.net_if_stats().get(item.text())[3]))
                self.listWidget_2.addItem(listWidget_2Item)
            except:
                return


# Функция выводит в listWidget все доступные сетевые интерфейсы
    def interfacesListSet(self):
        for interface in psutil.net_io_counters(pernic=True):
            listWidgetItem = QtWidgets.QListWidgetItem()
            listWidgetItem.setText(interface)
            listWidgetItem.setIcon(QtGui.QIcon("icons/network_card_thumb.png"))
            self.listWidget.addItem(listWidgetItem)


# Получаем статистику сетевой активности запущенных процессов
    def networkStatistickProcess(self):
        rowCount = 0
        row = 0
        collumn = 0
# Подчет количества нужных row
        for ps in psutil.pids():
            proc = psutil.Process(ps)
            if "pconn" in str(proc.connections()):
                for Pcon in proc.connections():
                    rowCount += 1
        self.tableWidget.setRowCount(rowCount)
# Вставляем данные в tableWidget
        for ps in psutil.pids():
            proc = psutil.Process(ps)
            if "pconn" in str(proc.connections()):
                for Pcon in proc.connections(kind="inet"):
                    item = QtWidgets.QTableWidgetItem()
                    item.setText(proc.name())
                    self.tableWidget.setItem(row, 0, item)
                    collumn += 1
                    for i in Pcon:
                        item = QtWidgets.QTableWidgetItem()
                        item.setText(str(i))
                        self.tableWidget.setItem(row, collumn, item)
                        collumn += 1
                    row += 1
                    collumn = 0
        self.tableWidget.setHorizontalHeaderLabels(["Process name","Fd", "Famili", "Type", "Local addr", "Remote addr", "Status"])
        self.tableWidget.resizeColumnsToContents()
# Автоматическое расширение tableWidget на всю ширину окна
        header = self.tableWidget.horizontalHeader()
        header.setStretchLastSection(True)



# Функция срабатывания таймера
    def ontimer(self):
        self.tableWidget.clear()
        self.networkStatistickProcess()

# Получаем список процессов имеющих сетевую активность и вставляем в listWidhet_3
    def networkStatisticksProcessForlistWidget_3(self):
        global ForPlotByteSend, ForPlotByteRecv
        for ps in psutil.pids():
            try:
                proc = psutil.Process(ps)
                if "pconn" in str(proc.connections()):

                    # Вставляем items в listWidget содержачие имя и pid процесса
                    item = QtWidgets.QListWidgetItem()
                    item.setText("Process: " + proc.name() + " Pid: " + str(ps))
                    item.setIcon(QtGui.QIcon("icons/exe-icon.png"))
                    # На каждой интерации обновления проверяем если вновь создаваемый item уже есть то делаем фон белый если item новый (новый процесс)
                    # то окрашиваем его зеленым
                    items = self.listWidget_3.findItems(item.text(), QtCore.Qt.MatchExactly)
                    if len(items) > 0:
                        for iTem in items:
                            iTem.setBackground(QtGui.QColor("white"))
                    else:
                        item.setBackground(QtGui.QColor("green"))
                        self.listWidget_3.addItem(item)
                        # Вызываем функцию ощистки ListWidget_3 от элементов завершенных процессов
                self.listWidgetClearItem()

            except:
                return




# функция очистки ListWidget_3 от items завершенных процессов
    def listWidgetClearItem(self):
        # Получаем список всех элементов
        items = []
        for index in range(self.listWidget_3.count()):
            items.append(self.listWidget_3.item(index))
        # Проверяем наличие существования процесса
        for Item in items:
            process = Item.text().split("Pid:")
            rezult = psutil.pid_exists(int(process[1]))
            # Если процесс не существует то окрашиваем в красный и удаляем элемент из listWidget
            if rezult == False:
                items = self.listWidget_3.findItems(Item.text(), QtCore.Qt.MatchExactly)
                for i in items:
                    i.setBackground(QtGui.QColor("red"))
                    self.listWidget_3.takeItem(self.listWidget_3.row(i))
            else:
                proc = psutil.Process(int(Item.text().split("Pid:")[1]))

    # Функция выделения элемента в listWidget_3
    # ищем item в tableWidget скролимся к нему
    def findItemIntableWidget(self,listWidgetItem):
        itemText = listWidgetItem.text().split("Process: ")
        itemText = itemText[1]
        itemText = itemText.split(" Pid: ")
        itemText = itemText[0]

        item = self.tableWidget.findItems(itemText, QtCore.Qt.MatchExactly)
        self.tableWidget.scrollToItem(item[0])

# Функция запускает таймер и присваевает значение глобальной переменной которая хранит значение выбранного item в listWidget
    def ontimerGraphTimer(self,listWidgetItem):
        global itemQW , selectedInterface, plotRecv, plotSend
        self.timefForGraph.start()
        # при выборе нового интерфейса аднные сбрасываются
        if itemQW != listWidgetItem:
            plotRecv = []
            plotSend = []
        itemQW = listWidgetItem
        self.graph()

# Строим графики
    def graph(self):
        global oldRecvBytes, oldSendBytes, plotRecv, plotSend

        self.axSend.cla()
        # Byte send
        new_value = psutil.net_io_counters(pernic=True).get(itemQW.text())[0]
        plotSend.append(new_value - oldSendBytes)
        oldSendBytes = new_value
        if int(len(plotSend)) >= 60:
            self.axSend.plot(plotSend[-60:], label="Byte send (TX)")
        else:
            self.axSend.plot(plotSend[1:], label="Byte send (TX)")
        self.axSend.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3,
                           ncol=2, mode="expand", borderaxespad=0.)
        self.canvasSend.draw()

        # Byte recv
        new_value = psutil.net_io_counters(pernic=True).get(itemQW.text())[1]
        plotRecv.append(new_value - oldRecvBytes)
        oldRecvBytes = new_value
        if int(len(plotRecv)) >= 60 :
            self.axSend.plot(plotRecv[-60:], label="Byte recv (RX)")
        else:
            self.axSend.plot(plotRecv[1:], label="Byte recv (RX)")
        self.axSend.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3,
                ncol=2, mode="expand", borderaxespad=0.)
        self.canvasSend.draw()

# Класс виджета для processInfo
class processInfoWidget(QtWidgets.QWidget):
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        self.ui = uic.loadUi('ui/showProcessInfo.ui', self)
        self.pushButton.clicked.connect(self.closeWidget)
        self.pushButton_2.clicked.connect(self.suspendProcess)
        self.pushButton_3.clicked.connect(self.killingProcess)

    def killingProcess(self):
        if self.pushButton_3.text() == "Kill":
            messageBox = QtWidgets.QMessageBox()
            messageBox.addButton(QtWidgets.QMessageBox.Yes)
            messageBox.addButton(QtWidgets.QMessageBox.No)
            messageBox.setText("Kill this process?")
            rezult = messageBox.exec_()
            if rezult == QtWidgets.QMessageBox.No:
                pass
            elif rezult == QtWidgets.QMessageBox.Yes:
                process = psutil.Process(int(self.label.text().split("Pid: ")[1]))
                process.kill()
                QtWidgets.QMessageBox.information(None, "Process killed", "Process killed")
                self.label_10.setStyleSheet("color: red")
                self.label_10.setText("Killed")



    def closeWidget(self):
        self.close()

    def suspendProcess(self):
        if self.pushButton_2.text() == "Suspend":
            messageBox = QtWidgets.QMessageBox()
            messageBox.addButton(QtWidgets.QMessageBox.Yes)
            messageBox.addButton(QtWidgets.QMessageBox.No)
            messageBox.setText("Susped this process?")
            rezult = messageBox.exec_()
            if rezult == QtWidgets.QMessageBox.No:
                pass
            elif rezult == QtWidgets.QMessageBox.Yes:
                process = psutil.Process(int(self.label.text().split("Pid: ")[1]))
                process.suspend()
                self.pushButton_2.setText("Resume")
                try:
                    status = str(process.status())
                    if status == "running":
                        self.label_10.setStyleSheet("color: green")
                    else:
                        self.label_10.setStyleSheet("color: red")
                    self.label_10.setText(status)
                except:
                    self.label_10.setText("None")

        elif self.pushButton_2.text() == "Resume":
            process = psutil.Process(int(self.label.text().split("Pid: ")[1]))
            process.resume()
            self.pushButton_2.setText("Suspend")
            try:
                status = str(process.status())
                if status == "running":
                    self.label_10.setStyleSheet("color: green")
                else:
                    self.showProcessInfoWidget.label_10.setStyleSheet("color: red")
                self.label_10.setText(status)
            except:
                self.label_10.setText("None")




# Класс виджета для processStatistick
class processStatistickWidget(QtWidgets.QWidget):
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        self.spForCpu = []
        self.spForMem = []
        self.ps = None
        self.process = None

        self.ui = uic.loadUi('ui/procesStatistick.ui', self)
        self.pushButton.clicked.connect(self.closeWidget)

# memory statistics
        self.figureMem = plt.figure()
        self.canvasMem = FigureCanvas(self.figureMem)
        self.axMem = self.figureMem.add_subplot(111)
        self.labelMem = QtWidgets.QLabel()
        self.labelMem.setText("Memory statistick")
        self.verticalLayout.addWidget(self.labelMem)
        self.verticalLayout.addWidget(self.canvasMem)

# CPU statistick
        self.figureCPU = plt.figure()
        self.canvasCPU = FigureCanvas(self.figureCPU)
        self.axCPU = self.figureCPU.add_subplot(111)
        self.labeCPU = QtWidgets.QLabel()
        self.labeCPU.setText("CPU statistick")
        self.verticalLayout.addWidget(self.labeCPU)
        self.verticalLayout.addWidget(self.canvasCPU)

        self.timer = QtCore.QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.timeout)

    def timeout(self):
        # CPU
        self.axCPU.cla()
        self.spForCpu.append(self.process.cpu_percent())
        for_x = [x for x in range(0, int(len(self.spForCpu)), 1)]
        if int(len(self.spForCpu)) >=60:
            self.axCPU.fill_between(range(0,60,1), self.spForCpu[-60:])
        else:
            self.axCPU.fill_between(for_x, self.spForCpu[-60:])
        self.canvasCPU.draw()

        # Memory
        self.axMem.cla()
        self.spForMem.append(self.process.memory_percent())
        for_x2 = [x for x in range(0, int(len(self.spForMem)), 1)]
        if int(len(self.spForMem)) >= 60:
            self.axMem.fill_between(range(0,60,1), self.spForMem[-60:])
        else:
            self.axMem.fill_between(for_x2, self.spForMem[-60:])
        self.canvasMem.draw()

    def closeWidget(self):
        self.axCPU.cla()
        self.axMem.cla()
        self.timer.stop()
        self.ps = None
        self.process = None
        self.spForCpu = []
        self.spForMem = []
        self.close()


app = QtWidgets.QApplication(sys.argv)
Form = Widget()
Form.show()
sys.exit(app.exec())
