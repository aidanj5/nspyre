from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg

from nspyre.widgets.plotting import LinePlotWidget, HeatmapPlotWidget
from nspyre.widgets.splitter_widget import Splitter, SplitterOrientation
# from nspyre.utils import connect_to_master
from nspyre.mongo_listener import Synched_Mongo_Database
from nspyre.views import Spyrelet_Views
from nspyre.utils import cleanup_register, join_nspyre_path, custom_decode
from nspyre.widgets.image import ImageWidget
from nspyre.widgets.code_editor import Scintilla_Code_Editor, Monokai_Python_Lexer
import pymongo

import numpy as np
import pandas as pd
import time
import inspect
import traceback
import textwrap

class CustomView():
    def __init__(self, code_editor, w1D, w2D, plot_layout, initial_df, initial_cache):
        self.is_updating = False
        self.editor = code_editor
        self.plot_layout = plot_layout
        self.plot_type = '1D'
        self.w = w1D
        self.ws = {'1D':w1D, '2D':w2D}
        self.valid_code = False
        self._source = "plot_type = '1D'\ndef plot(df, cache):\n    return {}"
        self.last_df = initial_df
        self.last_cache = initial_cache
        self.editor.request_run_signal.connect(self.analyze)
        
    
    def start_updating(self):
        self.analyze()
        self.w.clear()
        if self.valid_code:
            self.is_updating = True
    
    def stop_updating(self):
        self.is_updating = False

    def get_source(self):
        return self._source

    def analyze(self):
        self.valid_code = False
        source = self.editor.text()
        self._source = source
        try:
            exec(source)
        except:
            print("Error in executing the code")
            traceback.print_exc()
            return
        if not ('plot_type' in locals() and 'plot' in locals()):
            print("Missing either a 'plot_type' variable or a 'plot' function")
            return
        _plot_type, plot_fun = locals()['plot_type'], locals()['plot']
        if _plot_type in ['1D', '2D']:
            self.plot_type = _plot_type
            self.w = self.ws[_plot_type]
            self.plot_layout.setCurrentWidget(self.w)
        else:
            print("Invalid plot type!  Must be either '1D' or '2D'")
            return
        
        self.update_fun = plot_fun
        self.valid_code = True
        self.update(self.last_df, self.last_cache)

    def update(self, df, cache):
        self.last_df = df
        self.last_cache = cache
        if self.is_updating and self.valid_code:
            if self.plot_type == '1D':
                traces = self.update_fun(df, cache)
                for name, data in traces.items():
                    self.w.set(name, xs=data[0], ys=data[1])
            elif self.plot_type == '2D':
                im = np.array(self.update_fun(df, cache))
                self.w.set(im)

class BaseView():
    def __init__(self, view, w):
        self.view = view
        self.is_updating = False
        self.update_fun = view.update_fun
        self.init_formatter = view.get_formatter(self.w, 'init')
        self.update_formatter = view.get_formatter(self.w, 'update')
        # if not self.init_formatter is None:
        #     self.init_formatter(self.w)
            
    def start_updating(self):
        self.w.clear()
        if not self.init_formatter is None:
            self.init_formatter(self.w)
        self.is_updating = True

    def stop_updating(self):
        self.is_updating = False

    # def update(self, df):
    #     if self.is_updating:
    #         traces = self.update_fun(df)
    #         for name, data in traces.items():
    #             self.w.set(name, xs=data[0], ys=data[1])
    #         if not self.update_formatter is None:
    #             self.update_formatter(self.w, df)

    def get_source(self):
        return textwrap.dedent(inspect.getsource(self.update_fun))

class LinePlotView(BaseView):
    def __init__(self, view, w=None):
        if view.type != '1D':
            raise "This class is for 1D plot only"
        if w is None:
            self.w = LinePlotWidget()
        else:
            self.w = w
        super().__init__(view, self.w)
            
    def update(self, df, cache):
        if self.is_updating:
            traces = self.update_fun(df, cache)
            for name, data in traces.items():
                self.w.set(name, xs=data[0], ys=data[1])
            if not self.update_formatter is None:
                self.update_formatter(self.w, df, cache)

