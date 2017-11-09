#!/usr/bin/env python2
# -*- coding:utf-8 -*-

#============================================================================
# ErwinJr is a simulation program for quantum semiconductor lasers.
# Copyright (C) 2017 Ming Lyu (CareF)
#
# The EJplotControl class of this code is inspired by
# matplotlib.backend_qt5.NavigationToolbar2QT
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
#============================================================================
import matplotlib
matplotlib.use('Qt4Agg')
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4 import cursord
from matplotlib.backend_bases import NavigationToolbar2
from matplotlib.figure import Figure

from PyQt4.QtCore import *
from PyQt4.QtGui import *

import numpy as np
import six
import os
from functools import partial

class EJcanvas(FigureCanvas):
#  class EJcanvas(FigureCanvas, NavigationToolbar2):
    def __init__(self, xlabel='x', ylabel='y', parent=None): 
        self.figure = Figure()
        super(EJcanvas, self).__init__(self.figure)
        #  NavigationToolbar2.__init__(self, self)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.updateGeometry()
        self.axes = self.figure.add_subplot(111)
        self.xlabel = xlabel
        self.ylabel = ylabel

    def set_axes(self, fsize=12): 
        self.axes.autoscale(enable=True, axis='x', tight=True)
        self.axes.autoscale(enable=True, axis='y', tight=False)
        self.axes.spines['top'].set_color('none')
        self.axes.spines['right'].set_color('none')
        self.axes.spines['bottom'].set_position(('outward', 5))
        self.axes.set_xlabel(self.xlabel, fontsize=fsize)
        self.axes.spines['left'].set_position(('outward', 5))
        self.axes.set_ylabel(self.ylabel, fontsize=fsize)

    def test(self):
        x = np.linspace(0, 10, 100)
        self.axes.plot(x,np.sin(x))

    def resizeEvent(self, event):
        super(EJcanvas, self).resizeEvent(event)
        height = self.figure.get_figheight()
        width = self.figure.get_figwidth()
        self.figure.subplots_adjust(left=0.75/width, bottom=0.55/height, 
                right=1-0.12/width,top=1-0.09/height, wspace=0,hspace=0)

    def clear(self):
        #  print "clear"
        self.axes.clear()
        self.set_axes()
        #  self.draw()



