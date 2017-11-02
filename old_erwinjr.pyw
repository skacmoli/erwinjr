#!/usr/bin/env python2
# -*- coding:utf-8 -*-

#===============================================================================
# ErwinJr is a simulation program for quantum semiconductor lasers.
# Copyright (C) 2012 Kale J. Franz, PhD
# Copyright (C) 2017 Ming Lyu
#
# A portion of this code is Copyright (c) 2011, California Institute of 
# Technology ("Caltech"). U.S. Government sponsorship acknowledged.
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#===============================================================================

# TODO: 
# replace np.hstack (done, but self.strata part to test)
# find replacement for psyco
# try to seperate this file to smaller ones
# check unnecessary function call
# Ctrl+z support
# add status bar
# add target wavelength for optimization
# In plot controls, add "show one period" 
# save and load pickle for qclayers

from __future__ import division
import os, sys
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import PyQt4.Qwt5 as Qwt
import numpy as np
from numpy import pi, sqrt
from functools import partial
import time

import matplotlib
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D

import settings
import SupportClasses
from QCLayers import QCLayers, cst
from Strata import Strata
from QCLayers import h, c0, e0
import SaveLoad


#============================================================================
# Version
#============================================================================
ejVersion = 171027
majorVersion = '3.1.0'

#============================================================================
# Debug options
#============================================================================
DEBUG = 1
if DEBUG >=3: 
    import pickle


class MainWindow(QMainWindow):
    def __init__(self, fileName=None, parent=None):
        super(MainWindow, self).__init__(parent)

        self.colors = [(149,115,179), (110,124,190), (147,177,132),
                (174,199,82), (128,128,130), (218,189,63), (223,155,74),
                (210,87,71), (185,82,159), (105,189,69), (20,20,20),
                (110,205,222), (57,82,164)]

        self.newLineChar = '\n'
        if sys.platform == "darwin":
            self.newLineChar = '\n'

        self.qclayers = QCLayers()
        self.strata = Strata()
        self.numMaterials = self.qclayers.numMaterials #=8, to improve (TODO)

        self.stratumMaterialsList = ['Active Core', 
                                     'InP',
                                     'GaAs',
                                     'InGaAs', 
                                     'InAlAs', 
                                     'Au', 
                                     'SiNx', 
                                     'SiO2', 
                                     'Air']
        self.waveguideFacetsList = ['as-cleaved + as-cleaved',
                                    'as-cleaved + perfect HR',
                                    'as-cleaved + perfect AR',
                                    'perfect AR + perfect HR',
                                    'custom coating + as-cleaved',
                                    'custom coating + perfect HR',
                                    'custom coating + perfect AR']
        self.substratesList = ['InP', 'GaAs', 'GaSb', 'GaN']

        self.filename = fileName
        self.plotDirty = False
        self.solveType = None

        self.plotVX = False
        self.plotVL = False
        self.plotLH = False
        self.plotSO = False

        self.stateHolder = []
        self.pairSelected = False

        self.create_Quantum_menu()
        self.create_main_frame()

        self.create_zoomer()


        self.input_substrate('InP')
        self.update_inputBoxes()
        self.layerTable_refresh()
        self.layerTable.selectRow(1)
        self.layerTable.setFocus()

        self.stratumTable_refresh()

        #  self.update_inputBoxes()
        self.update_stratum_inputBoxes()

        qsettings = QSettings()
        self.recentFiles = qsettings.value("RecentFiles").toStringList()
        self.restoreGeometry(
                qsettings.value("MainWindow/Geometry").toByteArray())
        self.restoreState(qsettings.value("MainWindow/State").toByteArray())
        self.updateFileMenu()

        self.dirty = False

        if self.filename:
            self.fileOpen(self.filename)
        else:
            QTimer.singleShot(0, self.loadInitialFile)

        self.dirty = False
        self.update_windowTitle()