class HeatmapPlotView(BaseView):
    def __init__(self, view, w=None):
        if view.type != '2D':
            raise "This class is for 2D plot only"
        if w is None:
            self.w = HeatmapPlotWidget()
        else:
            self.w = w
        super().__init__(view, self.w)
            
    def update(self, df, cache):
        if self.is_updating:
            im = np.array(self.update_fun(df, cache))
            self.w.set(im)
            if not self.update_formatter is None:
                self.update_formatter(self.w, df, cache)

# class CustomView(QtWidgets.QWidget):
#     def __init__(self, )


class View_Manager(QtWidgets.QWidget):
    def __init__(self, mongodb_addr=None, parent=None, db_name='Spyre_Live_Data', react_to_drop=False, db=None):
        super().__init__(parent=parent)
        if db is None:
            self.db = Synched_Mongo_Database(db_name, mongodb_addr=mongodb_addr)
        else:
            self.db = db
        # cleanup_register(mongodb_addr)

        self.views = dict()
        self.items = dict()
        self.last_updated = dict()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_colors)
        self.timer.start(100)
        self.fade_rate = 2
        
        layout = QtWidgets.QHBoxLayout()
        # Build tree
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(1)
        self.tree.setHeaderHidden(True)

        layout.addWidget(self.tree)

        # Build layout
        self.plot_layout = QtWidgets.QStackedLayout()
        plot_container = QtWidgets.QWidget()
        plot_container.setLayout(self.plot_layout)
        self.default_image = ImageWidget(join_nspyre_path('images/logo.png'))
        self.plot_layout.addWidget(self.default_image)
        
        self.common_lineplotwidget = LinePlotWidget()
        self.common_heatmapplotwidget = HeatmapPlotWidget()
        self.plot_layout.addWidget(self.common_lineplotwidget)
        self.plot_layout.addWidget(self.common_heatmapplotwidget)


        splitter_config = {
            'main_w': self.tree,
            'side_w': plot_container,
            'orientation': SplitterOrientation.vertical_right_button,
        }
        hsplitter = Splitter(**splitter_config)
        hsplitter.setSizes([1, 400])
        hsplitter.setHandleWidth(10)

        self.code_editor = Scintilla_Code_Editor()
        lexer = Monokai_Python_Lexer(self.code_editor)
        self.code_editor.setLexer(lexer)
        splitter_config = {
            'main_w': hsplitter,
            'side_w': self.code_editor,
            'orientation': SplitterOrientation.horizontal_top_button,
        }
        vsplitter = Splitter(**splitter_config)
        vsplitter.setSizes([1, 400])
        vsplitter.setHandleWidth(10)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(vsplitter)
        self.setLayout(layout)

        if 'Register' in self.db.dfs:
            names = list(self.db.get_df('Register').index)
            names.sort()
            for name in names:
                self.add_col(name, try_update=False)
        
        self.show()


        self.tree.currentItemChanged.connect(self.new_table_selection)

        #Connect db signals
        self.db.col_added.connect(self.add_col)
        self.db.updated_row.connect(self._update_plot)
        if react_to_drop:
            self.db.col_dropped.connect(self.del_col)

    def _update_plot(self, col_name, row):
        if col_name != 'Register':
            self.last_updated[col_name] = time.time()
        self.update_plot(col_name, row)

    def update_plot(self, col_name, row):
        if col_name == 'Register':
            self.add_col(row.name)
            return
        for name, view in self.views[col_name].items():
            if col_name in self.db.get_df('Register').index and 'cache' in self.db.get_df('Register').loc[col_name] and not self.db.get_df('Register').loc[col_name]['cache'] is np.nan:
                cache = custom_decode(self.db.get_df('Register').loc[col_name]['cache'])
            else:
                cache = {}
            view.update(self.db.get_df(col_name), cache)
        
        
    def add_col(self, col_name, try_update=True):
        if col_name == 'Register':
            return
        sclass = self.db.get_df('Register').loc[col_name]['class']
        spyrelet_views = Spyrelet_Views(sclass)
        
        if col_name in self.views:
            return
        top = QtWidgets.QTreeWidgetItem(self.tree, [col_name])
        self.default_color = top.background(0) # This is used to remember the default color when instanciating (to restore in update_color)

        self.items[col_name] = {'__top':top}
        self.views[col_name] = dict()
        self.last_updated[col_name] = time.time()

        for name, view in spyrelet_views.views.items():
            if view.type == '1D':
                self.views[col_name][name] = LinePlotView(view, self.common_lineplotwidget)
            elif view.type == '2D':
                self.views[col_name][name] = HeatmapPlotView(view, self.common_heatmapplotwidget)
            self.items[col_name][name] = QtWidgets.QTreeWidgetItem(0)#QtGui.QStandardItem(name)
            self.items[col_name][name].setText(0, name)
            
            # self.plot_layout.addWidget(self.views[col_name][name].w)
            top.addChild(self.items[col_name][name])


        self.tree.insertTopLevelItem(0, top)
        try:
            self.update_plot(col_name, None)
        except:
            pass

    def make_new_custom_view(self, col_name):
        name_template = 'Custom {}'
        for i in range(100):
            name = name_template.format(i)
            if not name in self.views[col_name]:
                if col_name in self.db.get_df('Register').index and 'cache' in self.db.get_df('Register').loc[col_name] and not self.db.get_df('Register').loc[col_name]['cache'] is np.nan:
                    cache = custom_decode(self.db.get_df('Register').loc[col_name]['cache'])
                else:
                    cache = {}
                self.views[col_name][name] = CustomView(self.code_editor, self.common_lineplotwidget, self.common_heatmapplotwidget, self.plot_layout, self.db.get_df(col_name), cache)
                self.items[col_name][name] = QtWidgets.QTreeWidgetItem(0)
                self.items[col_name][name].setText(0, name)
                self.items[col_name]['__top'].addChild(self.items[col_name][name])
                break


    def del_col(self, col_name):
        if col_name == 'Register':
            return
        # for pname, view in self.views[col_name].items():
        #     self.plot_layout.removeWidget(view.w)
        #     view.w.deleteLater()
        for iname, item in self.items[col_name].items():
            self.tree.removeItemWidget(item,0)
        self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(self.items[col_name]['__top']))
        self.views.pop(col_name)
        self.items.pop(col_name)
        self.last_updated.pop(col_name)
    
    def get_view_name(self, item):
            if item is None:
                return None, None
            txt = item.text(0)
            if not txt in self.views:
                spyrelet_name = item.parent().text(0)
                view_name = txt
                return spyrelet_name, view_name
            else:
                # Selected a top level item
                return txt, None

    def new_table_selection(self, cur, prev):
        spyrelet_name, view_name = self.get_view_name(cur)
        spyrelet_name_old, view_name_old = self.get_view_name(prev)
        if not view_name_old is None:
            self.views[spyrelet_name_old][view_name_old].stop_updating()
        if view_name is None:
            # Selected a top level item
            self.plot_layout.setCurrentWidget(self.default_image)
            return
        
        self.code_editor.setText(self.views[spyrelet_name][view_name].get_source())
        self.plot_layout.setCurrentWidget(self.views[spyrelet_name][view_name].w)
        self.views[spyrelet_name][view_name].start_updating()
        if spyrelet_name in self.db.dfs:
            self.update_plot(spyrelet_name, None)

    def update_colors(self):
        try:
            for col_name, last_time in self.last_updated.items():
                delta = (time.time()-last_time)/self.fade_rate
                if delta<1:
                    color = QtGui.QColor(0, 255, 0, int(max((1-delta)*255,0)))
                    self.items[col_name]['__top'].setBackground(0, QtGui.QBrush(color))
                else:
                    self.items[col_name]['__top'].setBackground(0, self.default_color)
        except:
            pass

    def keyPressEvent(self, ev):
        if type(ev)==QtGui.QKeyEvent:
            sname, vname = self.get_view_name(self.tree.currentItem())
            if ev.matches(QtGui.QKeySequence.Copy):
                # app = QtWidgets.QApplication.instance()
                # app.clipboard().setText(sname)
                self.make_new_custom_view(sname)
                ev.accept()
            if ev.matches(QtGui.QKeySequence.Save):
                # filename, other = QtWidgets.QFileDialog.getSaveFileName(None, 'Save this table to...', '', 'Comma Separated Value (*.csv)')
                # if filename:
                print(self.db.get_df(sname))
                    # df = self.df_table.model()._data
                    # df.to_csv(path_or_buf=filename, sep=',')
                ev.accept()

if __name__ == '__main__':
    from nspyre.widgets.app import NSpyreApp
    from nspyre.utils import get_configs
    app = NSpyreApp([])
    w = View_Manager(react_to_drop=False)
    w.show()
    app.exec_()