class EJplotControl(NavigationToolbar2, QObject): 
    """This class is mostly copied from matplotlib.backend_qt5, excpet for no
    longer necessary for any GUI"""
    message = Signal(str)

    def __init__(self, canvas, parent):
        QObject.__init__(self, parent)
        self.canvas = canvas
        self._actions = {}
        self.custom_action = {}

        NavigationToolbar2.__init__(self, canvas)

    def _init_toolbar(self):
        pass
        #  for text, tooltip_text, image_file, callback in self.toolitems:
            #  if text is None:
                #  self.addSeparator()
            #  else:
                #  a = self.addAction(self._icon(image_file + '.png'),
                                   #  text, getattr(self, callback))
                #  self._actions[callback] = a
                #  if callback in ['zoom', 'pan']:
                    #  a.setCheckable(True)
                #  if tooltip_text is not None:
                    #  a.setToolTip(tooltip_text)
                #  if text == 'Subplots':
                    #  a = self.addAction(self._icon("qt4_editor_options.png"),
                                       #  'Customize', self.edit_parameters)
                    #  a.setToolTip('Edit axis, curve and image parameters')

        #  self.buttons = {}

    def set_action(self, callback, button):
        """
        According to matplotlib.backend_bases, supported actions are:
        toolitems = (
            ('Home', 'Reset original view', 'home', 'home'),
            ('Back', 'Back to  previous view', 'back', 'back'),
            ('Forward', 'Forward to next view', 'forward', 'forward'),
            (None, None, None, None),
            ('Pan', 'Pan axes with left mouse, zoom with right', 'move', 'pan'),
            ('Zoom', 'Zoom to rectangle', 'zoom_to_rect', 'zoom'),
            ('Subplots', 'Configure subplots', 'subplots', 'configure_subplots'),
            (None, None, None, None),
            ('Save', 'Save the figure', 'filesave', 'save_figure'),
          )
        format (text, tooltip_text, image_file, callback)
        """
        if callback in (self.toolitems[n][-1] for n in
                range(len(self.toolitems))):
            self.parent().connect(button, SIGNAL("clicked()"), 
                    getattr(self, callback))
            self._actions[callback] = button
            if callback in ['zoom', 'pan']:
                button.setCheckable(True)
        else: 
            raise TypeError("%s not supported."%callback)

    def set_custom(self, name, button, callback):
            """cusomized callback action, 
            s.t. this class manages the button's check status
            and its interaction with canvas. 
            Note that callback is called when clicke on canvas"""
            self.custom_action[name] = callback
            self._actions[name] = button
            button.setCheckable(True)
            # TODO Can this function become a decorator?

    def edit_parameters(self):
        allaxes = self.canvas.figure.get_axes()
        if not allaxes:
            QMessageBox.warning(
                self.parent(), "Error", "There are no axes to edit.")
            return
        elif len(allaxes) == 1:
            axes, = allaxes
        else:
            titles = []
            for axes in allaxes:
                name = (axes.get_title() or
                        " - ".join(filter(None, [axes.get_xlabel(),
                                                 axes.get_ylabel()])) or
                        "<anonymous {} (id: {:#x})>".format(
                            type(axes).__name__, id(axes)))
                titles.append(name)
            item, ok = QInputDialog.getItem(
                self.parent(), 'Customize', 'Select axes:', titles, 0, False)
            if ok:
                axes = allaxes[titles.index(six.text_type(item))]
            else:
                return

        figureoptions.figure_edit(axes, self)

    def _update_buttons_checked(self):
        # sync button checkstates to match active mode
        self._actions['pan'].setChecked(self._active == 'PAN')
        self._actions['zoom'].setChecked(self._active == 'ZOOM')
        for mode in self.custom_action: 
            self._actions[mode].setChecked(self._active == mode)

    def pan(self, *args):
        super(EJplotControl, self).pan(*args)
        self._update_buttons_checked()

    def zoom(self, *args):
        super(EJplotControl, self).zoom(*args)
        self._update_buttons_checked()

    def custom(self, mode):
        if self._active == mode: 
            self._active = None
        else:
            self._active = mode

        if self._idPress is not None:
            self._idPress = self.canvas.mpl_disconnect(self._idPress)
            self.mode = ''

        if self._idRelease is not None:
            self._idRelease = self.canvas.mpl_disconnect(self._idRelease)
            self.mode = ''

        if self._active:
            #  self._idPress = self.canvas.mpl_connect('button_press_event',
                                                    #  self.press[mode])
            self._idRelease = self.canvas.mpl_connect('button_release_event', 
                    self.custom_action[mode])
            self.mode = mode
            self.canvas.widgetlock(self)
        else:
            self.canvas.widgetlock.release(self)

        for a in self.canvas.figure.get_axes():
            a.set_navigate_mode(None)

        self.set_message(self.mode)
        self._update_buttons_checked()

    def set_message(self, s):
        self.message.emit(s)
        #  print s

    def set_cursor(self, cursor):
        self.canvas.setCursor(cursord[cursor])

    def draw_rubberband(self, event, x0, y0, x1, y1):
        height = self.canvas.figure.bbox.height
        y1 = height - y1
        y0 = height - y0
        rect = [int(val) for val in (x0, y0, x1 - x0, y1 - y0)]
        self.canvas.drawRectangle(rect)

    def remove_rubberband(self):
        self.canvas.drawRectangle(None)

    def save_figure(self, caption="Choose a filename to save to", 
            filename = None, default_filetype=None):
        filetypes = self.canvas.get_supported_filetypes_grouped()
        sorted_filetypes = sorted(six.iteritems(filetypes))
        #  if not default_filetype in self.canvas.get_supported_filetypes(): 
        if not default_filetype:
            default_filetype = self.canvas.get_default_filetype()

        if not filename:
            startpath = os.path.expanduser(
                matplotlib.rcParams['savefig.directory'])
            filename = os.path.join(startpath, self.canvas.get_default_filename())
        filters = []
        selectedFilter = None
        for name, exts in sorted_filetypes:
            exts_list = " ".join(['*.%s' % ext for ext in exts])
            filter = '%s (%s) ' % (name, exts_list)
            #  filter = '(*.%s) %s' % (exts_list, name)
            if default_filetype in exts:
                selectedFilter = filter
            filters.append(filter)
        filters = ';;'.join(filters)

        # for future update to pyqt5, change it to getSaveFileName
        fname, filter = QFileDialog.getSaveFileNameAndFilter(self.parent(),
                caption, filename, filters, selectedFilter)
        if fname:
            try:
                self.canvas.figure.savefig(six.text_type(fname), 
                        dpi=300, bbox_inches='tight')
            except Exception as e:
                QMessageBox.critical(
                    self.parent(), "Error saving band diagram", 
                    six.text_type(e), QMessageBox.Ok, QMessageBox.NoButton)

# vim: ts=4 sw=4 sts=4 expandtab