#===============================================================================
# Create Main Frame        
#===============================================================================

    def create_main_frame(self):

        self.mainTabWidget = QTabWidget()

        # ##########################
        #
        # Quantum Tab
        #
        # ##########################

        # Platform dependent settings, eg. layerout size settings
        if sys.platform == 'win32': 
            self.layerTableSize = 340
            self.DescriptionBoxWidth = 190
            self.LpStringBoxWidth=135
        elif sys.platform == 'darwin':
            self.layerTableSize = 405
            self.DescriptionBoxWidth = 285
            self.LpStringBoxWidth=130
        elif sys.platform == 'linux2':
            self.layerTableSize = 365
            self.DescriptionBoxWidth = 240
            self.LpStringBoxWidth=150
        else:
            QMessageBox.warning(self, 'ErwinJr - Warning', 
                    'Platform %s not tested.'%sys.platform)
            self.layerTableSize = 340
            self.DescriptionBoxSize = 190
        self.pairSelectStringWidth = self.DescriptionBoxWidth

        #set up quantumCanvas for band structure plot
        self.quantumCanvas = Qwt.QwtPlot(self)
        self.quantumCanvas.setCanvasBackground(Qt.white)
        self.quantumCanvas.canvas().setCursor(Qt.ArrowCursor)

        #set up layerTable
        self.layerTable = QTableWidget()
        self.layerTable.setSelectionBehavior(QTableWidget.SelectRows)
        self.layerTable.setSelectionMode(QTableWidget.SingleSelection)
        self.layerTable.setMaximumWidth(self.layerTableSize)
        self.layerTable.setMinimumWidth(self.layerTableSize)
        self.connect(self.layerTable,
                SIGNAL("itemChanged(QTableWidgetItem*)"),
                self.layerTable_itemChanged)
        self.connect(self.layerTable, SIGNAL("itemSelectionChanged()"),
                self.layerTable_itemSelectionChanged)

        #set up buttons
        self.deleteLayerButton = QPushButton("Delete Layer")
        self.connect(self.deleteLayerButton, SIGNAL("clicked()"),
                self.delete_layer)
        self.insertLayerAboveButton = QPushButton("Insert Layer Above")
        self.connect(self.insertLayerAboveButton, SIGNAL("clicked()"),
                self.insert_layerAbove)
        self.OptimizeFoMButton = QPushButton("Optimize Width (FoM)")
        self.OptimizeFoMButton.setEnabled(False)
        self.connect(self.OptimizeFoMButton, SIGNAL("clicked()"), partial(
            self.OptimizeLayer, goal = self.qclayers.figure_of_merit))
        self.OptimizeDipoleButton = QPushButton("Optimize Width (Dipole)")
        self.connect(self.OptimizeDipoleButton, SIGNAL("clicked()"), partial(
            self.OptimizeLayer, goal = self.qclayers.dipole))
        self.OptimizeDipoleButton.setEnabled(False)
        self.solveWholeButton = QPushButton("Solve Whole")
        self.connect(self.solveWholeButton, SIGNAL("clicked()"),
                self.solve_whole)
        self.solveBasisButton = QPushButton("Solve Basis")
        self.connect(self.solveBasisButton, SIGNAL("clicked()"),
                self.solve_basis)

        #set up left inputs
        self.substrateBox = QComboBox()
        self.substrateBox.addItems(self.substratesList)
        self.connect(self.substrateBox,
                SIGNAL("currentIndexChanged(const QString)"), 
                self.input_substrate)

        inputEFieldLabel = QLabel('<center><b><i>E<sub>field</sub></i></b></center>')
        self.inputEFieldBox = QDoubleSpinBox()
        self.inputEFieldBox.setDecimals(1)
        self.inputEFieldBox.setSuffix(' kV/cm')
        self.inputEFieldBox.setRange(0.0,250.0)
        self.connect(self.inputEFieldBox, 
                SIGNAL("valueChanged(double)"), 
                self.input_EField)

        inputHorzResLabel = QLabel('<center><b>Horizontal<br>Resolution</b></center>')
        self.inputHorzResBox = QComboBox();
        self.inputHorzResBox.addItems(['1.0','0.5','0.25','0.2','0.1'])
        # remove 0.25? because to 0.1
        self.connect(self.inputHorzResBox, 
                SIGNAL("currentIndexChanged(int)"), 
                self.input_horzRes)

        inputVertResLabel = QLabel('<center><b>Vertical<br>Resolution</b></center>')
        self.inputVertResBox = QDoubleSpinBox()
        self.inputVertResBox.setDecimals(2)
        self.inputVertResBox.setValue(0.5)
        self.inputVertResBox.setRange(0.0,10.0)
        self.inputVertResBox.setSingleStep(0.1)
        self.inputVertResBox.setSuffix(' meV')
        self.connect(self.inputVertResBox, SIGNAL("valueChanged(double)"), 
                self.input_vertRes)

        inputRepeatsLabel = QLabel('<center><b>Structure Repeats</b></center>')
        self.inputRepeatsBox = QSpinBox()
        self.inputRepeatsBox.setValue(1)
        self.inputRepeatsBox.setRange(1,5)
        self.connect(self.inputRepeatsBox, SIGNAL("valueChanged(int)"), 
                self.input_repeats)

        self.inputARInjectorCheck = QCheckBox("AR->Injector")
        self.inputInjectorARCheck = QCheckBox("Injector->AR")
        self.inputARInjectorCheck.setChecked(True)
        self.inputInjectorARCheck.setChecked(True)
        basis_groupBox = QGroupBox("Basis Divisions")
        vbox = QVBoxLayout()
        vbox.addWidget(self.inputARInjectorCheck)
        vbox.addWidget(self.inputInjectorARCheck)
        basis_groupBox.setLayout(vbox)
        self.connect(self.inputARInjectorCheck, SIGNAL("stateChanged(int)"), 
                self.input_basis)
        self.connect(self.inputInjectorARCheck, SIGNAL("stateChanged(int)"), 
                self.input_basis)

        # Lp groupbox
        self.LpFirstSpinbox = QSpinBox()
        self.LpFirstSpinbox.setValue(1)
        self.LpFirstSpinbox.setRange(1,1)
        self.connect(self.LpFirstSpinbox, SIGNAL("valueChanged(int)"), 
                self.update_inputBoxes)
        self.LpLastSpinbox  = QSpinBox()
        self.LpLastSpinbox.setValue(1)
        self.LpLastSpinbox.setRange(1,1)
        self.connect(self.LpLastSpinbox, SIGNAL("valueChanged(int)"), 
                self.update_inputBoxes)
        self.LpStringBox = QTextEdit('')
        self.LpStringBox.setReadOnly(True)
        self.LpStringBox.setSizePolicy(
                QSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed))
        self.LpStringBox.setMaximumHeight(95)
        self.LpStringBox.setMaximumWidth(self.LpStringBoxWidth)
        LpLayout = QGridLayout()
        LpLayout.addWidget(QLabel('<b>first</b>'), 0,0)
        LpLayout.addWidget(QLabel('<b>last</b>'), 0,1)
        LpLayout.addWidget(self.LpFirstSpinbox, 1,0)
        LpLayout.addWidget(self.LpLastSpinbox, 1,1)
        LpLayout.addWidget(self.LpStringBox, 2,0, 1,2)
        LpLayout_groupBox = QGroupBox("Period Info")
        LpLayout_groupBox.setLayout(LpLayout)

        # Global Optimization groupbox
        GlobalOptLayout = QGridLayout()
        self.targetWL_box = QLineEdit('')
        self.targetWL_box.setValidator(QDoubleValidator(0,100,1))
        self.targetWL_box.setSizePolicy(
                QSizePolicy(QSizePolicy.Minimum,QSizePolicy.Ignored))
        #  self.targetWL_box.setMaximumWidth(50)
        self.connect(self.targetWL_box, SIGNAL("editingFinished()"), 
                self.set_targetWL)
        GlobalOptLayout.addWidget(QLabel(u"<b>\u03BB</b>:"), 0, 0)
        GlobalOptLayout.addWidget(self.targetWL_box, 0, 1)
        GlobalOptLayout.addWidget(QLabel('um'), 0, 2)
        GlobalOptLayout.addWidget(QLabel("<b>Target function</b>"), 1,0,1,3)
        self.OptGoalsName = ('FoM', 'Dipole')
        self.OptGoalsFunc = (self.qclayers.figure_of_merit, 
                self.qclayers.dipole)
        #  self.OptGoalsDict = {'FoM':self.qclayers.figure_of_merit, 
                #  'Dipole': self.qclayers.dipole}
        self.goalFuncBox = QComboBox()
        self.goalFuncBox.addItems(self.OptGoalsName)
        #  self.OptGoal = self.OptGoalsDict[str(self.goalFuncBox.currentText())]
        self.OptGoal = self.OptGoalsFunc[self.goalFuncBox.currentIndex()]
        self.connect(self.goalFuncBox, 
                SIGNAL("currentIndexChanged(int)"), 
                self.set_goal)
        GlobalOptLayout.addWidget(self.goalFuncBox, 2, 0, 1, 3)
        self.GlobalOptButton = QPushButton("Optimize")
        self.connect(self.GlobalOptButton, SIGNAL("clicked()"),
                self.GlobalOptimization)
        GlobalOptLayout.addWidget(self.GlobalOptButton, 3, 0, 1, 3)
        GlobalOptLayout_groupBox = QGroupBox("Global Optimization")
        GlobalOptLayout_groupBox.setLayout(GlobalOptLayout)

        #set up material composition inputs
        self.mtrl_header1 = QLabel(
                '<center><b>In<sub>x</sub>Ga<sub>1-x</sub>As</b></center>')
        self.mtrl_header2 = QLabel(
                '<center><b>Al<sub>1-x</sub>In<sub>x</sub>As</b></center>')
        self.mtrl_header3 = QLabel('<center><b>Offset</b></center')

        self.MoleFracWellBox = []
        self.MoleFracBarrBox = []
        self.offsetLabel = []
        for n in range(self.numMaterials//2):
            self.MoleFracWellBox.append(QDoubleSpinBox())
            self.MoleFracWellBox[n].setDecimals(3)
            self.MoleFracWellBox[n].setValue(0.53)
            self.MoleFracWellBox[n].setRange(0.0, 1.0)
            self.MoleFracWellBox[n].setSingleStep(0.001)
            self.connect(self.MoleFracWellBox[n],
                    SIGNAL("editingFinished()"), 
                    partial(self.input_moleFrac, 2*n))
            self.MoleFracBarrBox.append(QDoubleSpinBox())
            self.MoleFracBarrBox[n].setDecimals(3)
            self.MoleFracBarrBox[n].setValue(0.52)
            self.MoleFracBarrBox[n].setRange(0.0, 1.0)
            self.MoleFracBarrBox[n].setSingleStep(0.001)
            self.connect(self.MoleFracBarrBox[n],
                    SIGNAL("editingFinished()"), 
                    partial(self.input_moleFrac, 2*n+1))
            self.offsetLabel.append(QLabel(''))

        self.strainDescription = QLabel('')
        self.LOPhononDescription = QLabel('')
        #self.strainDescription.setTextAlignment(Qt.AlignHCenter)
        mtrl_grid = QGridLayout()
        mtrl_title   = QLabel('<center><b>Mole Fractions</b></center>')
        mtrl_grid.addWidget(mtrl_title, 0,0, 1,4)
        mtrl_grid.addWidget(self.mtrl_header1, 1,1)
        mtrl_grid.addWidget(self.mtrl_header2, 1,2)
        mtrl_grid.addWidget(self.mtrl_header3, 1,3)
        for n in range(self.numMaterials//2):
            mtrl_grid.addWidget(QLabel('<center><b>#%d</b></center>'%(n+1)), 
                    2+n, 0)
            mtrl_grid.addWidget(self.MoleFracWellBox[n], 2+n, 1)
            mtrl_grid.addWidget(self.MoleFracBarrBox[n], 2+n, 2)
            mtrl_grid.addWidget(self.offsetLabel[n], 2+n, 3)

        mtrl_well    = QLabel('<center>(well)</center>')
        mtrl_barr    = QLabel('<center>(barrier)</center>')
        mtrl_grid.addWidget(mtrl_well, 6,1)
        mtrl_grid.addWidget(mtrl_barr, 6,2)
        mtrl_grid.addWidget(self.strainDescription, 7,0, 1,4)
        mtrl_grid.addWidget(self.LOPhononDescription, 8,0, 1,4)
        self.mtrl_groupBox = QGroupBox()
        self.mtrl_groupBox.setLayout(mtrl_grid)

        #set up description box
        self.DescriptionBox = QTextEdit('')
        self.DescriptionBox.setReadOnly(False)
        self.DescriptionBox.setSizePolicy(QSizePolicy(
            QSizePolicy.Fixed,QSizePolicy.Fixed))
        self.DescriptionBox.setMaximumHeight(40)
        self.DescriptionBox.setMaximumWidth(self.DescriptionBoxWidth)
        self.connect(self.DescriptionBox, SIGNAL("textChanged()"), 
                self.input_description)
        DescLayout = QVBoxLayout()
        DescLayout.addWidget(self.DescriptionBox)
        DescLayout_groupBox = QGroupBox("Description")
        DescLayout_groupBox.setLayout(DescLayout)

        #set up plot control inputs
        self.zoomButton = QPushButton("Zoom")
        self.zoomButton.setCheckable(True)
        self.connect(self.zoomButton, SIGNAL("toggled(bool)"), self.zoom)
        zoomOutButton = QPushButton("Zoom Out")
        self.connect(zoomOutButton, SIGNAL("clicked()"), self.zoom_out)
        self.panButton = QPushButton("Pan")
        self.panButton.setCheckable(True)
        self.connect(self.panButton, SIGNAL("toggled(bool)"), self.pan)
        self.wellSelectButton = QPushButton("Layer Select")
        self.wellSelectButton.setCheckable(True)
        self.connect(self.wellSelectButton, SIGNAL("toggled(bool)"), 
                self.well_select)
        clearWFsButton = QPushButton("Clear")
        self.connect(clearWFsButton, SIGNAL("clicked()"), self.clear_WFs)
        plotControl_grid = QGridLayout()
        plotControl_grid.addWidget(self.wellSelectButton, 0,0, 1,2)
        plotControl_grid.addWidget(self.zoomButton, 1,0, 1,1)
        plotControl_grid.addWidget(zoomOutButton, 1,1, 1,1)
        plotControl_grid.addWidget(self.panButton, 2,0, 1,1)
        plotControl_grid.addWidget(clearWFsButton, 2,1, 1,1)
        plotControl_groupBox = QGroupBox("Plot Controls")
        plotControl_groupBox.setLayout(plotControl_grid)

        #set up Calculate controls
        self.pairSelectButton = QPushButton("Pair Select")
        self.pairSelectButton.setCheckable(True)
        self.connect(self.pairSelectButton, SIGNAL("toggled(bool)"), 
                self.pair_select)
        self.FoMButton = QPushButton("Figure of Merit")
        self.FoMButton.setEnabled(False)
        self.connect(self.FoMButton, SIGNAL("clicked()"), self.figure_of_merit)
        self.transferOpticalParametersButton = QPushButton("-> Optical Params")
        self.transferOpticalParametersButton.setEnabled(False)
        self.connect(self.transferOpticalParametersButton, 
                SIGNAL("clicked()"), 
                self.transfer_optical_parameters)
        self.pairSelectString = QTextEdit('')
        self.pairSelectString.setReadOnly(True)
        self.pairSelectString.setSizePolicy(QSizePolicy(
            QSizePolicy.Fixed,QSizePolicy.Fixed))

        #  self.pairSelectString.setMaximumHeight(130)
        self.pairSelectString.setMaximumWidth(self.pairSelectStringWidth)
        calculateControl_grid = QGridLayout()
        calculateControl_grid.addWidget(self.pairSelectButton, 0,0, 1,2)
        calculateControl_grid.addWidget(self.FoMButton, 1,0, 1,1)
        calculateControl_grid.addWidget(self.transferOpticalParametersButton, 1,1, 1,1)
        calculateControl_grid.addWidget(self.pairSelectString, 2,0, 1,2)
        calculateControl_groupBox = QGroupBox("Calculate")
        calculateControl_groupBox.setLayout(calculateControl_grid)

        #lay out GUI
        #vBox1
        vBox1 = QVBoxLayout()
        vBox1.addWidget(QLabel("<center><b>Substrate</b></center>"))
        vBox1.addWidget(self.substrateBox)
        vBox1.addWidget(inputEFieldLabel)
        vBox1.addWidget(self.inputEFieldBox)
        vBox1.addWidget(inputHorzResLabel)
        vBox1.addWidget(self.inputHorzResBox)
        vBox1.addWidget(inputVertResLabel)
        vBox1.addWidget(self.inputVertResBox)
        vBox1.addWidget(inputRepeatsLabel)
        vBox1.addWidget(self.inputRepeatsBox)
        vBox1.addWidget(basis_groupBox)
        vBox1.addWidget(LpLayout_groupBox)
        vBox1.addWidget(GlobalOptLayout_groupBox)
        #vBox1.addWidget(designBy_groupBox)
        vBox1.addStretch()

        #vBox2
        vBox2 = QGridLayout()
        vBox2.addWidget(self.insertLayerAboveButton, 0,0)
        vBox2.addWidget(self.deleteLayerButton, 0,1)        
        vBox2.addWidget(self.OptimizeFoMButton, 1,0)
        vBox2.addWidget(self.OptimizeDipoleButton, 1,1)
        vBox2.addWidget(self.layerTable, 2,0, 1,2)
        #vBox2.addWidget(updateButton)      

        #vBox3
        vBox3 = QVBoxLayout()
        vBox3.addWidget(self.solveBasisButton)
        vBox3.addWidget(self.solveWholeButton)
        vBox3.addWidget(DescLayout_groupBox)
        vBox3.addWidget(self.mtrl_groupBox)
        vBox3.addWidget(plotControl_groupBox)
        vBox3.addWidget(calculateControl_groupBox)
        vBox3.addStretch()

        #vBox4
        vBox4 = QVBoxLayout()
        vBox4.addWidget(self.quantumCanvas)

        quantumLayout = QHBoxLayout()
        quantumLayout.addLayout(vBox1)
        quantumLayout.addLayout(vBox2)
        quantumLayout.addLayout(vBox3)
        quantumLayout.addLayout(vBox4)

        self.quantumWidget = QWidget()
        self.quantumWidget.setLayout(quantumLayout)
        self.quantumWidget.setAutoFillBackground(True)
        self.quantumWidget.setBackgroundRole(QPalette.Window)


        # ##########################
        #
        # Optical Tab
        #
        # ##########################

        #vBox1
        vBox1Grid = QGridLayout()

        self.editOpticalParametersBox = QCheckBox('Edit Parameters')
        self.editOpticalParametersBox.setChecked(False)
        self.connect(self.editOpticalParametersBox, 
                SIGNAL('toggled(bool)'), 
                self.edit_optical_parameters)
        vBox1Grid.addWidget(self.editOpticalParametersBox, 
                0,0, 1,2, Qt.AlignCenter)

        wlLabel = QLabel('<b><center>Wavelength</center</b>')
        vBox1Grid.addWidget(wlLabel, 1,0, 1,2)
        self.wavelengthBox = QDoubleSpinBox()
        self.wavelengthBox.setValue(self.strata.wavelength)
        self.wavelengthBox.setSuffix(u' \u03BCm')
        self.wavelengthBox.setDecimals(3)
        self.wavelengthBox.setSingleStep(0.1)
        self.wavelengthBox.setRange(0.0,30.0)
        self.wavelengthBox.setReadOnly(True)
        self.wavelengthBox.setStyleSheet('color:gray')
        self.connect(self.wavelengthBox, SIGNAL("valueChanged(double)"), 
                self.input_wavelength)
        vBox1Grid.addWidget(self.wavelengthBox, 2,0, 1,2)

        vBox1Grid.addItem(QSpacerItem(20,20), 3,0, 1,2)

        vBox1Grid.addWidget(QLabel(
            '<b><center>Operating<br>Field</center></b>'), 4,0, 1,1)
        self.operatingFieldBox = QDoubleSpinBox()
        self.operatingFieldBox.setDecimals(1)
        self.operatingFieldBox.setRange(0.,300.)
        self.operatingFieldBox.setSingleStep(1)
        self.operatingFieldBox.setSuffix(u' kV/cm')
        self.operatingFieldBox.setReadOnly(True)
        self.operatingFieldBox.setStyleSheet('color:gray')
        self.connect(self.operatingFieldBox, SIGNAL("valueChanged(double)"), 
                self.input_operatingField)
        vBox1Grid.addWidget(self.operatingFieldBox, 5,0, 1,1)

        vBox1Grid.addWidget(QLabel(
            '<b><center>Active Core<br>Period Length</center></b>'), 4,1, 1,1)
        self.ACPeriodLengthBox = QDoubleSpinBox()
        self.ACPeriodLengthBox.setDecimals(1)
        self.ACPeriodLengthBox.setRange(0.,10000.)
        self.ACPeriodLengthBox.setSingleStep(1)
        self.ACPeriodLengthBox.setSuffix(u' \u212B')
        self.connect(self.ACPeriodLengthBox, SIGNAL("valueChanged(double)"), 
                self.input_ACPeriodLength)
        self.ACPeriodLengthBox.setReadOnly(True)
        self.ACPeriodLengthBox.setStyleSheet('color:gray')
        vBox1Grid.addWidget(self.ACPeriodLengthBox, 5,1, 1,1)

        vBox1Grid.addWidget(QLabel(
            '<b><center>Active Core<br>Periods</center></b>'), 6,0, 1,1)
        self.ACPeriodsBox = QSpinBox()
        self.ACPeriodsBox.setRange(1,99)
        self.connect(self.ACPeriodsBox, SIGNAL("valueChanged(int)"), 
                self.input_ACPeriods)
        vBox1Grid.addWidget(self.ACPeriodsBox, 7,0, 1,1)

        vBox1Grid.addWidget(QLabel(
            '<b><center>Operating<br>Voltage</center></b>'), 6,1, 1,1)
        self.OperatingVoltageBox = QLineEdit()
        self.OperatingVoltageBox.setMaximumWidth(150)
        self.OperatingVoltageBox.setReadOnly(True)
        self.OperatingVoltageBox.setStyleSheet('color:gray')
        vBox1Grid.addWidget(self.OperatingVoltageBox, 7,1, 1,1)

        vBox1Grid.addItem(QSpacerItem(20,20), 8,0, 1,2)

        vBox1Grid.addWidget(QLabel(
            u'<b><center><i>\u03B1<sub>core</sub></i></center></b>'), 9,0, 1,1)
        self.aCoreBox = QLineEdit()
        self.aCoreBox.setMaximumWidth(150)
        self.aCoreBox.setReadOnly(True)
        self.aCoreBox.setStyleSheet('color:gray')
        self.connect(self.aCoreBox, SIGNAL("editingFinished()"), 
                self.input_aCore)
        vBox1Grid.addWidget(self.aCoreBox, 10,0, 1,1)

        vBox1Grid.addWidget(QLabel(
            u'<center><b>\u00F1<i><sub>core</sub></i></b></center>'), 9,1, 1,1)
        self.nCoreBox = QLineEdit()
        self.nCoreBox.setMaximumWidth(150)
        self.nCoreBox.setReadOnly(True)
        self.nCoreBox.setStyleSheet('color:gray')
        vBox1Grid.addWidget(self.nCoreBox, 10,1, 1,1)

        vBox1Grid.addItem(QSpacerItem(20,20), 11,0, 1,2)

        vBox1Grid.addWidget(QLabel(
            u'<center><b>Transition Broadening</b></center>'), 12,0, 1,2)
        self.transitionBroadeningBox = QDoubleSpinBox()
        self.transitionBroadeningBox.setMaximumWidth(85)
        self.transitionBroadeningBox.setDecimals(1)
        self.transitionBroadeningBox.setRange(0.,1000.)
        self.transitionBroadeningBox.setSingleStep(1)
        self.transitionBroadeningBox.setSuffix(u' meV')
        self.transitionBroadeningBox.setReadOnly(True)
        self.transitionBroadeningBox.setStyleSheet('color:gray')
        self.connect(self.transitionBroadeningBox, 
                SIGNAL("valueChanged(double)"), 
                self.input_transitionBroadening)
        vBox1Grid.addWidget(self.transitionBroadeningBox, 13,0, 1,2, Qt.AlignCenter)

        vBox1subGrid1 = QGridLayout()

        vBox1subGrid1.addWidget(QLabel(
            u'<b><center><i>\u03C4<sub>upper</sub></i></center></b>'), 
            0,0, 1,1)
        self.tauUpperBox = QDoubleSpinBox()
        self.tauUpperBox.setDecimals(3)
        self.tauUpperBox.setRange(0.,99.)
        self.tauUpperBox.setSingleStep(1)
        self.tauUpperBox.setSuffix(u' ps')
        self.tauUpperBox.setReadOnly(True)
        self.tauUpperBox.setStyleSheet('color:gray')
        #self.tauUpperBox.setSizePolicy(QSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed))
        self.connect(self.tauUpperBox, SIGNAL("valueChanged(double)"), 
                self.input_tauUpper)
        vBox1subGrid1.addWidget(self.tauUpperBox, 1,0, 1,1)

        vBox1subGrid1.addWidget(QLabel(
            u'<b><center><i>\u03C4<sub>lower</sub></i></b></center></b>'), 
            0,1, 1,1)
        self.tauLowerBox = QDoubleSpinBox()
        self.tauLowerBox.setDecimals(3)
        self.tauLowerBox.setRange(0.,99.)
        self.tauLowerBox.setSingleStep(1)
        self.tauLowerBox.setSuffix(u' ps')
        self.tauLowerBox.setReadOnly(True)
        self.tauLowerBox.setStyleSheet('color:gray')
        #self.tauLowerBox.setSizePolicy(QSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed))
        self.connect(self.tauLowerBox, SIGNAL("valueChanged(double)"), 
                self.input_tauLower)
        vBox1subGrid1.addWidget(self.tauLowerBox, 1,1, 1,1)

        vBox1subGrid1.addWidget(QLabel(u'<b><center><i>\u03C4<sub>upper,lower</sub></i></b></center></b>'), 0,2, 1,1)
        self.tauUpperLowerBox = QDoubleSpinBox()
        self.tauUpperLowerBox.setDecimals(3)
        self.tauUpperLowerBox.setRange(0.,99.)
        self.tauUpperLowerBox.setSingleStep(1)
        self.tauUpperLowerBox.setSuffix(u' ps')
        self.tauUpperLowerBox.setReadOnly(True)
        self.tauUpperLowerBox.setStyleSheet('color:gray')
        #self.tauUpperLowerBox.setSizePolicy(QSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed))
        self.connect(self.tauUpperLowerBox, SIGNAL("valueChanged(double)"), 
                self.input_tauUpperLower)
        vBox1subGrid1.addWidget(self.tauUpperLowerBox, 1,2, 1,1)

        vBox1Grid.addLayout(vBox1subGrid1, 14,0, 1,2)

        vBox1Grid.addWidget(QLabel(
            u'<b><center>optical dipole</center></b>'), 15,0, 1,1)
        self.opticalDipoleBox = QDoubleSpinBox()
        self.opticalDipoleBox.setDecimals(1)
        self.opticalDipoleBox.setRange(0.,10000.)
        self.opticalDipoleBox.setSingleStep(1)
        self.opticalDipoleBox.setSuffix(u' \u212B')
        self.opticalDipoleBox.setReadOnly(True)
        self.opticalDipoleBox.setStyleSheet('color:gray')
        self.connect(self.opticalDipoleBox, 
                SIGNAL("valueChanged(double)"), 
                self.input_opticalDipole)
        vBox1Grid.addWidget(self.opticalDipoleBox, 16,0, 1,1)

        vBox1Grid.addWidget(QLabel(
            u'<center><b>Figure of Merit</b></center>'), 15,1, 1,1)
        self.FoMBox = QLineEdit()
        self.FoMBox.setMaximumWidth(150)
        self.FoMBox.setReadOnly(True)
        self.FoMBox.setStyleSheet('color:gray')
        vBox1Grid.addWidget(self.FoMBox, 16,1, 1,1)

        vBox1Grid.addItem(QSpacerItem(20,20), 17,0, 1,2)

        vBox1Grid.addWidget(QLabel(
            u'<center><b>Waveguide Facets</b></center>'), 18,0, 1,2)
        self.waveguideFacetsBox = QComboBox();
        self.waveguideFacetsBox.addItems(self.waveguideFacetsList)
        self.connect(self.waveguideFacetsBox, 
                SIGNAL("currentIndexChanged(const QString &)"), 
                self.input_waveguideFacets)
        vBox1Grid.addWidget(self.waveguideFacetsBox, 19,0, 1,2)

        vBox1Grid.addWidget(QLabel(
            u'<b><center>Waveguide<br>Length</center></b>'), 20,0, 1,1)
        self.waveguideLengthBox = QDoubleSpinBox()
        self.waveguideLengthBox.setDecimals(1)
        self.waveguideLengthBox.setRange(0.,20.)
        self.waveguideLengthBox.setSingleStep(1)
        self.waveguideLengthBox.setSuffix(u' mm')
        self.connect(self.waveguideLengthBox, 
                SIGNAL("valueChanged(double)"), 
                self.input_waveguideLength)
        vBox1Grid.addWidget(self.waveguideLengthBox, 21,0, 1,1)


        self.customFacetBoxLabel = QLabel(
                u'<b><center>Custom<br>Reflectivity</center></b>')
        self.customFacetBoxLabel.setStyleSheet('color:gray')
        vBox1Grid.addWidget(self.customFacetBoxLabel, 20,1, 1,1)
        self.customFacetBox = QDoubleSpinBox()
        self.customFacetBox.setDecimals(1)
        self.customFacetBox.setRange(0.,100.)
        self.customFacetBox.setSingleStep(1)
        self.customFacetBox.setSuffix(u'%')
        self.customFacetBox.setEnabled(False)
        self.connect(self.customFacetBox, SIGNAL("valueChanged(double)"), 
                self.input_customFacet)
        vBox1Grid.addWidget(self.customFacetBox, 21,1, 1,1)


        vBox1GridWidget = QWidget()
        vBox1GridWidget.setLayout(vBox1Grid)
        vBox1GridWidget.setContentsMargins(0,0,0,0)
        vBox1GridWidget.setMaximumWidth(235)
        vBox1 = QVBoxLayout()
        vBox1.addWidget(vBox1GridWidget)
        vBox1.setSpacing(0)
        vBox1.addStretch()


        #set up stratumTable
        self.stratumTable = QTableWidget()
        self.stratumTable.setSelectionBehavior(QTableWidget.SelectRows)
        self.stratumTable.setSelectionMode(QTableWidget.SingleSelection)
        self.stratumTable.setMinimumWidth(450)
        self.stratumTable.setMaximumWidth(450)
        if sys.platform == 'darwin':
            self.stratumTable.setMinimumWidth(550)
            self.stratumTable.setMaximumWidth(550)
        self.stratumTable.setMinimumHeight(450)
        self.stratumTable.setMaximumHeight(650)
        self.connect(self.stratumTable, 
                SIGNAL("itemChanged(QTableWidgetItem*)"),
                self.stratumTable_itemChanged)
        self.connect(self.stratumTable, SIGNAL("itemSelectionChanged()"),
                self.stratumTable_itemSelectionChanged)


        insertStratumAboveButton = QPushButton("Insert Stratum Above")
        self.connect(insertStratumAboveButton, SIGNAL("clicked()"), 
                self.insert_stratumAbove)
        insertStratumBelowButton = QPushButton("Insert Stratum Below")
        self.connect(insertStratumBelowButton, SIGNAL("clicked()"), 
                self.insert_stratumBelow)
        deleteStratumButton = QPushButton("Delete Stratum")
        self.connect(deleteStratumButton, SIGNAL("clicked()"), self.delete_stratum)

        #vBox2
        vBox2Grid = QGridLayout()
        vBox2Grid.addWidget(insertStratumAboveButton, 1,0, 1,1)
        vBox2Grid.addWidget(insertStratumBelowButton, 1,1, 1,1)
        vBox2Grid.addWidget(deleteStratumButton, 1,2, 1,1)
        vBox2Grid.addWidget(self.stratumTable, 2,0, 1,3)

        #Optimization
        optiFrameLayout = QGridLayout()

        self.opti1DChoiceBox = QComboBox()
        self.opti1DChoiceBox.addItems(['Thickness','Doping'])
        self.connect(self.opti1DChoiceBox, 
                SIGNAL("currentIndexChanged(const QString &)"), 
                self.input_opti1DChoice)
        optiFrameLayout.addWidget(self.opti1DChoiceBox, 1,0, 1,1)

        opti1DLayerBoxLabel = QLabel('<b><center>1<sup>st</sup> Dimension<br>'
                'Strata Number(s)</center></b>')
        opti1DLayerBoxLabel.setToolTip('Ex: 6,8')
        optiFrameLayout.addWidget(opti1DLayerBoxLabel, 0,1, 1,1)
        self.opti1DLayerBox = QLineEdit()
        self.connect(self.opti1DLayerBox, SIGNAL('editingFinished()'), 
                self.input_opti1DLayer)
        self.opti1DLayerBox.setToolTip('Ex: 6,8')
        optiFrameLayout.addWidget(self.opti1DLayerBox, 1,1, 1,1)

        opti1DRangeBoxLabel = QLabel('<b><center>Optimization<br>Range</center></b>')
        opti1DRangeBoxLabel.setToolTip('Ex: 1:0.1:3')
        optiFrameLayout.addWidget(opti1DRangeBoxLabel, 0,2, 1,1)
        self.opti1DRangeBox = QLineEdit()
        self.opti1DRangeBox.setToolTip('Ex: 1:0.1:3')
        self.connect(self.opti1DRangeBox, SIGNAL('editingFinished()'), 
                self.input_opti1DRange)
        optiFrameLayout.addWidget(self.opti1DRangeBox, 1,2, 1,1)

        self.opti1DRunButton = QPushButton('Optimize 1D')
        self.connect(self.opti1DRunButton, SIGNAL('clicked(bool)'), self.run_opti1D)
        optiFrameLayout.addWidget(self.opti1DRunButton, 1,3, 1,1)

        self.opti2DChoiceBox = QComboBox()
        self.opti2DChoiceBox.addItems(['Thickness','Doping'])
        self.connect(self.opti2DChoiceBox, 
                SIGNAL("currentIndexChanged(const QString &)"), 
                self.input_opti2DChoice)
        optiFrameLayout.addWidget(self.opti2DChoiceBox, 3,0, 1,1)

        opti2DLayerBoxLabel = QLabel('<b><center>2<sup>nd</sup> Dimension<br>'
                'Strata Number(s)</center></b>')
        opti2DLayerBoxLabel.setToolTip('Ex: 2 5 7')
        optiFrameLayout.addWidget(opti2DLayerBoxLabel, 2,1, 1,1)
        self.opti2DLayerBox = QLineEdit()
        self.opti2DLayerBox.setToolTip('Ex: 2 5 7')
        self.connect(self.opti2DLayerBox, SIGNAL('editingFinished()'), 
                self.input_opti2DLayer)
        optiFrameLayout.addWidget(self.opti2DLayerBox, 3,1, 1,1)

        opti2DRangeBoxLabel = QLabel('<b><center>Optimization<br>Range</center></b>')
        opti2DRangeBoxLabel.setToolTip('Ex: 1:5')
        optiFrameLayout.addWidget(opti2DRangeBoxLabel, 2,2, 1,1)
        self.opti2DRangeBox = QLineEdit()
        self.opti2DRangeBox.setToolTip('Ex: 1:5')
        self.connect(self.opti2DRangeBox, SIGNAL('editingFinished()'), 
                self.input_opti2DRange)
        optiFrameLayout.addWidget(self.opti2DRangeBox, 3,2, 1,1)

        self.opti2DRunButton = QPushButton('Optimize 2D')
        self.connect(self.opti2DRunButton, SIGNAL('clicked(bool)'), self.run_opti2D)
        optiFrameLayout.addWidget(self.opti2DRunButton, 3,3, 1,1)

        self.optiFrame = QGroupBox('Optimization')
        self.optiFrame.setMaximumWidth(450)
        self.optiFrame.setMinimumWidth(450)
        self.optiFrame.setLayout(optiFrameLayout)
        vBox2Grid.addWidget(self.optiFrame, 3,0, 1,3)

        vBox2 = QVBoxLayout()
        vBox2.addLayout(vBox2Grid)
        vBox2.addStretch()



        #vBox3
        self.plotModeButton = QPushButton("Plot Mode")
        self.connect(self.plotModeButton, SIGNAL("clicked()"), self.solve_mode)
        vBox3 = QVBoxLayout()
        vBox3.addWidget(self.plotModeButton)

        vBox3.addWidget(QLabel(u'<center><b><i>\u03B2<sub>eff</sub></i></b></center>'))
        self.betaEffBox = QLineEdit()
        self.betaEffBox.setMaximumWidth(150)
        self.betaEffBox.setEnabled(False)
        vBox3.addWidget(self.betaEffBox)

        self.modeCalculationsBox = QTextEdit('')
        self.modeCalculationsBox.setReadOnly(True)
        self.modeCalculationsBox.setSizePolicy(QSizePolicy(
            QSizePolicy.Fixed,QSizePolicy.Fixed))
        self.modeCalculationsBox.setMaximumHeight(175)
        self.modeCalculationsBox.setMaximumWidth(150)
        vBox3.addWidget(self.modeCalculationsBox)

        vBox3.addStretch()


        #vBox4

        #set up opticalCanvas for stratum / mode plot
        self.opticalCanvas = Qwt.QwtPlot(self)
        self.opticalCanvas.setCanvasBackground(Qt.white)
        self.opticalCanvas.canvas().setCursor(Qt.ArrowCursor)

        #optical optimization canvas
        self.optimization1DCanvas = Qwt.QwtPlot(self)
        self.optimization1DCanvas.setCanvasBackground(Qt.white)
        self.optimization1DCanvas.canvas().setCursor(Qt.ArrowCursor)
        self.optimization1DCanvas.setVisible(False)

        #2D optical optimization canvas
        #optimization2DFig = Figure((5.0, 4.0), dpi=dpi)
        self.optimization2DFig = Figure()
        self.optimization2DCanvas = FigureCanvas(self.optimization2DFig)
        #self.optimization2DAxes = self.optimization2DFig.add_subplot(111, projection='3d')
        margins = [0.05,0.05,0.95,0.95]
        self.optimization2DAxes = self.optimization2DFig.add_axes(
                margins, projection='3d')
        self.optimization2DAxes.autoscale(enable=True, axis='both', tight=True)
        #get the background color of the central widget
        #bgColor = self.mainTabWidget.palette().brush(QPalette.Window).color().name()
        bgColorRed = self.mainTabWidget.palette().brush(QPalette.Window).color().red()
        bgColorBlue = self.mainTabWidget.palette().brush(QPalette.Window).color().blue()
        bgColorGreen = self.mainTabWidget.palette().brush(QPalette.Window).color().green()
        self.bgColor = (bgColorRed/255.0, bgColorGreen/255.0, bgColorBlue/255.0, 1)
        self.optimization2DAxes.patch.set_color(self.bgColor)
        self.optimization2DFig.patch.set_color(self.bgColor)
        self.optimization2DCanvas.setVisible(False)



        vBox4 = QVBoxLayout()
        vBox4.addWidget(self.opticalCanvas)
        vBox4.addWidget(self.optimization1DCanvas)
        vBox4.addWidget(self.optimization2DCanvas)

        opticalLayout = QHBoxLayout()
        opticalLayout.addLayout(vBox1)
        opticalLayout.addLayout(vBox2)
        opticalLayout.addLayout(vBox3)
        opticalLayout.addLayout(vBox4)  



        self.opticalWidget = QWidget()
        self.opticalWidget.setLayout(opticalLayout)
        self.opticalWidget.setAutoFillBackground(True)
        self.opticalWidget.setBackgroundRole(QPalette.Window)        

        # ###############################
        #
        # Thermal Tab
        #
        # ###############################

#        vBox1 = QVBoxLayout()

#        thermalTable = QTableWidget()
#        thermalTable.setSelectionBehavior(QTableWidget.SelectRows)
#        thermalTable.setSelectionMode(QTableWidget.SingleSelection)
#        thermalTable.setMaximumWidth(380)
#        thermalTable.setMinimumWidth(380)
#        self.connect(thermalTable,SIGNAL("itemChanged(QTableWidgetItem*)"),self.stratumTable_itemChanged)
#        self.connect(thermalTable,SIGNAL("itemSelectionChanged()"),self.stratumTable_itemSelectionChanged)
#        vBox1.addWidget(thermalTable)

#        thermalWidget = QWidget()
#        thermalWidget.setLayout(vBox1)
#        thermalWidget.setAutoFillBackground(True)
#        thermalWidget.setBackgroundRole(QPalette.Window)


        self.mainTabWidget.addTab(self.quantumWidget, 'Quantum')
        self.mainTabWidget.addTab(self.opticalWidget, 'Optical')
#        self.mainTabWidget.addTab(thermalWidget, 'Thermal')
        self.connect(self.mainTabWidget, SIGNAL('currentChanged(int)'), 
                self.change_main_tab)

        self.setCentralWidget(self.mainTabWidget)

        self.layerTable.selectRow(0)
        self.layerTable.setFocus()




#===============================================================================
# Optical Tab Input Controls
#===============================================================================

    def update_stratum_inputBoxes(self):
        self.wavelengthBox.setValue(self.strata.wavelength)
        self.operatingFieldBox.setValue(self.strata.operatingField)
        self.ACPeriodLengthBox.setValue(self.strata.Lp)
        self.ACPeriodsBox.setValue(self.strata.Np)
        self.OperatingVoltageBox.setText('{0:.1f} V'.format(
                    self.strata.Np*self.strata.operatingField/self.strata.Lp))
        self.aCoreBox.setText(
                '{0:.3f} cm^-1'.format(self.strata.aCore))
        self.nCoreBox.setText(
                '{0.real:2.3f}+{0.imag:1.3e}j'.format(self.strata.nCore))
        self.transitionBroadeningBox.setValue(
                self.strata.transitionBroadening * 1000) #display in meV
        self.tauUpperBox.setValue(self.strata.tauUpper)
        self.tauLowerBox.setValue(self.strata.tauLower)
        self.tauUpperLowerBox.setValue(self.strata.tauUpperLower)
        self.opticalDipoleBox.setValue(self.strata.opticalDipole)
        self.FoMBox.setText(u'{0:4.0f} ps \u212B^2'.format(self.strata.FoM))
        self.waveguideFacetsBox.setCurrentIndex(
                self.waveguideFacetsList.index(self.strata.waveguideFacets))
        self.waveguideLengthBox.setValue(self.strata.waveguideLength)
        self.customFacetBox.setValue(self.strata.customFacet * 100) #display in percent

        self.strata.updateFacets()

    def update_modeCalculations_box(self):

        self.strata.calculate_performance_parameters()
        reportString = (u"\u0393: <b>%3.1f%%</b><br>"
                u"<i>\u03B1<sub>wg</sub></i> : %3.1f cm<sup>-1</sup><br>"
                u"<i>\u03B1<sub>mirror</sub></i> : %3.1f cm<sup>-1</sup><br>"
                u"gain: %3.3f cm/A<br>"
                u"<i>J<sub>th0</sub></i> : <b>%3.3f kA/cm<sup>2</sup></b><br>"
                u"<i>I<sub>th0</sub></i> : %5.1f mA<br>"
                u"<i>V<sub>op</sub></i> : %3.1f V<br>"
                u"<i>\u03B7<sub>voltage</sub></i> : %3.1f%%<br>"
                u"<i>\u03B7<sub>extraction</sub></i> : %3.1f%%<br>"
                u"<i>\u03B7<sub>inversion</sub></i> : %3.1f%%<br>"
                u"<i>\u03B7<sub>modal</sub></i> : %3.1f%%<br>")%(
                        self.strata.confinementFactor*100, 
                        self.strata.waveguideLoss, 
                        self.strata.mirrorLoss,
                        self.strata.gain, 
                        self.strata.Jth0, 
                        self.strata.Ith0*1000, 
                        self.strata.operatingVoltage, 
                        self.strata.voltageEfficiency*100,
                        self.strata.extractionEfficiency*100,
                        self.strata.inversionEfficiency*100, 
                        self.strata.modalEfficiency*100)

        #  reportString = u""

        #  #confinement factor
        #  reportString += u"\u0393: <b>{0:3.1f}%</b><br>".format(self.strata.confinementFactor*100)
        #  #waveguide loss
        #  reportString += u"<i>\u03B1<sub>wg</sub></i> : {0:3.1f} cm<sup>-1</sup><br>".format(self.strata.waveguideLoss)
        #  #mirror loss
        #  reportString += u"<i>\u03B1<sub>mirror</sub></i> : {0:3.1f} cm<sup>-1</sup><br>".format(self.strata.mirrorLoss)
        #  #gain
        #  reportString += u"gain: {0:3.3f} cm/A<br>".format(self.strata.gain)
        #  #Jth0
        #  reportString += u"<i>J<sub>th0</sub></i> : <b>{0:3.3f} kA/cm<sup>2</sup></b><br>".format(self.strata.Jth0)
        #  #Ith0
        #  reportString += u"<i>I<sub>th0</sub></i> : {0:5.1f} mA<br>".format(self.strata.Ith0*1000)

        #  #Voltage
        #  reportString += u"<i>V<sub>op</sub></i> : {0:3.1f} V<br>".format(self.strata.operatingVoltage)
        #  #Voltage Efficiency
        #  reportString += u"<i>\u03B7<sub>voltage</sub></i> : {0:3.1f}%<br>".format(self.strata.voltageEfficiency*100)
        #  #Extraction Efficiency
        #  reportString += u"<i>\u03B7<sub>extraction</sub></i> : {0:3.1f}%<br>".format(self.strata.extractionEfficiency*100)
        #  #Inversion Efficiency
        #  reportString += u"<i>\u03B7<sub>inversion</sub></i> : {0:3.1f}%<br>".format(self.strata.inversionEfficiency*100)
        #  #Modal Efficiency
        #  reportString += u"<i>\u03B7<sub>modal</sub></i> : {0:3.1f}%<br>".format(self.strata.modalEfficiency*100)

        self.modeCalculationsBox.setText(reportString)

    def edit_optical_parameters(self, toggleState):
        if toggleState == True:
            self.wavelengthBox.setReadOnly(False)
            self.wavelengthBox.setStyleSheet('color:black')
            self.operatingFieldBox.setReadOnly(False)
            self.operatingFieldBox.setStyleSheet('color:black')
            self.ACPeriodLengthBox.setReadOnly(False)
            self.ACPeriodLengthBox.setStyleSheet('color:black')
            self.aCoreBox.setReadOnly(False)
            self.aCoreBox.setStyleSheet('color:black')
            self.tauUpperBox.setReadOnly(False)
            self.tauUpperBox.setStyleSheet('color:black')
            self.tauUpperLowerBox.setReadOnly(False)
            self.tauUpperLowerBox.setStyleSheet('color:black')
            self.tauLowerBox.setReadOnly(False)
            self.tauLowerBox.setStyleSheet('color:black')
            self.opticalDipoleBox.setReadOnly(False)
            self.opticalDipoleBox.setStyleSheet('color:black')
            self.transitionBroadeningBox.setReadOnly(False)
            self.transitionBroadeningBox.setStyleSheet('color:black')
        else:
            self.wavelengthBox.setReadOnly(True)
            self.wavelengthBox.setStyleSheet('color:gray')
            self.operatingFieldBox.setReadOnly(True)
            self.operatingFieldBox.setStyleSheet('color:gray')
            self.ACPeriodLengthBox.setReadOnly(True)
            self.ACPeriodLengthBox.setStyleSheet('color:gray')
            self.aCoreBox.setReadOnly(True)
            self.aCoreBox.setStyleSheet('color:gray')
            self.tauUpperBox.setReadOnly(True)
            self.tauUpperBox.setStyleSheet('color:gray')
            self.tauLowerBox.setReadOnly(True)
            self.tauLowerBox.setStyleSheet('color:gray')
            self.tauUpperLowerBox.setReadOnly(True)
            self.tauUpperLowerBox.setStyleSheet('color:gray')
            self.opticalDipoleBox.setReadOnly(True)
            self.opticalDipoleBox.setStyleSheet('color:gray')
            self.transitionBroadeningBox.setReadOnly(True)
            self.transitionBroadeningBox.setStyleSheet('color:gray')

    def input_wavelength(self, value):
        self.strata.wavelength = value

        self.dirty = True
        self.update_windowTitle()       
        self.update_stratum_inputBoxes()
        self.stratumTable_refresh()

    def input_operatingField(self, value):
        self.strata.operatingField = value

        self.dirty = True
        self.update_windowTitle()       
        self.update_stratum_inputBoxes()
        self.stratumTable_refresh()

    def input_ACPeriodLength(self, value):
        self.strata.Lp = value

        self.dirty = True
        self.update_windowTitle()       
        self.update_stratum_inputBoxes()
        self.stratumTable_refresh()

    def input_ACPeriods(self, value):
        self.strata.Np = value

        self.dirty = True
        self.update_windowTitle()       
        self.update_stratum_inputBoxes()
        self.stratumTable_refresh()

    def input_aCore(self):
        initialText = unicode(self.aCoreBox.text())
        txt = initialText.split()[0]
        try:
            value = float(txt)
            self.strata.aCore = value
            kCore = 1/(4*pi) * self.strata.aCore * self.strata.wavelength*1e-4 
            # See Def of acore
            # 1e-4: aCore in cm-1, wl in um
            self.strata.nCore = self.qclayers.get_nCore(self.strata.wavelength) \
                    + 1j*kCore


            self.dirty = True
            self.update_windowTitle()       
            self.update_stratum_inputBoxes()
            self.stratumTable_refresh()
        except ValueError:
            self.aCore.setText(initialText)            

    def input_transitionBroadening(self, value):
        self.strata.transitionBroadening = value / 1000

        self.dirty = True
        self.update_windowTitle()       
        self.update_stratum_inputBoxes()
        self.stratumTable_refresh()

    def input_tauUpper(self, value):
        self.strata.tauUpper = value
        self.strata.FoM = self.strata.opticalDipole**2 * self.strata.tauUpper * (1- self.strata.tauLower/self.strata.tauUpperLower)

        self.dirty = True
        self.update_windowTitle()       
        self.update_stratum_inputBoxes()
        self.stratumTable_refresh()

    def input_tauLower(self, value):
        self.strata.tauLower = value
        self.strata.FoM = self.strata.opticalDipole**2 * self.strata.tauUpper * (1- self.strata.tauLower/self.strata.tauUpperLower)

        self.dirty = True
        self.update_windowTitle()       
        self.update_stratum_inputBoxes()
        self.stratumTable_refresh()

    def input_tauUpperLower(self, value):
        self.strata.tauUpperLower = value
        self.strata.FoM = self.strata.opticalDipole**2 * self.strata.tauUpper * (1- self.strata.tauLower/self.strata.tauUpperLower)

        self.dirty = True
        self.update_windowTitle()       
        self.update_stratum_inputBoxes()
        self.stratumTable_refresh()

    def input_opticalDipole(self, value):
        self.strata.opticalDipole = value
        self.strata.FoM = self.strata.opticalDipole**2 * self.strata.tauUpper * (1- self.strata.tauLower/self.strata.tauUpperLower)

        self.dirty = True
        self.update_windowTitle()       
        self.update_stratum_inputBoxes()
        self.stratumTable_refresh()

    def input_waveguideFacets(self, selection):
        self.strata.waveguideFacets = selection
        if selection == 'as-cleaved + as-cleaved':
            self.customFacetBoxLabel.setStyleSheet('color:gray')
            self.customFacetBox.setEnabled(False)
        elif selection == 'as-cleaved + perfect HR':
            self.customFacetBoxLabel.setStyleSheet('color:gray')
            self.customFacetBox.setEnabled(False)
        elif selection == 'as-cleaved + perfect AR':
            self.customFacetBoxLabel.setStyleSheet('color:gray')
            self.customFacetBox.setEnabled(False)
        elif selection == 'perfect AR + perfect HR':
            self.customFacetBoxLabel.setStyleSheet('color:gray')
            self.customFacetBox.setEnabled(False)
        elif selection == 'custom coating + as-cleaved':
            self.customFacetBoxLabel.setStyleSheet('color:black')
            self.customFacetBox.setEnabled(True)
        elif selection == 'custom coating + perfect HR':
            self.customFacetBoxLabel.setStyleSheet('color:black')
            self.customFacetBox.setEnabled(True)
        elif selection == 'custom coating + perfect AR':
            self.customFacetBoxLabel.setStyleSheet('color:black')
            self.customFacetBox.setEnabled(True)

        self.dirty = True
        self.update_windowTitle()       
        self.update_stratum_inputBoxes()
        self.stratumTable_refresh()

    def input_waveguideLength(self, value):
        self.strata.waveguideLength = value

        self.dirty = True
        self.update_windowTitle()       
        self.update_stratum_inputBoxes()
        self.stratumTable_refresh()

    def input_customFacet(self, value):
        self.strata.customFacet = value / 100.0

        self.dirty = True
        self.update_windowTitle()       
        self.update_stratum_inputBoxes()
        self.stratumTable_refresh()

    def input_opti1DChoice(self, selectionString):
        pass

    def input_opti1DLayer(self):
        pass

    def input_opti1DRange(self):
        pass

    def input_opti2DChoice(self, selectionString):
        pass

    def input_opti2DLayer(self):
        pass

    def input_opti2DRange(self):
        pass




#===============================================================================
# Optical Tab Strata Table Control
#===============================================================================

    def stratumTable_refresh(self):
        #calculate index for each layer
        self.strata.populate_rIndexes()

        #set properties for Active Core Layer
        for q in xrange(self.strata.stratumDopings.size):
            if self.strata.stratumMaterials[q] == 'Active Core':
                self.strata.stratumThicknesses[q] = \
                        self.strata.Np * self.strata.Lp * 1e-4
                self.strata.stratumDopings[q] = self.strata.nD
                self.strata.stratumRIndexes[q] = self.strata.nCore

        #update table
        self.stratumTable.clear()
        self.stratumTable.setColumnCount(6)
        self.stratumTable.setRowCount(self.strata.stratumDopings.size) #need to change
        self.stratumTable.setHorizontalHeaderLabels(
                ['Material', 'Mole Frac', 'Thickness', 'Doping', 
                    'Refractive Index', 'Loss'])
        vertLabels = []
        for n in xrange(self.strata.stratumDopings.size):
            vertLabels.append(str(n+1))
        self.stratumTable.setVerticalHeaderLabels(vertLabels)

        for q in xrange(self.strata.stratumDopings.size):
            #Stratum Material Setup
            materialWidget = QComboBox()
            materialWidget.addItems(self.stratumMaterialsList)
            materialWidget.setCurrentIndex(
                    self.stratumMaterialsList.index(self.strata.stratumMaterials[q]))
            self.connect(materialWidget, SIGNAL("currentIndexChanged(int)"), 
                    partial(self.stratumTable_materialChanged, q))
            self.stratumTable.setCellWidget(q, 0, materialWidget)

            #Stratum Composition Setup
            composition = QTableWidgetItem()
            if self.strata.stratumMaterials[q] not in self.strata.needsCompositionList:
                composition.setFlags(Qt.NoItemFlags)
            else:
                composition.setData(0,'{0:3.3f}'.format(
                    self.strata.stratumCompositions[q]))
                composition.setTextAlignment(Qt.AlignCenter)
            self.stratumTable.setItem(q, 1, composition)

            #Stratum Thickness Setup
            thickness = QTableWidgetItem(unicode(self.strata.stratumThicknesses[q]))
            thickness.setTextAlignment(Qt.AlignCenter)
            self.stratumTable.setItem(q, 2, thickness)
            if self.strata.stratumMaterials[q] == 'Active Core':
                thickness.setFlags(Qt.NoItemFlags)

            #Stratum Doping Setup
            doping = QTableWidgetItem()
            if self.strata.stratumMaterials[q] in self.strata.notDopableList:
                doping.setFlags(Qt.NoItemFlags)
            else:
                doping.setData(0,'{0:3.2f}'.format(self.strata.stratumDopings[q]))
                doping.setTextAlignment(Qt.AlignCenter)
                if self.strata.stratumMaterials[q] == 'Active Core':
                    doping.setFlags(Qt.NoItemFlags)
            self.stratumTable.setItem(q, 3, doping)

            #Stratum RIndex Setup
            rIndex = QTableWidgetItem(
                    '{0.real:2.3f}+{0.imag:1.3e}j'.format(
                        self.strata.stratumRIndexes[q]))
            rIndex.setTextAlignment(Qt.AlignCenter)
            rIndex.setFlags(Qt.NoItemFlags)
            self.stratumTable.setItem(q, 4, rIndex)

            #Stratum Loss Setup
            loss = self.strata.stratumRIndexes[q].imag*4*pi/self.strata.wavelength/1e-4
            alpha = QTableWidgetItem('{0:3.2f}'.format(loss))
            alpha.setTextAlignment(Qt.AlignCenter)
            alpha.setFlags(Qt.NoItemFlags)
            self.stratumTable.setItem(q, 5, alpha)

        self.stratumTable.resizeColumnsToContents()

        self.update_opticalCanvas()

    def stratumTable_itemChanged(self, item):
        column = self.stratumTable.currentColumn()
        row = self.stratumTable.currentRow()
        if column == -1: #column == -1 on GUI initialization
            return
        elif column == 0:
            return
        elif column == 1:
            xFrac = float(item.text())
            if xFrac < 0 or xFrac > 1:
                QMessageBox.warning(self,
                        'ErwinJr Error',
                        'Mole Fraction must be between 0 and 1')
            else:
                self.strata.stratumCompositions[row] = xFrac
        elif column == 2:
            self.strata.stratumThicknesses[row] = float(item.text())
        elif column == 3:
            self.strata.stratumDopings[row] = float(item.text())

        self.stratumTable_refresh()
        self.stratumTable.selectRow(row)

        self.dirty = True
        self.update_windowTitle()   

    def stratumTable_itemSelectionChanged(self):
        self.strata.stratumSelected = self.stratumTable.currentRow()
        if self.strata.stratumSelected >= 0 and \
                self.strata.stratumSelected < self.qclayers.layerWidth.size:
            self.strata.populate_x()
            self.update_opticalCanvas()

    def stratumTable_materialChanged(self, row, selection):
        self.strata.stratumMaterials[row] = self.stratumMaterialsList[selection]

        self.stratumTable_refresh()
        self.stratumTable.selectRow(row)

        self.dirty = True
        self.update_windowTitle()  

    def insert_stratumAbove(self):
        row = self.stratumTable.currentRow()
        if row == -1:
            return

        #  if row == 0:
            #  self.strata.stratumMaterials.insert(row, self.strata.stratumMaterials[row])
            #  self.strata.stratumCompositions = np.hstack([self.strata.stratumCompositions[row], self.strata.stratumCompositions[row:,]])
            #  self.strata.stratumThicknesses = np.hstack([self.strata.stratumThicknesses[row], self.strata.stratumThicknesses[row:,]])
            #  self.strata.stratumDopings = np.hstack([self.strata.stratumDopings[row], self.strata.stratumDopings[row:,]])
            #  self.strata.stratumRIndexes = np.hstack([self.strata.stratumRIndexes[row], self.strata.stratumRIndexes[row:,]])

        #  else:
            #  self.strata.stratumMaterials.insert(row, self.strata.stratumMaterials[row])
            #  self.strata.stratumCompositions = np.hstack([self.strata.stratumCompositions[0:row], self.strata.stratumCompositions[row], self.strata.stratumCompositions[row:,]])
            #  self.strata.stratumThicknesses = np.hstack([self.strata.stratumThicknesses[0:row], self.strata.stratumThicknesses[row], self.strata.stratumThicknesses[row:,]])
            #  self.strata.stratumDopings = np.hstack([self.strata.stratumDopings[0:row], self.strata.stratumDopings[row], self.strata.stratumDopings[row:,]])
            #  self.strata.stratumRIndexes = np.hstack([self.strata.stratumRIndexes[0:row], self.strata.stratumRIndexes[row], self.strata.stratumRIndexes[row:,]])

        self.strata.stratumMaterials.insert(row, self.strata.stratumMaterials[row])

        self.strata.stratumCompositions = np.insert(
                self.strata.stratumCompositions, row, 
                self.strata.stratumCompositions[row])
        self.strata.stratumThicknesses = np.insert(
                self.strata.stratumThicknesses, row, 
                self.strata.stratumThicknesses[row])
        self.strata.stratumDopings = np.insert(
                self.strata.stratumDopings, row, 
                self.strata.stratumDopings[row])
        self.strata.stratumRIndexes = np.insert(
                self.strata.stratumRIndexes, row, 
                self.strata.stratumRIndexes[row])

        self.stratumTable_refresh()
        self.stratumTable.selectRow(row)
        self.stratumTable.setFocus()

        self.dirty = True
        self.update_windowTitle()

    def insert_stratumBelow(self):
        row = self.stratumTable.currentRow()
        if row == -1:
            return

        #  if row == self.strata.stratumDopings.size-1:
            #  self.strata.stratumMaterials.insert(row, self.strata.stratumMaterials[row])
            #  self.strata.stratumCompositions = np.hstack([self.strata.stratumCompositions[:], self.strata.stratumCompositions[row]])
            #  self.strata.stratumThicknesses = np.hstack([self.strata.stratumThicknesses[:], self.strata.stratumThicknesses[row]])
            #  self.strata.stratumDopings = np.hstack([self.strata.stratumDopings[:], self.strata.stratumDopings[row]])
            #  self.strata.stratumRIndexes = np.hstack([self.strata.stratumRIndexes[:], self.strata.stratumRIndexes[row]])

        #  else:
            #  self.strata.stratumMaterials.insert(row, self.strata.stratumMaterials[row])
            #  self.strata.stratumCompositions = np.hstack([self.strata.stratumCompositions[0:row+1], self.strata.stratumCompositions[row], self.strata.stratumCompositions[row+1:,]])
            #  self.strata.stratumThicknesses = np.hstack([self.strata.stratumThicknesses[0:row+1], self.strata.stratumThicknesses[row], self.strata.stratumThicknesses[row+1:,]])
            #  self.strata.stratumDopings = np.hstack([self.strata.stratumDopings[0:row+1], self.strata.stratumDopings[row], self.strata.stratumDopings[row+1:,]])
            #  self.strata.stratumRIndexes = np.hstack([self.strata.stratumRIndexes[0:row+1], self.strata.stratumRIndexes[row], self.strata.stratumRIndexes[row+1:,]])

        self.strata.stratumMaterials.insert(row, self.strata.stratumMaterials[row])
        self.strata.stratumCompositions = np.insert(
                self.strata.stratumCompositions, row+1, 
                self.strata.stratumCompositions[row])
        self.strata.stratumThicknesses = np.insert(
                self.strata.stratumThicknesses, row+1, 
                self.strata.stratumThicknesses[row])
        self.strata.stratumDopings = np.insert(
                self.strata.stratumDopings, row+1, 
                self.strata.stratumDopings[row])
        self.strata.stratumRIndexes = np.insert(
                self.strata.stratumRIndexes, row+1, 
                self.strata.stratumRIndexes[row])

        self.stratumTable_refresh()
        self.stratumTable.selectRow(row+1)
        self.stratumTable.setFocus()

        self.dirty = True
        self.update_windowTitle()

    def delete_stratum(self):
        #don't delete last stratum
        if self.strata.stratumDopings.size == 1:
            return

        row = self.stratumTable.currentRow()
        if row == -1:
            return

        self.strata.stratumMaterials.pop(row)
        #  self.strata.stratumCompositions = np.hstack([self.strata.stratumCompositions[0:row], self.strata.stratumCompositions[row+1:,]])
        #  self.strata.stratumThicknesses = np.hstack([self.strata.stratumThicknesses[0:row], self.strata.stratumThicknesses[row+1:,]])
        #  self.strata.stratumDopings = np.hstack([self.strata.stratumDopings[0:row], self.strata.stratumDopings[row+1:,]])
        #  self.strata.stratumRIndexes = np.hstack([self.strata.stratumRIndexes[0:row], self.strata.stratumRIndexes[row+1:,]])
        self.strata.stratumCompositions = np.delete(
                self.strata.stratumCompositions, row)
        self.strata.stratumThicknesses = np.delete(
                self.strata.stratumThicknesses, row)
        self.strata.stratumDopings = np.delete(
                self.strata.stratumDopings, row)
        self.strata.stratumRIndexes = np.delete(
                self.strata.stratumRIndexes, row)

        #if current row was last row (now deleted)
        if row+1 > self.strata.stratumThicknesses.size:
            self.strata.stratumSelected -= 1
            row -= 1

        self.stratumTable.selectRow(row)
        self.stratumTable_refresh()
        self.stratumTable.selectRow(row)
        self.stratumTable.setFocus()

        self.dirty = True
        self.update_windowTitle()        




#===============================================================================
# Optical Tab Plotting and Plot Control
#===============================================================================

    def update_opticalCanvas(self):
        self.strata.populate_x()

        self.opticalCanvas.clear()

        self.curvenR = Qwt.QwtPlotCurve()
        self.curvenR.setData(self.strata.xPoints,self.strata.xn.real)
        self.curvenR.setPen(QPen(Qt.black, 1.5))
        if settings.antialiased:
            self.curvenR.setRenderHint(Qwt.QwtPlotItem.RenderAntialiased)
        self.curvenR.attach(self.opticalCanvas)
        self.opticalCanvas.setAxisTitle(Qwt.QwtPlot.yLeft, 'Refractive Index')

        if self.strata.stratumSelected >= 0 and \
                self.strata.stratumSelected < self.strata.stratumThicknesses.size:
            mask = ~np.isnan(self.strata.xStratumSelected)
            self.stratumSelection = SupportClasses.MaskedCurve(
                    self.strata.xPoints, self.strata.xStratumSelected,
                    mask)
            self.stratumSelection.setPen(QPen(Qt.blue, 2))
            if settings.antialiased:
                self.stratumSelection.setRenderHint(Qwt.QwtPlotItem.RenderAntialiased)
            self.stratumSelection.attach(self.opticalCanvas)

        #plot Intensity
        if hasattr(self.strata,'xI'):
            self.curvexI = Qwt.QwtPlotCurve()
            self.curvexI.setData(self.strata.xPoints, 
                    self.strata.xI*self.strata.stratumRIndexes.real.max())
            self.curvexI.setPen(QPen(Qt.red, 1.5))
            if settings.antialiased:
                self.curvexI.setRenderHint(Qwt.QwtPlotItem.RenderAntialiased)
            self.curvexI.attach(self.opticalCanvas)
            self.opticalCanvas.setAxisTitle(Qwt.QwtPlot.yLeft, 
                    'Refractive Index, Mode Intensity')

        self.opticalCanvas.setAxisTitle(Qwt.QwtPlot.xBottom, u'Position (\u03BCm)')
        self.opticalCanvas.replot()

    def solve_mode(self):
        betaInit = self.betaEffBox.text()
        if betaInit == '':
            betaInit = None
        else:
            betaInit = complex(str(betaInit))
        self.strata.beta = self.strata.beta_find(betaInit)
        self.betaEffBox.setText(
                '{0.real:2.3f}+{0.imag:1.3e}j'.format(self.strata.beta))
        self.strata.mode_plot()
        self.update_modeCalculations_box()
        self.update_opticalCanvas()

    def run_opti1D(self):
        #get initial parameters
        try:
            optiType1D  = self.opti1DChoiceBox.currentText()
            strata1D    = np.array(SupportClasses.matlab_range(
                self.opti1DLayerBox.text()), dtype=int)
            strata1D   -= 1 #indexing starts at 0
            optiRange1D = np.array(SupportClasses.matlab_range(
                self.opti1DRangeBox.text()))
        except ValueError:
            QMessageBox.warning(self,"ErwinJr Error", "Invalid entry.")
            return

        #set up GUI
        self.optiFrame.setEnabled(False)
        self.plotModeButton.setEnabled(False)

        Jth0Array = np.zeros(optiRange1D.size)*np.NaN
        ylabel = '<i>J<sub>th0</sub></i>'

        stratumThicknessesInitial = self.strata.stratumThicknesses.copy()
        stratumDopingsInitial = self.strata.stratumDopings.copy()

        for q, rangeValue in enumerate(optiRange1D):
            if optiType1D == 'Thickness':
                self.strata.stratumThicknesses[strata1D] = rangeValue
                xlabel = u'Thickness (\u03BCm)'
            elif optiType1D == 'Doping':
                self.strata.stratumDopings[strata1D] = rangeValue
                xlabel = 'Doping (x10<sup>17</sup> cm<sup>-3</sup>)'
            elif optiType1D == 'Active Core Periods':
                pass
            elif optiTyp1D == 'deltaE':
                pass
            elif optiTyp1D == 'E3c':
                pass
            elif optiTyp1D == 'Custom Facet':
                pass
            elif optiTyp1D == 'Waveguide Length':
                pass
            elif optiTyp1D == 'Ridge Width':
                pass
            elif optiType1D == 'Tsink':
                pass
            self.stratumTable_refresh()
            self.update_stratum_inputBoxes()
            self.solve_mode()
            Jth0Array[q] = self.strata.Jth0
            self.plot_on_optimization1DCanvas(optiRange1D, xlabel, Jth0Array, ylabel)

        #reset initial values
        self.strata.stratumThicknesses = stratumThicknessesInitial
        self.strata.stratumDopings = stratumDopingsInitial
        self.update_stratum_inputBoxes()
        self.stratumTable_refresh()
        self.solve_mode()

        #reset GUI
        self.optiFrame.setEnabled(True)
        self.plotModeButton.setEnabled(True)

    def plot_on_optimization1DCanvas(self, xVals, xlabel, yVals, ylabel):
        self.optimization2DCanvas.setVisible(False)
        self.optimization1DCanvas.setVisible(True)

        self.optimization1DCanvas.clear()

        mask = ~np.isnan(yVals)
        optiCurve = SupportClasses.MaskedCurve(xVals, yVals, mask)
        optiCurve.setPen(QPen(Qt.blue, 1.5))
        if settings.antialiased:
            optiCurve.setRenderHint(Qwt.QwtPlotItem.RenderAntialiased)
        optiCurve.attach(self.optimization1DCanvas)

        self.optimization1DCanvas.setAxisTitle(Qwt.QwtPlot.xBottom, xlabel)
        self.optimization1DCanvas.setAxisTitle(Qwt.QwtPlot.yLeft, ylabel)
        self.optimization1DCanvas.replot()

    def run_opti2D(self):
        #get initial parameters
        try:
            optiType1D  = self.opti1DChoiceBox.currentText()
            strata1D    = np.array(SupportClasses.matlab_range(
                self.opti1DLayerBox.text()), dtype=int)
            strata1D   -= 1 #indexing starts at 0
            optiRange1D = np.array(SupportClasses.matlab_range(
                self.opti1DRangeBox.text()))
            optiType2D  = self.opti2DChoiceBox.currentText()
            strata2D    = np.array(SupportClasses.matlab_range(
                self.opti2DLayerBox.text()), dtype=int)
            strata2D   -= 1 #indexing starts at 0
            optiRange2D = np.array(SupportClasses.matlab_range(
                self.opti2DRangeBox.text()))
        except ValueError:
            QMessageBox.warning(self,"ErwinJr Error", "Invalid entry.")
            return

        Jth0Array = np.NaN * np.zeros((optiRange1D.size, optiRange2D.size))
        zlabel = '$J_{th0}$'

        stratumThicknessesInitial = self.strata.stratumThicknesses.copy()
        stratumDopingsInitial = self.strata.stratumDopings.copy()

        for qq, rangeValue2D in enumerate(optiRange2D):
            if optiType2D == 'Thickness':
                self.strata.stratumThicknesses[strata2D] = rangeValue2D
                xlabel = u'Thickness ($\mu m$)'
            elif optiType2D == 'Doping':
                self.strata.stratumDopings[strata2D] = rangeValue2D
                xlabel = 'Doping ($x10^{17} cm^{-3}$)'
            for q, rangeValue1D in enumerate(optiRange1D):
                if optiType1D == 'Thickness':
                    self.strata.stratumThicknesses[strata1D] = rangeValue1D
                    ylabel = u'Thickness ($\mu m$)'
                elif optiType1D == 'Doping':
                    self.strata.stratumDopings[strata1D] = rangeValue1D
                    ylabel = 'Doping ($x10^{17} cm^{-3}$)'

                self.stratumTable_refresh()
                self.update_stratum_inputBoxes()
                self.solve_mode()
                Jth0Array[q,qq] = self.strata.Jth0
                self.plot_on_optimization2DCanvas(optiRange1D, xlabel, 
                        optiRange2D, ylabel, Jth0Array, zlabel)
                QCoreApplication.processEvents()

        #reset initial values
        self.strata.stratumThicknesses = stratumThicknessesInitial
        self.strata.stratumDopings = stratumDopingsInitial
        self.update_stratum_inputBoxes()
        self.stratumTable_refresh()
        self.solve_mode()

        #reset GUI
        self.optiFrame.setEnabled(True)
        self.plotModeButton.setEnabled(True)

    def plot_on_optimization2DCanvas(self, 
            xVals, xlabel, yVals, ylabel, zVals, zlabel):
        self.optimization1DCanvas.setVisible(False)
        self.optimization2DCanvas.setVisible(True)

        X,Y = meshgrid(yVals, xVals)
        Z = zVals

        self.optimization2DAxes.cla()
        self.optimization2DAxes.patch.set_color(self.bgColor)
        self.optimization2DAxes.mouse_init()

        normd = matplotlib.colors.Normalize(
                np.nanmin(np.nanmin(Z)), np.nanmax(np.nanmax(Z)))
        self.optimization2DAxes.plot_surface(X, Y, Z, 
                cstride=1, rstride=1, norm=normd, cmap=matplotlib.cm.Blues_r, 
                linewidth=0, antialiased=False, shade=False)
        self.optimization2DAxes.set_zlim(0.95*np.nanmin(np.nanmin(Z)), 
                1.05*np.nanmax(np.nanmax(Z)))
        self.optimization2DAxes.set_xlabel(xlabel)
        self.optimization2DAxes.set_ylabel(ylabel)
        self.optimization2DAxes.set_zlabel(zlabel)
        self.optimization2DCanvas.draw()




#===============================================================================
# Quantum Tab Input Controls
#===============================================================================

    def update_inputBoxes(self):
        try:
            self.substrateBox.setCurrentIndex(self.substratesList.index(
                self.qclayers.substrate))
        except Exception as err:
            QMessageBox.warning(self,"ErwinJr - Warning",
                             "Substrate data wrong.\n"+str(err))

        self.qclayers.update_alloys()
        self.qclayers.update_strain()
        self.qclayers.populate_x()
        for n in range(self.numMaterials//2):
            self.MoleFracWellBox[n].setValue(self.qclayers.moleFrac[2*n])
            self.MoleFracBarrBox[n].setValue(self.qclayers.moleFrac[2*n+1])
            self.offsetLabel[n].setText("%6.0f meV" %
                    ((self.qclayers.EcG[2*n+1]-self.qclayers.EcG[2*n])*1000))

        self.update_quantumCanvas()

        strainString = ("<center>Net Strain: <b>%6.3f%%</b></center>" %
                self.qclayers.netStrain)
        self.strainDescription.setText(strainString)
        hwLOString = ("<center>LO phonon: <b>%4.1f ~ %4.1f meV</b></center>" %
                (min(self.qclayers.hwLO)*1000, max(self.qclayers.hwLO)*1000))
        self.LOPhononDescription.setText(hwLOString)

        self.inputVertResBox.setValue(self.qclayers.vertRes)
        self.inputEFieldBox.setValue(self.qclayers.EField)
        self.inputRepeatsBox.setValue(self.qclayers.repeats)
        self.inputHorzResBox.setCurrentIndex(self.inputHorzResBox.findText( 
            QString(unicode(self.qclayers.xres))))

        self.DescriptionBox.setText(self.qclayers.description)

        self.update_Lp_box()

        self.dirty = True
        self.update_windowTitle()

    def input_substrate(self, substrateType):
        """
        SLOT connected to SIGNAL self.substrateBox.currentIndexChanged(const QString)
        update substrate chosen
        """
        if substrateType == 'InP':
            self.qclayers.substrate = 'InP'
            self.materialList = ['InGaAs/AlInAs #1', 
                    'InGaAs/AlInAs #2', 
                    'InGaAs/AlInAs #3', 
                    'InGaAs/AlInAs #4']
            self.mtrl_header1.setText( '<center><b>\
                    In<sub>x</sub>Ga<sub>1-x</sub>As\
                    </b></center>')
            self.mtrl_header2.setText('<center><b>\
                    Al<sub>1-x</sub>In<sub>x</sub>As\
                    </b></center')

        elif substrateType == 'GaAs':
            self.qclayers.substrate = 'GaAs'
            self.materialList = ['AlGaAs/AlGaAs #1', 
                    'AlGaAs/AlGaAs #2', 
                    'AlGaAs/AlGaAs #3', 
                    'AlGaAs/AlGaAs #4']
            self.mtrl_header1.setText('<center><b>\
                    Al<sub>x</sub>Ga<sub>1-x</sub>As\
                    </b></center')
            self.mtrl_header2.setText('<center><b>\
                    Al<sub>x</sub>Ga<sub>1-x</sub>As\
                    </b></center')

        elif substrateType == 'GaSb':
            self.qclayers.substrate = 'GaSb'
            self.materialList = ['InAsSb/AlGaSb #1', 
                    'InAsSb/AlGaSb #2', 
                    'InAsSb/AlGaSb #3', 
                    'InAsSb/AlGaSb #4']
            self.mtrl_header1.setText('<center><b>\
                    InAs<sub>y</sub>Sb<sub>1-y</sub>\
                    </b></center')
            self.mtrl_header2.setText('<center><b>\
                    Al<sub>x</sub>Ga<sub>1-x</sub>Sb\
                    </b></center')

        elif substrateType == 'GaN':
            #  self.input_substrate(self.qclayers.substrate)
            QMessageBox.information(self, 'ErwinJr Error', 
                    'III-Nitride substrates have not yet been implemented.')
            self.substrateBox.setCurrentIndex(
                    self.substrateBox.findText(self.qclayers.substrate))
            return

        else:
            raise TypeError('substrate selection not allowed')
            return

        self.quantumCanvas.clear()
        #self.layerTable_refresh()
        self.update_Lp_limits()
        self.update_inputBoxes()
        self.layerTable_refresh()
        self.qclayers.populate_x()


    def input_EField(self):
        """
        SLOT connected to SIGNAL self.inputEFieldBox.valueChanged(double)
        update external E field in unit kV/cm
        """
        self.qclayers.EField = float(self.inputEFieldBox.value())

        self.qclayers.populate_x()
        self.update_quantumCanvas()

        self.dirty = True
        self.update_windowTitle()

    def input_horzRes(self):
        """
        SLOT connected to SIGNAL self.inputHorzResBox.currentIndexChanged(int)
        update position resolution (xres), in angstrom
        """
        horzRes = unicode(self.inputHorzResBox.currentText())
        horzRes = float(horzRes)
        self.qclayers.set_xres(horzRes)
        self.qclayers.populate_x()
        self.update_quantumCanvas()
        self.dirty = True
        self.update_windowTitle()

    def input_vertRes(self):
        self.qclayers.vertRes = float(self.inputVertResBox.value())
        self.dirty = True
        self.update_windowTitle()

    def input_repeats(self):
        self.qclayers.repeats = int(self.inputRepeatsBox.value())
        self.qclayers.populate_x()
        self.update_quantumCanvas()
        self.dirty = True
        self.update_windowTitle()

    def input_basis(self):
        """
        SLOT connected to self.inputARInjectorCheck.stateChanged(int) and
        self.inputInjectorARCheck.stateChanged(int)
        update dividers info
        """
        self.qclayers.basisARInjector = self.inputARInjectorCheck.isChecked()
        self.qclayers.basisInjectorAR = self.inputInjectorARCheck.isChecked()
        self.dirty = True
        self.update_windowTitle()

    def update_Lp_limits(self):
        """
        Update Lp select range in the Period Info box (GUI)
        """
        self.LpFirstSpinbox.setRange(1,self.qclayers.layerWidth.size-1)
        self.LpFirstSpinbox.setValue(1)
        self.LpLastSpinbox.setRange(1,self.qclayers.layerWidth.size-1)
        self.LpLastSpinbox.setValue(self.qclayers.layerWidth.size-1)

    def update_Lp_box(self):
        """
        Update Lp box in the Period Info box (GUI): 
            Lp:total length
            well: persentage of well material 
            nD: average doping (cm-3)
            ns: 2D carrier density in 1E11 cm-2
        """
        LpFirst = self.LpFirstSpinbox.value()
        LpLast = self.LpLastSpinbox.value()+1 
            #+1 because range is not inclusive of last value
        # total length of the layers (1 period)
        Lp = sum(self.qclayers.layerWidth[LpFirst:LpLast]) *self.qclayers.xres
        Lp_string  = u"Lp: %g \u212B<br>" % Lp
        # total length of well (1 period)
        Lw = sum((1-self.qclayers.layerBarriers[LpFirst:LpLast])
                *self.qclayers.layerWidth[LpFirst:LpLast]) *self.qclayers.xres
        if Lp == 0: 
            Lp_string += u"wells: NA%%<br>" 
            # average doping of the layers
            Lp_string += (u"n<sub>D</sub>: NA\u00D710<sup>17</sup>"
                    u"cm<sup>-3</sup><br>") 
        else: 
            Lp_string += u"wells: %6.1f%%<br>" % (100.0*Lw/Lp)
            # average doping of the layers
            nD = self.qclayers.xres * sum(
                    self.qclayers.layerDopings[LpFirst:LpLast]
                    *self.qclayers.layerWidth[LpFirst:LpLast])/Lp
            Lp_string += (u"n<sub>D</sub>: %6.3f\u00D710<sup>17</sup>"
                    u"cm<sup>-3</sup><br>") % nD
        # 2D carrier density in 1E11cm-2
        ns = self.qclayers.xres * sum(
                self.qclayers.layerDopings[LpFirst:LpLast]
                *self.qclayers.layerWidth[LpFirst:LpLast])*1e-2
        Lp_string += (u"n<sub>s</sub>: %6.3f\u00D710<sup>11</sup>"
            u"cm<sup>-2</sup") % ns
        self.LpStringBox.setText(Lp_string)

    def set_targetWL(self):
        try:
            wl = float(self.targetWL_box.text())
        except ValueError:
            QMessageBox.warning(self, 'ErwinJr Error', 
                'Invalid input:%s'%(self.targetWL_box.text()))
            self.targetWL_box.setText('')
        self.targetWL = wl
        self.targetWL_box.setText('%.1f'%self.targetWL)

    def set_goal(self, goal): 
        self.OptGoal = self.OptGoalsFunc[goal]

    def input_description(self):
        self.qclayers.description = self.DescriptionBox.toPlainText()
        self.dirty = True
        self.update_windowTitle()

    def input_moleFrac(self, boxID):
        self.qclayers.moleFrac[boxID] = float(
                self.MoleFracWellBox[boxID//2].value() if boxID % 2 == 0
                else self.MoleFracBarrBox[(boxID-1)//2].value())
        self.dirty = True
        self.update_windowTitle()

        self.update_inputBoxes()
        self.qclayers.update_alloys()
        self.qclayers.update_strain()
        self.qclayers.populate_x()
        self.update_quantumCanvas()




#===============================================================================
# Quantum Tab Layer Table Control
#===============================================================================

    def layerTable_refresh(self):
        """Refresh layer table, called every time after data update"""
        # Block itemChanged SIGNAL while refreshing
        #  self.clear_WFs()
        self.layerTable.blockSignals(True) 
        self.layerTable.clear()
        self.layerTable.setColumnCount(6)
        self.layerTable.setRowCount(self.qclayers.layerWidth.size+1)
        self.layerTable.setHorizontalHeaderLabels(['Width', 'ML', 'Brr', 
            'AR', 'Doping', 'Material'])
        #  vertLabels = []
        #  for n in xrange(self.qclayers.layerWidth.size+1):
            #  vertLabels.append(str(n))
        vertLabels = [str(n) for n in
                range(self.qclayers.layerWidth.size+1)]
        self.layerTable.setVerticalHeaderLabels(vertLabels)        

        #color for barrier layers
        gray = QColor(230,230,240)  # for Barrier layers
        gray2 = QColor(230,230,230) # for unchangable background

        for q, layerWidth in enumerate(self.qclayers.layerWidth):
            #Width Setup
            width = QTableWidgetItem("%5.1f" %
                    (layerWidth*self.qclayers.xres))
            width.setTextAlignment(Qt.AlignCenter)
            if bool(self.qclayers.layerBarriers[q]):
                width.setBackgroundColor(gray)
            self.layerTable.setItem(q, 0, width)
            if q == 0:
                width.setFlags(Qt.NoItemFlags)
                width.setBackgroundColor(gray2)

            #ML Setup
            numML = self.qclayers.xres*layerWidth/self.qclayers.MLThickness[q]
            item = QTableWidgetItem("%5.1f" % numML)
            item.setTextAlignment(Qt.AlignCenter)
            if bool(self.qclayers.layerBarriers[q]):
                item.setBackgroundColor(gray)
            self.layerTable.setItem(q, 1, item)
            if q == 0:
                item.setFlags(Qt.NoItemFlags)
                item.setBackgroundColor(gray2)

            #Barrier Layer Setup
            item = QTableWidgetItem()
            #  item.setCheckState(int(self.qclayers.layerBarriers[q])*2)
            item.setCheckState(Qt.Checked if
                    self.qclayers.layerBarriers[q]==1 else Qt.Unchecked)
            if bool(self.qclayers.layerBarriers[q]):
                item.setBackgroundColor(gray)
            self.layerTable.setItem(q, 2, item)
            if q == 0:
                item.setFlags(Qt.NoItemFlags)
                item.setBackgroundColor(gray2)

            #Active Region Layer Setup
            item = QTableWidgetItem()
            #  item.setCheckState(int(self.qclayers.layerARs[q])*2)
            item.setCheckState(Qt.Checked if
                    self.qclayers.layerARs[q]==1 else Qt.Unchecked)
            if bool(self.qclayers.layerBarriers[q]):
                item.setBackgroundColor(gray)
            self.layerTable.setItem(q, 3, item)
            if q == 0:
                item.setFlags(Qt.NoItemFlags)
                item.setBackgroundColor(gray2)

            #Layer Doping Setup
            doping = QTableWidgetItem(unicode(self.qclayers.layerDopings[q]))
            doping.setTextAlignment(Qt.AlignCenter)
            if bool(self.qclayers.layerBarriers[q]):
                doping.setBackgroundColor(gray)
            self.layerTable.setItem(q, 4, doping)
            if q == 0:
                doping.setFlags(Qt.NoItemFlags)
                doping.setBackgroundColor(gray2)

            #Material Setup
            if q == 0:
                item = QTableWidgetItem(unicode(self.materialList[
                    int(self.qclayers.layerMaterials[q])-1]))
                #TODO: reformat layerMaterials to int begin at 0
                item.setBackgroundColor(gray2)
                item.setFlags(Qt.NoItemFlags)
                self.layerTable.setItem(q, 5, item)
            else:
                materialWidget = QComboBox()
                materialWidget.addItems(self.materialList)
                materialWidget.setCurrentIndex(self.qclayers.layerMaterials[q]-1)
                self.connect(materialWidget, 
                        SIGNAL("currentIndexChanged(int)"), 
                        partial(self.layerTable_materialChanged, q))
                self.layerTable.setCellWidget(q, 5, materialWidget)

        self.layerTable.resizeColumnsToContents()

        self.layerTable.blockSignals(False)

    def layerTable_itemChanged(self, item):
        """SLOT connected to SIGNAL self.layerTable.itemChanged(QTableWidgetItem*)
        Update layer profile after user input"""
        #TODO: redo illegal input
        #  column = self.layerTable.currentColumn()
        #  row = self.layerTable.currentRow()
        #  print "---debug, itemChanged--- (%d, %d)"%(column, row)
        #  print "--debug, itemChanged (%d, %d)"%(item.column(), item.row())
        #  print item.text()
        #  if column == -1: #column == -1 on GUI initialization
            #  return
        column = item.column()
        row = item.row()
        if column == 0: #column == 0 for item change in Widths column
            new_width = float(item.text())
            new_width_int = int(np.round(new_width/self.qclayers.xres))
            #  if np.mod(new_width, self.qclayers.xres) != 0 \
                    #  and self.qclayers.xres != 0.1:
            if np.abs(new_width_int * self.qclayers.xres-new_width) > 1E-9:
                # TODO: bug to fix, np.mod is not good for xres < 0.5
                # potential solution is to change internal length to int
                # times xres
                QMessageBox.warning(self,"ErwinJr - Warning", 
                        ("You entered a width that is not compatible with "
                        "the minimum horizontal resolution. "
                        "%f %% %f = %f"%(new_width, self.qclayers.xres,
                            np.mod(new_width, self.qclayers.xres))))
                return
            if row == self.qclayers.layerWidth.size: #add row at end of list
                self.qclayers.layerWidth = np.append(
                        self.qclayers.layerWidth, new_width_int)
                self.qclayers.layerBarriers = np.append(
                        self.qclayers.layerBarriers, 
                        0 if self.qclayers.layerBarriers[-1] == 1 else 1)
                self.qclayers.layerARs = np.append(
                        self.qclayers.layerARs, 
                        self.qclayers.layerARs[-1])
                self.qclayers.layerMaterials = np.append(
                        self.qclayers.layerMaterials, 
                        self.qclayers.layerMaterials[-1])
                self.qclayers.layerDopings = np.append(
                        self.qclayers.layerDopings, 
                        self.qclayers.layerDopings[-1])
                self.qclayers.layerDividers = np.append(
                        self.qclayers.layerDividers, 
                        self.qclayers.layerDividers[-1])
                row += 1 #used so that last (blank) row is again selected

                #make first item the same as last item
                self.qclayers.layerWidth[0] = self.qclayers.layerWidth[-1]
                self.qclayers.layerBarriers[0] = self.qclayers.layerBarriers[-1]
                self.qclayers.layerARs[0] = self.qclayers.layerARs[-1]
                self.qclayers.layerMaterials[0] = self.qclayers.layerMaterials[-1]
                self.qclayers.layerDopings[0] = self.qclayers.layerDopings[-1]
                self.qclayers.layerDividers[0] = self.qclayers.layerDividers[-1]
                self.update_Lp_limits()

            elif row == self.qclayers.layerWidth.size-1:
                self.qclayers.layerWidth[row] = new_width_int
                #make first item the same as last item
                self.qclayers.layerWidth[0] = self.qclayers.layerWidth[-1]
                #  self.qclayers.layerBarriers[0] = self.qclayers.layerBarriers[-1]
                #  self.qclayers.layerARs[0] = self.qclayers.layerARs[-1]
                #  self.qclayers.layerMaterials[0] = self.qclayers.layerMaterials[-1]
                #  self.qclayers.layerDopings[0] = self.qclayers.layerDopings[-1]
                #  self.qclayers.layerDividers[0] = self.qclayers.layerDividers[-1]  

            else: #change Width of selected row in-place
                self.qclayers.layerWidth[row] = new_width_int

        elif column == 1: #column == 1 for ML
            if self.qclayers.xres != 0.1:
                QMessageBox.warning(self,"ErwinJr - Warning", 
                        (u"Horizontal Resolution of 0.1 \u212B required" 
                        u"when setting monolayer thicknesses."))
                return
            if row == self.qclayers.layerWidth.size: #add row at end of list
                pass
            elif row == self.qclayers.layerWidth.size-1:
                self.qclayers.layerWidth[row] = int(np.round( 
                    self.qclayers.MLThickness[row] * float(item.text())
                    / self.qclayers.xres))

                #make first item the same as last item
                self.qclayers.layerWidth[0] = self.qclayers.layerWidth[-1]
                #  self.qclayers.layerBarriers[0] = self.qclayers.layerBarriers[-1]
                #  self.qclayers.layerARs[0] = self.qclayers.layerARs[-1]
                #  self.qclayers.layerMaterials[0] = self.qclayers.layerMaterials[-1]
                #  self.qclayers.layerDopings[0] = self.qclayers.layerDopings[-1]
                #  self.qclayers.layerDividers[0] = self.qclayers.layerDividers[-1]

                self.update_Lp_limits()

            else: #change Width of selected row in-place
                self.qclayers.layerWidth[row] = int(np.round(
                        self.qclayers.MLThickness[row] * float(item.text()) 
                        / self.qclayers.xres ))
        elif column == 2: #column == 2 for item change in Barrier column
            if row == self.qclayers.layerWidth.size: 
                #don't do anything if row is last row
                return
            #  self.qclayers.layerBarriers[row] = int(item.checkState())//2
            self.qclayers.layerBarriers[row] = (item.checkState() == Qt.Checked)
        elif column == 3: #column == 3 for item change in AR column
            if row == self.qclayers.layerWidth.size: 
                #don't do anything if row is last row
                return
            #  self.qclayers.layerARs[row] = int(item.checkState())//2
            self.qclayers.layerARs[row] = (item.checkState() == Qt.Checked)
        elif column == 4: #column == 4 for item change in Doping column
            if row == self.qclayers.layerWidth.size: 
                #don't do anything if row is last row
                return
            self.qclayers.layerDopings[row] = float(item.text())
        elif column == 5: #column == 5 for item change in Materials column
            #self.qclayers.layerWidth[row] = int(item.text[row])
           pass
        else:
            pass
        self.layerTable_refresh()
        #self.qclayers.populate_x()
        #self.layerTable.selectRow(row)
        self.layerTable.setCurrentCell(row,column)
        self.layerTable.setFocus()

        self.update_Lp_box()

        self.dirty = True
        self.update_windowTitle()        

    def layerTable_materialChanged(self, row, selection):
        """SLOT as partial(self.layerTable_materialChanged, q)) connected to 
        SIGNAL self.materialWidget.currentIndexChanged(int) """
        self.qclayers.layerMaterials[row] = selection+1
        #self.layerTable_refresh()
        self.qclayers.populate_x()
        self.layerTable.selectRow(row)

        self.dirty = True
        self.update_windowTitle()        

    def layerTable_itemSelectionChanged(self):
        """SLOT connected to SIGNAL self.layerTable.itemSelectionChanged()"""
        #This is the primary call to update_quantumCanvas
        self.qclayers.layerSelected = self.layerTable.currentRow()
        if self.qclayers.layerSelected >= 0 and \
                self.qclayers.layerSelected < self.qclayers.layerWidth.size:
            self.qclayers.populate_x()
            self.update_quantumCanvas()

    def delete_layer(self):
        #don't delete last layer
        if self.qclayers.layerWidth.size == 1:
            return
        row = self.layerTable.currentRow()
        if row == -1 or row >= self.qclayers.layerWidth.size:
            return

        self.qclayers.layerWidth = np.delete(self.qclayers.layerWidth, row)
        self.qclayers.layerBarriers = np.delete(self.qclayers.layerBarriers, row)
        self.qclayers.layerARs = np.delete(self.qclayers.layerARs, row)
        self.qclayers.layerMaterials = np.delete(self.qclayers.layerMaterials, row)
        self.qclayers.layerDopings = np.delete(self.qclayers.layerDopings, row)
        self.qclayers.layerDividers = np.delete(self.qclayers.layerDividers, row)

        if row == self.qclayers.layerWidth.size: #if row == last_row
            #make first item the same as last item
            self.qclayers.layerWidth[0] = self.qclayers.layerWidth[-1]
            self.qclayers.layerBarriers[0] = self.qclayers.layerBarriers[-1]
            self.qclayers.layerARs[0] = self.qclayers.layerARs[-1]
            self.qclayers.layerMaterials[0] = self.qclayers.layerMaterials[-1]
            self.qclayers.layerDopings[0] = self.qclayers.layerDopings[-1]
            self.qclayers.layerDividers[0] = self.qclayers.layerDividers[-1]

        self.update_Lp_limits()
        self.update_Lp_box()

        self.qclayers.update_strain()
        self.layerTable_refresh()
        self.qclayers.populate_x()
        self.layerTable.selectRow(row)
        self.layerTable.setFocus()

        self.dirty = True
        self.update_windowTitle()

    def insert_layerAbove(self):
        row = self.layerTable.currentRow()
        if row == -1:
            return

        self.qclayers.layerWidth = np.insert(
                self.qclayers.layerWidth, row, 0)
        self.qclayers.layerBarriers = np.insert(
                self.qclayers.layerBarriers, row,
                0 if self.qclayers.layerBarriers[row] == 1 else 1)
        self.qclayers.layerARs = np.insert(
                self.qclayers.layerARs, row, 
                self.qclayers.layerARs[row])
        self.qclayers.layerMaterials = np.insert(
                self.qclayers.layerMaterials, row,
                self.qclayers.layerMaterials[row])
        self.qclayers.layerDopings = np.insert(
                self.qclayers.layerDopings, row,
                self.qclayers.layerDopings[row])
        self.qclayers.layerDividers = np.insert(
                self.qclayers.layerDividers, row,
                self.qclayers.layerDividers[row])

        self.update_Lp_limits()
        self.update_Lp_box()

        self.layerTable_refresh()
        self.qclayers.populate_x()
        self.layerTable.selectRow(row)
        self.layerTable.setFocus()

        self.dirty = True
        self.update_windowTitle()            




#===============================================================================
# Quantum Tab Buttons
#===============================================================================

    def Calculating(self, is_doing):
        """UI repaint for doing calculating """
        for button in (self.solveWholeButton, self.solveBasisButton,
                self.pairSelectButton):
            button.setEnabled(not is_doing)
            button.repaint()
        if self.pairSelected: 
            self.FoMButton.setEnabled(not is_doing)
            self.FoMButton.repaint()
            if self.solveType == 'whole':
                for button in (self.OptimizeFoMButton, self.OptimizeDipoleButton):
                    button.setEnabled(not is_doing)
                    button.repaint()


    def solve_whole(self):  #solves whole structure
        """SLOT connected to SIGNAL self.solveWholeButton.clicked()
        Whole solver """
        if hasattr(self.qclayers, "EigenE"):
            self.clear_WFs()
        self.pairSelected = False
        self.Calculating(True)

        self.qclayers.populate_x_band()
        try:
            self.qclayers.solve_psi()
            self.plotDirty = True
            self.solveType = 'whole'
            self.update_quantumCanvas()
            if DEBUG >= 4: 
                with open('qclayer.pkl','wb') as f:
                    pickle.dump(self.qclayers, f, pickle.HIGHEST_PROTOCOL)
                print self.qclayers.EigenE
        except (IndexError,TypeError) as err:
            QMessageBox.warning(self, 'ErwinJr - Error', str(err))

        self.Calculating(False)


    def solve_basis(self):  #solves structure with basis
        """SLOT connected to SIGNAL self.solveBasisButton.clicked()
        Basis solver """
        self.Calculating(True)

        try:
            self.dCL = self.qclayers.basisSolve()
            self.qclayers.convert_dCL_to_data(self.dCL)
            self.solveType = 'basis'        
            self.plotDirty = True
            self.update_quantumCanvas()
        except (ValueError,IndexError) as err:
            QMessageBox.warning(self,"ErwinJr - Error", str(err))

        self.Calculating(False)

    def pair_select(self, on):
        """ SLOT connected to SINGAL self.pairSelectButton.clicked()
        Enable/Disable pair selection."""
        if on:
            self.wellSelectButton.setChecked(False)
            self.panButton.setChecked(False)
            self.zoomButton.setChecked(False)
            self.selectedWF = []
            self.stateHolder = []
            self.picker.setEnabled(True)
            self.quantumCanvas.canvas().setCursor(Qt.PointingHandCursor)
        else:
            self.picker.setEnabled(False)
            self.stateHolder = []
            self.pairSelectString.setText('')
            for curve in self.selectedWF:
                try:
                    curve.detach()
                except RuntimeError:
                    #underlying C/C++ object has been deleted
                    pass
            self.quantumCanvas.replot()
            self.quantumCanvas.canvas().setCursor(Qt.ArrowCursor)

    def hinput(self, aQPointF):
        #x data is self.qclayers.xPointsPost
        x = aQPointF.x()

        xLayerNum = np.argmin((self.qclayers.xPoints-x)**2)
        layerNum = self.qclayers.xLayerNums[xLayerNum]

        self.layerTable.selectRow(layerNum)
        self.layerTable.setFocus()

    def figure_of_merit(self):
        """
        SLOT connected to SIGNAL self.FoMButton.clicked()
        Calculate Figure of merit
        """
        if len(self.stateHolder) < 2:
            return

        self.Calculating(True)
        self.FoMButton.setEnabled(False)
        self.FoMButton.repaint()

        upper = self.stateHolder[1]
        lower = self.stateHolder[0]        
        if upper < lower:
            upper, lower = lower, upper
            #  temp = upper
            #  upper = lower
            #  lower = temp

        self.tauLower = self.qclayers.lo_life_time(lower)
        self.tauUpper = self.qclayers.lo_life_time(upper)
        self.FoM = self.opticalDipole**2 * self.tauUpper \
                * (1- self.tauLower/self.tauUpperLower)
        # tauUpperLower is the inverse of transition rate (lifetime)
        self.alphaISB = self.qclayers.alphaISB(upper, lower)

        self.FoMString  = (u"<i>\u03C4<sub>upper</sub></i> : %6.2f ps<br>"
                u"<i>\u03C4<sub>lower</sub></i> : %6.2f ps"
                u"<br>FoM: <b>%6.0f ps \u212B<sup>2</sup></b>"
                u"<br><i>\u03B1<sub>ISB</sub></i> : %.2f cm<sup>2</sup>") % (
                        self.tauUpper, self.tauLower, self.FoM, self.alphaISB)

        self.pairSelectString.setText(self.pairString + self.FoMString)

        self.Calculating(False)
        self.FoMButton.setEnabled(True)
        self.transferOpticalParametersButton.setEnabled(True)

    def OptimizeLayer(self, goal):
        """Optimize the thickness of selected layer to maximaze the goal
        function using Newton's method.. 
        Support only for whole solve
        """
        row = self.layerTable.currentRow()
        if row == -1 or row >= self.qclayers.layerWidth.size:
            QMessageBox.warning(self, "ErwinJr Error", 
                "Invalid layer selection.")
            return

        self.Calculating(True)

        try:
            xres = self.qclayers.xres
            step = 1 # * xres
            upper = self.stateHolder[1]
            lower = self.stateHolder[0]        
            old_width = -1
            origin_width = new_width = self.qclayers.layerWidth[row]
            if DEBUG >= 1:
                print "--debug-- width optimization"
            #  print "init: \n Lyaer # %d width = %.2f"%(row, new_width)

            goals = np.empty(3)
            goal_old = goals[1] = np.abs(goal(upper,lower))
            width_tried = [origin_width]
            goal_tried = [goal_old]
            #  while abs(old_width - new_width) >= 0.7*xres:
            while old_width != new_width :
                # Solve for values of goal near old_width
                # improve: only solve for eigen states near selection
                goal_old = goals[1]
                self.qclayers.layerWidth[row] = new_width - step
                self.qclayers.populate_x()
                self.qclayers.populate_x_band()
                self.qclayers.solve_psi()
                goals[0] = np.abs(goal(upper,lower))

                self.qclayers.layerWidth[row] = new_width + step
                self.qclayers.populate_x()
                self.qclayers.populate_x_band()
                self.qclayers.solve_psi()
                goals[2] = np.abs(goal(upper,lower))
                diff = (goals[2] - goals[0])/2
                diff2 = goals[0] + goals[2] - 2*goals[1]

                step_cutoff = 0.5E3 
                old_width = new_width
                # set a cutoff s.t. Newton's method won't go too far
                if -diff2 < 1/step_cutoff:
                    # When Newton's method is not a good one
                    new_width += int(np.round(step *
                        step_cutoff*diff/goals[1]))
                else:
                    new_width += -int(np.round(step * diff/diff2))
                if new_width <= 0:
                    new_width = 1
                if DEBUG >= 1:
                    print "Layer # %d width = %.1f; goal = %f"%(
                            row, old_width*xres, goals[1])
                    print "\tdiff = %f; diff2 = %f, new_width= %.1f"%(
                            diff, diff2, new_width*xres)

                self.qclayers.layerWidth[row] = new_width
                self.qclayers.populate_x()
                self.qclayers.populate_x_band()
                self.qclayers.solve_psi()
                goal_new = np.abs(goal(upper,lower))
                E_i = self.qclayers.EigenE[upper]
                E_j = self.qclayers.EigenE[lower]
                wavelength = h*c0/(e0*np.abs(E_i-E_j))*1e6
                if DEBUG >= 1:
                    print "\tgoal_new = %f, wl = %.1f um"%(goal_new, wavelength)

                while goal_new < goal_old*0.95: 
                    #  So a step will not go too far
                    #  new_width = (old_width + new_width)/2
                    new_width = int( (old_width + new_width)/(2))
                    if DEBUG >= 1:
                        print "\tGoing too far, back a little bit: "
                        print "\tnew_width=%.1f"%(new_width*xres)
                    self.qclayers.layerWidth[row] = new_width
                    self.qclayers.populate_x()
                    self.qclayers.populate_x_band()
                    self.qclayers.solve_psi()
                    goal_new = np.abs(goal(upper,lower))
                    E_i = self.qclayers.EigenE[upper]
                    E_j = self.qclayers.EigenE[lower]
                    wavelength = h*c0/(e0*np.abs(E_i-E_j))*1e6
                    if DEBUG >= 1:
                        print "\tgoal_new = %f, wl = %.1f um"%(goal_new, wavelength)

                goal_old = goals[1]
                goals[1] = goal_new
                if new_width in width_tried:
                    print "new_width has been tried"
                    break
                width_tried.append(new_width)
                goal_tried.append(goal_new)

            self.qclayers.layerWidth[row] = new_width
        finally:
            self.Calculating(False)
            if self.qclayers.layerWidth[row] != origin_width: 
                self.clear_WFs()
                self.layerTable_refresh()
                self.qclayers.populate_x()
                self.qclayers.populate_x_band()
                self.dirty = True
                self.update_windowTitle()  
                self.plotDirty = True
                self.update_quantumCanvas()
        if DEBUG >= 1:
            print "done"

    def GlobalOptimization(self):
        if not hasattr(self, 'targetWL'):
            QMessageBox.warning(self, "ErwinJr Error", 
                "Target wavelength is not set.")
            return
        if DEBUG >= 1:
            print "Global Optimization for %s"%self.OptGoal.__name__
        Jaco = 0

    def ginput(self, aQPointF):
        """Pair select in GUI, according to mouse click
        SLOT connect to SIGNAL self.picker.selected(const QwtDoublePoint&)
        """
        #x data is self.qclayers.xPointsPost
        #y data is self.qclayers.xyPsiPsi[:,q] + self.qclayers.EigenE[q]
        x = aQPointF.x()
        y = aQPointF.y()
        xData = np.tile(self.qclayers.xPointsPost,
                (self.qclayers.xyPsiPsi.shape[1],1)).T
        yData = self.qclayers.xyPsiPsi + self.qclayers.EigenE

        xScale = self.quantumCanvas.axisScaleDiv(Qwt.QwtPlot.xBottom).upperBound() - self.quantumCanvas.axisScaleDiv(Qwt.QwtPlot.xBottom).lowerBound()
        yScale = self.quantumCanvas.axisScaleDiv(Qwt.QwtPlot.yLeft).upperBound() - self.quantumCanvas.axisScaleDiv(Qwt.QwtPlot.yLeft).lowerBound()

        r = np.nanmin(sqrt( ((xData-x)/xScale)**2+((yData-y)/yScale)**2 ), axis=0)
        selectedState = np.nanargmin(r)
        if len(self.stateHolder) >= 2:
            # start new pair selection
            self.stateHolder = []
            for curve in self.selectedWF:
                try:
                    curve.detach()
                except RuntimeError:
                    #underlying C/C++ object has been deleted
                    pass
            self.selectedWF = []
            self.quantumCanvas.replot()
            self.pairSelected = False
            for button in (self.FoMButton, self.OptimizeFoMButton,
                    self.OptimizeDipoleButton):
                button.setEnabled(False)
                button.repaint()
        self.stateHolder.append(selectedState)

        q = selectedState
        mask = ~np.isnan(self.qclayers.xyPsiPsi[:,q])
        curve = SupportClasses.MaskedCurve(
                self.qclayers.xPointsPost,
                self.qclayers.xyPsiPsi[:,q] + self.qclayers.EigenE[q],mask)
        curve.setPen(QPen(Qt.black, 3))
        curve.setRenderHint(Qwt.QwtPlotItem.RenderAntialiased)
        curve.attach(self.quantumCanvas)
        self.selectedWF.append(curve)
        self.quantumCanvas.replot()

        self.pairString  = (u"selected: %d, ..<br>"%selectedState)

        #  if np.mod(len(self.stateHolder),2) == 0:
        if len(self.stateHolder) == 2:
            self.pairSelected = True
            #TODO: put these enablement to a functions
            self.FoMButton.setEnabled(True)
            if self.solveType == 'whole':
                self.OptimizeFoMButton.setEnabled(True)
                self.OptimizeDipoleButton.setEnabled(True)
            E_i = self.qclayers.EigenE[self.stateHolder[0]]
            E_j = self.qclayers.EigenE[self.stateHolder[1]]
            if E_i > E_j:
                upper = self.stateHolder[0]
                lower = self.stateHolder[1]
            else:
                upper = self.stateHolder[1]
                lower = self.stateHolder[0]

            self.eDiff = 1000*(E_i-E_j)
            self.wavelength = h*c0/(e0*np.abs(E_i-E_j))*1e6

            if self.solveType is 'basis':
                couplingEnergy = self.qclayers.coupling_energy(self.dCL, upper, lower)
                self.transitionBroadening = self.qclayers.broadening_energy(
                        upper, lower)
                self.qclayers.populate_x_band()
                self.opticalDipole = self.qclayers.dipole(upper, lower)            
                self.tauUpperLower = 1/self.qclayers.lo_transition_rate(upper, lower)
                self.pairString  = (u"selected: %d, %d<br>"
                                 u"energy diff: <b>%6.1f meV</b> (%6.1f um)<br>"
                                 u"coupling: %6.1f meV<br>broadening: %6.1f meV<br>"
                                 u"dipole: <b>%6.1f \u212B</b>"
                                 u"<br>LO scattering: <b>%6.2g ps</b><br>") % (
                                         self.stateHolder[0], 
                                         self.stateHolder[1], 
                                         self.eDiff, self.wavelength,
                                         couplingEnergy, 
                                         self.transitionBroadening, 
                                         self.opticalDipole, 
                                         self.tauUpperLower)

            elif self.solveType is 'whole':
                self.qclayers.populate_x_band()
                self.opticalDipole = self.qclayers.dipole(upper, lower)
                self.tauUpperLower = 1/self.qclayers.lo_transition_rate(upper, lower)
                self.transitionBroadening = 0.1 * self.eDiff
                self.pairString = (u"selected: %d, %d<br>"
                                 u"energy diff: <b>%6.1f meV</b> (%6.1f um)<br>"
                                u"dipole: %6.1f \u212B<br>" 
                                u"LO scattering: %6.2g ps<br>") % (
                                        self.stateHolder[0], 
                                        self.stateHolder[1], 
                                        self.eDiff, self.wavelength, 
                                        self.opticalDipole,
                                        self.tauUpperLower)
            else:
                self.FoMButton.setEnabled(False)

        self.pairSelectString.clear()
        self.pairSelectString.setText(self.pairString)        

    def transfer_optical_parameters(self):
        #set wavelength
        self.strata.wavelength = 1.24/np.abs(self.eDiff)*1000

        #set operating field
        self.strata.operatingField = self.qclayers.EField

        #set Lp
        LpFirst = self.LpFirstSpinbox.value()
        LpLast = self.LpLastSpinbox.value()+1 
            #+1 because range is not inclusive of last value
        self.strata.Lp = self.qclayers.xres * np.sum(
                self.qclayers.layerWidth[LpFirst:LpLast])

        #set nD doping sheet density
        self.strata.nD = np.sum(self.qclayers.layerDopings[LpFirst:LpLast] *
                self.qclayers.layerWidth[LpFirst:LpLast]) / \
                np.sum(self.qclayers.layerWidth[LpFirst:LpLast])
        #set aCore
        self.strata.aCore = self.alphaISB
        #set nCore
        kCore = 1/(4*pi) * self.strata.aCore * self.strata.wavelength*1e-4 
        # See Def of acore
        # 1e-4: aCore in cm-1, wl in um
        self.strata.nCore = self.qclayers.get_nCore(self.strata.wavelength) \
                + 1j*kCore

        #set tauUpper
        self.strata.tauUpper = self.tauUpper
        #set tauLower
        self.strata.tauLower = self.tauLower
        #set tauUpperLower
        self.strata.tauUpperLower = self.tauUpperLower
        #set optical dipole
        self.strata.opticalDipole = self.opticalDipole
        #set figure of merit
        self.strata.FoM = self.FoM
        #2gamma transition broadening
        self.strata.transitionBroadening = self.transitionBroadening / 1000 
            # store in eV

        #GUI settings
        self.transferOpticalParametersButton.setEnabled(False)
        self.editOpticalParametersBox.setChecked(False)

        #update all the input boxes
        self.update_stratum_inputBoxes()

        #update the stratumTable
        self.stratumTable_refresh()




#===============================================================================
# Quantum Tab Plotting and Plot Control
#===============================================================================

    def update_quantumCanvas(self):
        #setup for layer outline

        #PyQwt code
        if self.plotDirty: #self.plotdirty is True when self.go is executed
            self.quantumCanvas.clear()

        #plot xVc
        try:
            self.curveVc.detach()
            self.curveAR.detach()
        except AttributeError:
            #self.curveVc has not yet been formed
            pass
        except RuntimeError:
            #self.curveVc deleted with self.quantumCanvas.clear()
            pass
        self.curveVc = Qwt.QwtPlotCurve()
        self.curveVc.setData(self.qclayers.xPoints,self.qclayers.xVc)
        self.curveVc.setPen(QPen(Qt.black, 1))
        if settings.antialiased:
            self.curveVc.setRenderHint(Qwt.QwtPlotItem.RenderAntialiased)
        self.curveVc.attach(self.quantumCanvas)

        #plot Conduction Band L-Valley
        if self.plotVL:
            self.curveVL = Qwt.QwtPlotCurve()
            self.curveVL.setData(self.qclayers.xPoints,self.qclayers.xVL)
            self.curveVL.setPen(QPen(Qt.green, 1, Qt.DashLine))
            if settings.antialiased:
                self.curveVL.setRenderHint(Qwt.QwtPlotItem.RenderAntialiased)
            self.curveVL.attach(self.quantumCanvas)
        else:
            try:
                self.curveVL.detach()
            except (AttributeError, RuntimeError):
                pass

        #plot Conduction Band X-Valley
        if self.plotVX:
            self.curveVX = Qwt.QwtPlotCurve()
            self.curveVX.setData(self.qclayers.xPoints,self.qclayers.xVX)
            self.curveVX.setPen(QPen(Qt.magenta, 1, Qt.DashDotLine))
            if settings.antialiased:
                self.curveVX.setRenderHint(Qwt.QwtPlotItem.RenderAntialiased)
            self.curveVX.attach(self.quantumCanvas)
        else:
            try:
                self.curveVX.detach()
            except (AttributeError, RuntimeError):
                pass

        #plot Light Hole Valence Band
        if self.plotLH:
            self.curveLH = Qwt.QwtPlotCurve()
            self.curveLH.setData(self.qclayers.xPoints,self.qclayers.xVLH)
            self.curveLH.setPen(QPen(Qt.black, 1))
            if settings.antialiased:
                self.curveLH.setRenderHint(Qwt.QwtPlotItem.RenderAntialiased)
            self.curveLH.attach(self.quantumCanvas)
        else:
            try:
                self.curveLH.detach()
            except (AttributeError, RuntimeError):
                pass

        #plot Split Off Valence Band
        if self.plotSO:
            self.curveSO = Qwt.QwtPlotCurve()
            self.curveSO.setData(self.qclayers.xPoints,self.qclayers.xVSO)
            self.curveSO.setPen(QPen(Qt.red, 1, Qt.DashLine))
            if settings.antialiased:
                self.curveSO.setRenderHint(Qwt.QwtPlotItem.RenderAntialiased)
            self.curveSO.attach(self.quantumCanvas)
        else:
            try:
                self.curveSO.detach()
            except (AttributeError, RuntimeError):
                pass

        #highlight selected layer & make AR layers bold
        try:
            self.curveSelection.detach()
        except AttributeError:
            #self.curveSelection has not yet been formed
            pass       
        except RuntimeError:
            #self.curveSelection deleted with self.quantumCanvas.clear()        
            pass
        if self.qclayers.layerSelected >= 0 and \
                self.qclayers.layerSelected < self.qclayers.layerWidth.size:
            mask = ~np.isnan(self.qclayers.xARs)
            self.curveAR = SupportClasses.MaskedCurve(
                    self.qclayers.xPoints,self.qclayers.xARs,mask)
            self.curveAR.setPen(QPen(Qt.black, 2))
            if settings.antialiased:
                self.curveAR.setRenderHint(Qwt.QwtPlotItem.RenderAntialiased)
            self.curveAR.attach(self.quantumCanvas)

            mask = ~np.isnan(self.qclayers.xLayerSelected)
            self.curveSelection = SupportClasses.MaskedCurve(
                    self.qclayers.xPoints,
                    self.qclayers.xLayerSelected, mask)
            self.curveSelection.setPen(QPen(Qt.blue, 1.5))
            if settings.antialiased:
                self.curveSelection.setRenderHint(Qwt.QwtPlotItem.RenderAntialiased)
            self.curveSelection.attach(self.quantumCanvas)

        #plot wavefunctions
        #TODO color it between zero and the function
        if self.plotDirty and hasattr(self.qclayers, 'EigenE'):
            self.plotDirty=False
            self.curveWF = []
            for q in xrange(self.qclayers.EigenE.size):
                mask = ~np.isnan(self.qclayers.xyPsiPsi[:,q])
                curve = SupportClasses.MaskedCurve(
                        self.qclayers.xPointsPost,
                        self.qclayers.xyPsiPsi[:,q] + self.qclayers.EigenE[q],
                        mask)
                r,g,b = self.colors[np.mod(q,13)]
                curve.setPen(QPen(QColor(r,g,b), 2))
                curve.setRenderHint(Qwt.QwtPlotItem.RenderAntialiased)
                self.curveWF.append(curve)
                curve.attach(self.quantumCanvas)

        self.quantumCanvas.setAxisTitle(Qwt.QwtPlot.xBottom, u'Position (\u212B)')
        self.quantumCanvas.setAxisTitle(Qwt.QwtPlot.yLeft, 'Energy (eV)')
        self.quantumCanvas.replot()
        self.zoomer.setZoomBase()

    def create_zoomer(self):
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.zoomer = Qwt.QwtPlotZoomer(
            Qwt.QwtPlot.xBottom,
            Qwt.QwtPlot.yLeft,
            Qwt.QwtPicker.DragSelection,
            Qwt.QwtPicker.AlwaysOff,
            self.quantumCanvas.canvas())
        self.zoomer.setEnabled(False)
        #self.zoomer.setRubberBandPen(QPen(Qt.green))
        pattern = [
            Qwt.QwtEventPattern.MousePattern(Qt.LeftButton,
                                             Qt.NoModifier),
            Qwt.QwtEventPattern.MousePattern(Qt.MidButton,
                                             Qt.NoModifier),
            Qwt.QwtEventPattern.MousePattern(Qt.RightButton,
                                             Qt.NoModifier),
            Qwt.QwtEventPattern.MousePattern(Qt.LeftButton,
                                             Qt.ShiftModifier),
            Qwt.QwtEventPattern.MousePattern(Qt.MidButton,
                                             Qt.ShiftModifier),
            Qwt.QwtEventPattern.MousePattern(Qt.RightButton,
                                             Qt.ShiftModifier),
            ]
        self.zoomer.setMousePattern(pattern)

        self.picker = Qwt.QwtPlotPicker(
            Qwt.QwtPlot.xBottom,
            Qwt.QwtPlot.yLeft,
            Qwt.QwtPicker.PointSelection | Qwt.QwtPicker.DragSelection,
            Qwt.QwtPlotPicker.CrossRubberBand,
            Qwt.QwtPicker.AlwaysOn,
            self.quantumCanvas.canvas())
        self.picker.setRubberBandPen(QPen(Qt.green))
        self.picker.setTrackerPen(QPen(Qt.black))
        self.picker.connect(self.picker, 
                SIGNAL('selected(const QwtDoublePoint&)'), self.ginput)
        self.picker.setEnabled(False)

        self.picker2 = Qwt.QwtPlotPicker(
            Qwt.QwtPlot.xBottom,
            Qwt.QwtPlot.yLeft,
            Qwt.QwtPicker.PointSelection | Qwt.QwtPicker.DragSelection,
            Qwt.QwtPlotPicker.NoRubberBand,
            Qwt.QwtPicker.AlwaysOff,
            self.quantumCanvas.canvas())
        #self.picker2.setRubberBandPen(QPen(Qt.green))
        self.picker2.setTrackerPen(QPen(Qt.black))
        self.picker2.connect(self.picker2, 
                SIGNAL('selected(const QwtDoublePoint&)'), self.hinput)
        self.picker2.setEnabled(False)

        self.panner = Qwt.QwtPlotPanner(self.quantumCanvas.canvas())
        self.panner.setEnabled(False)

        self.zoom(False)

    def well_select(self, on):
        """ SLOT connected to self.wellSelectButton.toggled(bool) 
        Prepare for well selection."""
        if on:
            self.pairSelectButton.setChecked(False)
            self.panButton.setChecked(False)
            self.zoomButton.setChecked(False)
            self.picker2.setEnabled(True)
            self.quantumCanvas.canvas().setCursor(Qt.PointingHandCursor)
        else:
            self.picker2.setEnabled(False)
            self.quantumCanvas.canvas().setCursor(Qt.ArrowCursor)

    def zoom(self, on):
        if on:
            self.pairSelectButton.setChecked(False)
            self.wellSelectButton.setChecked(False)
            self.panButton.setChecked(False)
            self.zoomer.setEnabled(True)
            self.quantumCanvas.canvas().setCursor(Qt.CrossCursor)
        else:
            self.zoomer.setEnabled(False)
            self.quantumCanvas.canvas().setCursor(Qt.ArrowCursor)

    def zoom_out(self):
        """Auto scale and clear the zoom stack
        """
        self.pairSelectButton.setChecked(False)
        self.wellSelectButton.setChecked(False)
        self.zoomButton.setChecked(False)
        self.panButton.setChecked(False)
        self.quantumCanvas.setAxisAutoScale(Qwt.QwtPlot.xBottom)
        self.quantumCanvas.setAxisAutoScale(Qwt.QwtPlot.yLeft)
        self.quantumCanvas.replot()
        self.zoomer.setZoomBase()

    def pan(self, on):
        if on:
            self.pairSelectButton.setChecked(False)
            self.wellSelectButton.setChecked(False)
            self.zoomButton.setChecked(False)
            self.quantumCanvas.setCursor(Qt.OpenHandCursor)
            self.panner.setEnabled(True)
            self.quantumCanvas.canvas().setCursor(Qt.OpenHandCursor)
        else:
            self.panner.setEnabled(False)
            self.quantumCanvas.canvas().setCursor(Qt.ArrowCursor)

    def clear_WFs(self):
        self.plotDirty = False
        delattr(self.qclayers,'EigenE')
        self.quantumCanvas.clear()
        self.update_quantumCanvas()




#===============================================================================
# General Menu Functions
#===============================================================================

    def change_main_tab(self, tabIdx):
        self.menuBar().clear()
        if tabIdx == 0:
            self.create_Quantum_menu()
        elif tabIdx == 1:
            self.create_Optical_menu()
        elif tabIdx == 2:
            pass
        else:
            assert 1==2

    def add_actions(self, target, actions):
        for action in actions:
            if action is None:
                target.addSeparator()
            else:
                target.addAction(action)

    def create_action(self, text, slot=None, shortcut=None, 
                        icon=None, tip=None, checkable=False, 
                        signal="triggered()", ischecked=False):
        action = QAction(text, self)
        if icon is not None:
            action.setIcon(QIcon("images/%s.png" % icon))
        if shortcut is not None:
            action.setShortcut(shortcut)
        if tip is not None:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot is not None:
            self.connect(action, SIGNAL(signal), slot)
        if checkable:
            action.setCheckable(True)
        if ischecked:
            action.setChecked(True)
        return action

    def create_Quantum_menu(self):
        #file menu
        self.file_menu = self.menuBar().addMenu("&File")
        newFileAction      = self.create_action("&New...", 
                self.fileNew, QKeySequence.New, 
                "filenew", "New ErwinJr file")
        openFileAction     = self.create_action("&Open", 
                shortcut="Ctrl+O", slot=self.fileOpen, 
                tip="Open ErwinJr file", icon="fileopen")
        saveFileAction     = self.create_action("&Save", 
                shortcut="Ctrl+S", slot=self.fileSave, 
                tip="Save ErwinJr file", icon="filesave")
        saveAsFileAction   = self.create_action("S&ave As", 
                shortcut="Ctrl+W", slot=self.fileSaveAs, 
                tip="Save ErwinJr file as", icon="filesaveas")
        exportQuantumCanvasAction = self.create_action("Export Band Diagram Image", 
                slot=self.export_quantumCanvas, 
                tip="Export Band Diagram Image")
        exportBandCSVAction = self.create_action("Export Band Diagram Data", 
                slot=self.export_band_diagram_data, 
                tip="Export Band Diagram Data")
        quit_action = self.create_action("&Quit", 
                slot=self.close, shortcut="Ctrl+Q", 
                tip="Close the application", icon="filequit")
        self.fileMenuActions = (newFileAction, openFileAction, 
                saveFileAction, saveAsFileAction, None, 
                exportBandCSVAction, exportQuantumCanvasAction, None, 
                quit_action)
        self.connect(self.file_menu, SIGNAL("aboutToShow()"), 
                self.updateFileMenu)
        #  self.add_actions(self.file_menu, 
                #  (newFileAction, openFileAction, 
                    #  saveFileAction, saveAsFileAction, None, quit_action))

        #edit menu
        self.edit_menu = self.menuBar().addMenu("&Edit")
        temperatureAction = self.create_action("&Temperature", 
                slot=self.set_temperature, tip="Set temperature")
        bumpLayerAction = self.create_action("&Bump First Layer", 
                slot=self.bump_first_layer, 
                tip="Move zeroth layer to first layer")
        copyStructureAction = self.create_action("&Copy Structure", 
                slot=self.copy_structure, 
                tip="Copy Layer Structure to Clipboard")
        self.add_actions(self.edit_menu, 
                (temperatureAction, bumpLayerAction, None, copyStructureAction))

        #view menu
        self.view_menu = self.menuBar().addMenu("&View")
        VXBandAction = self.create_action("X Valley Conduction Band", 
                checkable=True, ischecked=self.plotVX, slot=self.view_VXBand)
        VLBandAction = self.create_action("L Valley Conduction Band", 
                checkable=True, ischecked=self.plotVL, slot=self.view_VLBand)
        LHBandAction = self.create_action("Light Hole Valence Band", 
                checkable=True, ischecked=self.plotLH, slot=self.view_LHBand)
        SOBandAction = self.create_action("Split Off Valence Band", 
                checkable=True, ischecked=self.plotSO, slot=self.view_SOBand)
        self.add_actions(self.view_menu, 
                (VXBandAction,VLBandAction,LHBandAction,SOBandAction))        

        #help menu
        self.help_menu = self.menuBar().addMenu("&Help")
        about_action = self.create_action("&About",shortcut='F1', 
                slot=self.on_about)
        licenses_action = self.create_action("&License", 
                slot=self.on_licenses)
        tutorialAction = self.create_action("&Tutorial", 
                slot=self.on_tutorial)
        self.add_actions(self.help_menu, 
                (tutorialAction,about_action,licenses_action))

    def create_Optical_menu(self):
        #file menu
        self.file_menu = self.menuBar().addMenu("&File")
        newFileAction      = self.create_action("&New...", 
                self.fileNew, QKeySequence.New, 
                "filenew", "New ErwinJr file")
        openFileAction     = self.create_action("&Open", 
                shortcut="Ctrl+O", slot=self.fileOpen, 
                tip="Open ErwinJr file", icon="fileopen")
        saveFileAction     = self.create_action("&Save", 
                shortcut="Ctrl+S", slot=self.fileSave, 
                tip="Save ErwinJr file", icon="filesave")
        saveAsFileAction   = self.create_action("S&ave As", 
                shortcut="Ctrl+W", slot=self.fileSaveAs, 
                tip="Save ErwinJr file as", icon="filesaveas")
        quit_action = self.create_action("&Quit", 
                slot=self.close, shortcut="Ctrl+Q", 
                tip="Close the application", icon="filequit")
        self.fileMenuActions = (newFileAction, openFileAction, 
                saveFileAction, saveAsFileAction, None, quit_action)
        self.connect(self.file_menu, SIGNAL("aboutToShow()"), 
                self.updateFileMenu)
        #self.add_actions(self.file_menu, (newFileAction, openFileAction, saveFileAction, saveAsFileAction, None, quit_action))

        #help menu
        self.help_menu = self.menuBar().addMenu("&Help")
        about_action = self.create_action("&About",shortcut='F1', slot=self.on_about)
        licenses_action = self.create_action("&License", slot=self.on_licenses)
        tutorialAction = self.create_action("&Tutorial", slot=self.on_tutorial)
        self.add_actions(self.help_menu, (tutorialAction,about_action,licenses_action))




#===============================================================================
# File Menu Items
#===============================================================================

    def updateFileMenu(self):
        self.file_menu.clear()
        self.add_actions(self.file_menu, self.fileMenuActions[:-1])
        current = (QString(self.filename)
                   if self.filename is not None else None)
        recentFiles = []
        for fname in self.recentFiles:
            if fname != current and QFile.exists(fname):
                recentFiles.append(fname)
        if recentFiles:
            self.file_menu.addSeparator()
            for i, fname in enumerate(recentFiles):
                action = QAction(
                        "&{0}  {1}".format(i + 1, QFileInfo(
                        fname).fileName()), self)
                action.setData(QVariant(fname))
                self.connect(action, SIGNAL("triggered()"),
                             partial(self.fileOpen,fname))
                self.file_menu.addAction(action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.fileMenuActions[-1])

    def addRecentFile(self, fname):
        if fname is None:
            return
        if not self.recentFiles.contains(fname):
            self.recentFiles.prepend(QString(fname))
            while self.recentFiles.count() > 9:
                self.recentFiles.takeLast()

    def loadInitialFile(self):
        qsettings = QSettings()
        fname = unicode(qsettings.value("LastFile").toString())
        if fname and QFile.exists(fname):
            if fname.split('.')[-1] == 'qcl':
                self.qclLoad(fname)

            self.zoomer.zoom(0)
            self.quantumCanvas.clear()
            self.update_Lp_limits()
            self.update_inputBoxes()
            self.layerTable_refresh()
            self.qclayers.populate_x()

            self.strata.populate_rIndexes()
            self.update_stratum_inputBoxes()
            self.stratumTable_refresh()
            self.opticalCanvas.clear()
            self.update_opticalCanvas()

        self.filename = fname
        self.addRecentFile(fname)
        self.dirty = False
        self.update_windowTitle()       

    def fileNew(self):
        if not self.okToContinue():
            return False

        self.filename = None
        self.plotDirty = False
        self.quantumCanvas.clear()
        self.opticalCanvas.clear()
        self.optimization1DCanvas.clear()

        self.qclayers = QCLayers()
        self.strata = Strata()

        self.zoomer.zoom(0)

        self.update_Lp_limits()
        self.update_inputBoxes()
        self.layerTable_refresh()
        self.qclayers.populate_x()

        self.layerTable_refresh()
        self.layerTable.selectRow(1)
        self.layerTable.setFocus()

        self.update_stratum_inputBoxes()

        self.update_opticalCanvas()
        self.stratumTable_refresh()

        self.dirty = False
        self.update_windowTitle()

        return True

    def okToContinue(self):
        if self.dirty:
            reply = QMessageBox.question(self, 
                    "ErwinJr " + str(majorVersion) + " - Unsaved Changes", 
                    "Save unsaved changes?", 
                    QMessageBox.Yes|QMessageBox.No|QMessageBox.Cancel)
            if reply == QMessageBox.Cancel:
                return False
            elif reply == QMessageBox.Yes:
                self.fileSave()
        return True

    def update_windowTitle(self):
        if self.filename is not None:
            self.setWindowTitle("ErwinJr " + str(majorVersion) + 
                    " - %s[*]" % os.path.basename(str(self.filename)))
        else:
            self.setWindowTitle("ErwinJr " + str(majorVersion) + "[*]")
        self.setWindowModified(self.dirty)

    def fileOpen(self, fname = None):
        #if not self.okToContinue():
        #    return False

        #clear all old data, also calls self.okToContinue()
        if not self.fileNew(): 
            return False
        if fname is None:
            dir = os.path.dirname(str(self.filename)) if self.filename else "."
            fname =unicode(QFileDialog.getOpenFileName(self,
                "ErwinJr - Choose file", dir, 
                "ErwinJr files (*.qcl)\nAll files (*.*)"))
        #open file and determine if it is from the Matlab version of ErwinJr
        filehandle = open(fname, 'r')
        firstLine = filehandle.readline()
        filehandle.close()
        if fname:
            if firstLine.split(':')[0] == 'Description':
                self.qclPtonLoad(fname)
            elif firstLine == 'ErwinJr Data File' + self.newLineChar:
                self.qclLoad(fname)
            else:
                QMessageBox.warning(self,'ErwinJr Error',
                        'Could not recognize input file.')
                return
            self.zoomer.zoom(0)
            self.quantumCanvas.clear()
            self.update_Lp_limits()
            self.update_inputBoxes()
            self.layerTable_refresh()
            self.qclayers.populate_x()

            #if firstLine == 'ErwinJr Data File\n':
            self.strata.populate_rIndexes()
            self.update_stratum_inputBoxes()
            self.stratumTable_refresh()
            self.opticalCanvas.clear()
            self.update_opticalCanvas()

        self.filename = fname
        self.addRecentFile(fname)
        self.dirty = False
        self.update_windowTitle()

        return True

    def qclPtonLoad(self, fname):
        """Legacy load: No longer updated and supported since Ver 3.0.0"""
        try:
            filehandle = open(fname, 'r')
            self.qclayers.description = filehandle.readline().split(':')[1].strip()
            self.qclayers.EField  = float(
                    filehandle.readline().split(':')[1].strip())
            self.qclayers.xres    = float(
                    filehandle.readline().split(':')[1].strip())
            self.qclayers.vertRes = float(
                    filehandle.readline().split(':')[1].strip())
            self.qclayers.moleFrac[0] = float(
                    filehandle.readline().split(':')[1].strip())
            self.qclayers.moleFrac[1] = float(
                    filehandle.readline().split(':')[1].strip())
            self.qclayers.moleFrac[2] = float(
                    filehandle.readline().split(':')[1].strip())
            self.qclayers.moleFrac[3] = float(
                    filehandle.readline().split(':')[1].strip())
            self.qclayers.solver = filehandle.readline().split(':')[1].strip()
            self.qclayers.Temperature = float(
                    filehandle.readline().split(':')[1].strip())
            self.qclayers.TempFoM = float(
                    filehandle.readline().split(':')[1].strip())
            self.qclayers.repeats = int(
                    filehandle.readline().split(':')[1].strip())
            self.qclayers.diffLength  = float(
                    filehandle.readline().split(':')[1].strip())

            filehandle.readline() #throw the column description line away
            lines = filehandle.readlines()
            rows = len(lines)
            self.qclayers.layerWidth = np.empty(rows, dtype=np.int_)
            for item in ('layerBarriers', 'layerARs', 
                    'layerDopings', 'layerMaterials', 'layerDividers'):
                setattr(self.qclayers, item, np.zeros(rows))
            for q, line in enumerate(lines):
                line = line.split('\t')
                self.qclayers.layerWidth[q]       = int(np.round(float(line[1])
                                                       /self.qclayers.xres))
                self.qclayers.layerBarriers[q]  = float(line[2])
                self.qclayers.layerARs[q]       = float(line[3])
                self.qclayers.layerMaterials[q] = float(line[4])
                self.qclayers.layerDopings[q]   = float(line[5])
                self.qclayers.layerDividers[q]  = float(line[6])
            self.qclayers.layerMaterials[np.nonzero(
                self.qclayers.layerMaterials == 4)[0]] = 1
            self.qclayers.layerMaterials[np.nonzero(
                self.qclayers.layerMaterials == 5)[0]] = 2

            filehandle.close()

            self.bump_first_layer()
        except Exception as err:
            QMessageBox.warning(self,"ErwinJr - Warning",
                             "Could not load *.qcl file.\n"+str(err))

    def qclLoad(self, fname):
        #  print "Loading "+fname
        try:
            with open(fname, 'r') as f:
                SaveLoad.qclLoad(f, self.qclayers, self.strata)
        except Exception as err:
            QMessageBox.warning(self,"ErwinJr - Warning",
                             "Could not load *.qcl file.\n"+str(err))

    def fileSave(self):
        if self.filename is None:
            return self.fileSaveAs()
        else:
            #os.path.extsep
            if self.filename.split('.')[-1] == 'qcl':
                if self.qclSave(self.filename):
                    self.dirty = False
                    self.update_windowTitle()
                    return True
                else:
                    return False
            else:
                raise IOError('The *.' + self.filename.split('.')[-1] + 
                        ' extension is not supported.')
                return False

    def fileSaveAs(self):
        fname = self.filename if self.filename is not None else "."
        typeString = "ErwinJr 2.x file (*.qcl)\nAll files (*.*)"
        fname = unicode(QFileDialog.getSaveFileName(self,
            "ErwinJr - Save File", QString(fname), typeString))
        if fname:
            if "." not in fname:
                fname += ".qcl"
            self.addRecentFile(fname)
            self.filename = fname
            return self.fileSave()
        return False

    def qclSave(self, fname):
        try: 
            with open(fname, 'w') as f:
                f.write("ErwinJr Data File\n")
                f.write("Version:" + str(ejVersion) + '\n')
                SaveLoad.qclSave(f, self.qclayers, self.strata)
        except Exception as err:
            QMessageBox.warning(self,"ErwinJr - Warning",
                             "Could not save *.qcl file.\n"+str(err))
        return True

    #  def qclPtonSave(self, fname):
        #  filehandle = open(fname, 'w')
        #  filehandle.write("Description:" + self.qclayers.description + '\n')
        #  filehandle.write("Efield:" + str(self.qclayers.EField) + '\n')
        #  filehandle.write("xres:" + str(self.qclayers.xres) + '\n')
        #  filehandle.write("Eres:" + str(self.qclayers.vertRes) + '\n')
        #  filehandle.write("InGaAsx:" + str(self.qclayers.moleFrac[0]) + '\n')
        #  filehandle.write("AlInAsx:" + str(self.qclayers.moleFrac[1]) + '\n')
        #  filehandle.write("InGaAsx2:" + str(self.qclayers.moleFrac[2]) + '\n')
        #  filehandle.write("AlInAsx2:" + str(self.qclayers.moleFrac[3]) + '\n')
        #  filehandle.write("Solver:" + self.qclayers.solver + '\n')
        #  filehandle.write("Temp:" + str(self.qclayers.Temp) + '\n')
        #  filehandle.write("TempFoM:" + str(self.qclayers.TempFoM) + '\n')
        #  filehandle.write("PlotPeriods:" + str(self.qclayers.repeats) + '\n')
        #  filehandle.write("DiffLeng:" + str(self.qclayers.diffLength) + '\n')

        #  filehandle.write("regionNum\twellWdiths\tbarrierSwitch\tarSwitch\tmaterial\tdoping\tdivider\n")
        #  for row in xrange(self.qclayers.layerWidth.size):
            #  string = "%d\t%f\t%d\t%d\t%d\t%f\t%d\n" % (row+1, 
                    #  self.qclayers.xres * self.qclayers.layerWidth[row], 
                    #  self.qclayers.layerBarriers[row], 
                    #  self.qclayers.layerARs[row], 
                    #  self.qclayers.layerMaterials[row], 
                    #  self.qclayers.layerDopings[row], 
                    #  self.qclayers.layerDividers[row])
            #  filehandle.write(string)

        #  filehandle.close()
        #  return True

    def closeEvent(self, event):
        if self.okToContinue():
            qsettings = QSettings()
            filename = QVariant(QString(self.filename)) if self.filename \
                    else QVariant()
            qsettings.setValue("LastFile", filename)
            recentFiles = QVariant(self.recentFiles) if self.recentFiles \
                    else QVariant()
            qsettings.setValue("RecentFiles", recentFiles)
            qsettings.setValue("MainWindow/Geometry", QVariant(self.saveGeometry()))
            qsettings.setValue("MainWindow/State", QVariant(self.saveState()))
        else:
            event.ignore()




#===============================================================================
# Export Functions
#===============================================================================

    def export_quantumCanvas(self):
        fname = unicode(QFileDialog.getSaveFileName(self,
            "ErwinJr - Export Band Structure Image",
            self.filename.split('.')[0], 
            "Portable Network Graphics file (*.png)"))
        if not fname:
            return

        try:
            self.curveAR.detach()
            self.curveSelection.detach()
            self.quantumCanvas.replot()
        except:
            pass

        #set background color to white and save presets
        bgColor = self.quantumCanvas.canvasBackground()
        bgRole = self.mainTabWidget.backgroundRole()
        self.mainTabWidget.setBackgroundRole(QPalette.Base)
        self.quantumWidget.setBackgroundRole(QPalette.Base)
        self.quantumCanvas.setCanvasBackground(Qt.white)
        self.quantumCanvas.setAutoFillBackground(True)

        #save image
        QPixmap.grabWidget(self.quantumCanvas).save(fname+'.png', 'PNG')

        self.quantumWidget.setBackgroundRole(QPalette.Window)
        self.quantumCanvas.setCanvasBackground(bgColor)
        self.mainTabWidget.setBackgroundRole(bgRole)

        try:
            self.curveAR.attach(self.quantumCanvas)
            self.curveSelection.attach(self.quantumCanvas)
            self.quantumCanvas.replot()
        except:
            pass

    def export_band_diagram_data(self):
        fname = unicode(QFileDialog.getSaveFileName(self,
            "ErwinJr - Export Band Structure Data",
            self.filename.split('.')[0], 
            "Comma-Separated Value file (*.csv)"))
        if fname != '': #if user doesn't click cancel
            # TODO: savetxt is not defined
            savetxt(fname.split('.')[0] + '_CB' + '.csv', 
                    np.column_stack([self.qclayers.xPoints,self.qclayers.xVc]), 
                    delimiter=',')

            try: self.qclayers.xyPsiPsi
            except AttributeError: pass #band structure hasn't been solved yet
            else:
                xyPsiPsiEig = np.zeros(self.qclayers.xyPsiPsi.shape)
                for q in xrange(self.qclayers.EigenE.size):
                    xyPsiPsiEig[:,q] = self.qclayers.xyPsiPsi[:,q] + \
                            self.qclayers.EigenE[q]
                savetxt(fname.split('.')[0] + '_States' + '.csv', 
                        np.column_stack([self.qclayers.xPointsPost, xyPsiPsiEig]), 
                        delimiter=',')




#===============================================================================
# Edit Menu Items
#===============================================================================

    def bump_first_layer(self):
        self.qclayers.layerWidth = np.insert(self.qclayers.layerWidth, 
                0, self.qclayers.layerWidth[-1])
        self.qclayers.layerBarriers = np.insert(self.qclayers.layerBarriers, 
                0, self.qclayers.layerBarriers[-1])
        self.qclayers.layerARs = np.insert(self.qclayers.layerARs, 
                0, self.qclayers.layerARs[-1])
        self.qclayers.layerMaterials = np.insert(self.qclayers.layerMaterials, 
                0, self.qclayers.layerMaterials[-1])
        self.qclayers.layerDopings = np.insert(self.qclayers.layerDopings, 
                0, self.qclayers.layerDopings[-1])
        self.qclayers.layerDividers = np.insert(self.qclayers.layerDividers, 
                0, self.qclayers.layerDividers[-1])

        self.update_inputBoxes()
        self.layerTable_refresh()
        self.layerTable.setCurrentCell(1,0)
        self.layerTable.setFocus()

        self.dirty = True
        self.update_windowTitle()

    def set_temperature(self):
        nowTemp = cst.Temperature
        newTemp, buttonResponse = QInputDialog.getDouble(self, 
                'ErwinJr Input Dialog', 'Set Temperature', 
                value=nowTemp, min=0)
        if buttonResponse:
            cst.set_temperature(newTemp)
            self.qclayers.Temperature = newTemp
            self.qclayers.populate_x()
            self.qclayers.populate_x_band()
            self.update_quantumCanvas()

    def copy_structure(self):
        clipboard = QApplication.clipboard()
        string = ''
        for layer in self.qclayers.layerWidth[1:]:
            string += '%g\n' % (layer*self.qclayers.xres)
        clipboard.setText(string)




#===============================================================================
# View Menu Items
#===============================================================================

    def view_VXBand(self):
        if self.plotVX:
            self.plotVX = False
        else:
            self.plotVX = True
        self.plotDirty = True
        self.update_quantumCanvas()

    def view_VLBand(self):
        if self.plotVL:
            self.plotVL = False
        else:
            self.plotVL = True
        self.plotDirty = True
        self.update_quantumCanvas()

    def view_LHBand(self):
        if self.plotLH:
            self.plotLH = False
        else:
            self.plotLH = True
        self.plotDirty = True
        self.update_quantumCanvas()

    def view_SOBand(self):
        if self.plotSO:
            self.plotSO = False
        else:
            self.plotSO = True
        self.plotDirty = True
        self.update_quantumCanvas()




#===============================================================================
# Help Menu Items
#===============================================================================

    def on_about(self):
        msg = """ ErwinJr 2.x Authors and Contributors

         * Kale J. Franz, PhD (Jet Propulsion Laboratory)
            kfranz@alumni.princeton.edu
            www.kalefranz.com

With contributions from:
         * Yamac Dikmelik (Johns Hopkins University)
         * Yu Song (Princeton University)
        """
        QMessageBox.about(self, "ErwinJr " + str(ejVersion), msg.strip())

    def on_licenses(self):
        copyright1 = """
#=======================================
# ErwinJr is a simulation program for quantum semiconductor lasers.
# Copyright (C) 2012 Kale J. Franz, PhD
#
# A portion of this code is Copyright (c) 2011, California Institute of 
# Technology ("Caltech"). U.S. Government sponsorship acknowledged.
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#=======================================
"""
        QMessageBox.about(self, "ErwinJr " + str(ejVersion), copyright1.strip())

    def on_tutorial(self):
        if os.name == "nt":
            os.startfile("tutorial.pdf")
        elif os.name == "posix":
            os.system("/usr/bin/xdg-open tutorial.pdf")  





def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("JPL")
    app.setOrganizationDomain("erwinjr.org")
    app.setApplicationName("ErwinJr")
    qsettingsSystem = QSettings(QSettings.SystemScope,"JPL","ErwinJr")
    installDirectory = str(qsettingsSystem.value('installDirectory').toString())
    if installDirectory:
        os.chdir(installDirectory)

    # Create and display the splash screen
    splash_pix = QPixmap('images/erwinjr_splash.png')
    splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    splash.setMask(splash_pix.mask())
    splash.show()
    app.processEvents()

    time.sleep(1)

    app.setWindowIcon(QIcon('images/EJpng48x48.png'))

    #this block handles a filename passed in by command line
    try:
        fileName = sys.argv[1]
        name, ext = os.path.splitext(fileName)
        assert ext == ".qcl"
        assert os.path.exists(fileName)
        fileName = os.path.abspath(fileName)
    except (IndexError, AssertionError):
        fileName = None

    form = MainWindow(fileName)
    form.show()
    splash.finish(form)

    # Import Psyco if available
    #  try:
        #  import psyco
        #  psyco.full()
    #  except ImportError:
        #  noPsycoBox = QMessageBox(QMessageBox.Question, 'EwrinJr '+str(majorVersion), "Psyco could not be loaded.\nExecution will be slowed.")
        #  noPsycoBox.exec_()

    qsettings = QSettings()
    if not qsettings.value('firstRun').toInt()[1]:
        if not installDirectory:
            qsettingsSystem.setValue("installDirectory", QVariant(os.getcwd()))
        firstRunBox = QMessageBox(QMessageBox.Question, 
                'EwrinJr '+str(majorVersion), 
                ("Welcome to ErwinJr!\n" 
                "Since this is your first time running the program, "
                "would you like to open an example file or a blank file?"),
            parent=form)
        firstRunBox.addButton("Blank File", QMessageBox.NoRole)
        firstRunBox.addButton("Example File", QMessageBox.YesRole)
        ansr =firstRunBox.exec_()
        if ansr:
            form.fileOpen('examples/NPhoton PQLiu.qcl')
        else:
            form.fileNew()
        qsettings.setValue("firstRun", 1)


    app.exec_()

if __name__ == "__main__":
    main()

# vim: ts=4 sw=4 sts=4 expandtab