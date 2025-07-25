'''
MAP Client, a program to generate detailed musculoskeletal models for OpenSim.
    Copyright (C) 2012  University of Auckland
    
This file is part of MAP Client. (http://launchpad.net/mapclient)

    MAP Client is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    MAP Client is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with MAP Client.  If not, see <http://www.gnu.org/licenses/>..
'''
from PySide6 import QtCore, QtGui, QtWidgets

from mapclientplugins.segmentationstep.tools import normal, orientation, point, curve, resetorientation
from mapclientplugins.segmentationstep.widgets.ui_segmentationwidget import Ui_SegmentationWidget
from mapclientplugins.segmentationstep.undoredo import CommandSetScale, CommandSetSingleParameterMethod, CommandSetGraphicVisibility, CommandSetGlyphSize
from mapclientplugins.segmentationstep.widgets.zincwidget import ProjectionMode
from mapclientplugins.segmentationstep.definitions import ViewMode, ViewType, ELEMENT_OUTLINE_GRAPHIC_NAME, IMAGE_PLANE_GRAPHIC_NAME, ELEMENT_NODE_LABEL_GRAPHIC_NAME
from mapclientplugins.segmentationstep.widgets.segmentationstate import SegmentationState
from mapclientplugins.segmentationstep.zincutils import getGlyphSize, setGlyphSize
from mapclientplugins.segmentationstep.widgets.sceneviewertab import SceneviewerTab
from mapclientplugins.segmentationstep.scene.master import MasterScene
import os

class SegmentationWidget(QtWidgets.QWidget):
    """
    About dialog to display program about information.
    """


    def __init__(self, model, parent=None):
        """
        Constructor
        """
        QtWidgets.QWidget.__init__(self, parent)
        self._ui = Ui_SegmentationWidget()
        self._ui.setupUi(self)

        self._ui.splitterToolBox.setStretchFactor(0, 0)
        self._ui.splitterToolBox.setStretchFactor(1, 1)

        self._model = model
        self._scene = MasterScene(self._model)
        self._serialization_location = None

        self._setupTabs()
        self._setupTools()

        self._debug_print = False

        self._viewstate = None

        self._setupUi()

        self._makeConnections()

    def _makeConnections(self):
        self._ui._lineEditWidthScale.editingFinished.connect(self._scaleChanged)
        self._ui._lineEditHeightScale.editingFinished.connect(self._scaleChanged)
        self._ui._lineEditDepthScale.editingFinished.connect(self._scaleChanged)

        self._ui._checkBoxCoordinateLabels.clicked.connect(self._graphicVisibilityChanged)
        self._ui._checkBoxImageOutline.clicked.connect(self._graphicVisibilityChanged)
        self._ui._checkBoxImagePlane.clicked.connect(self._graphicVisibilityChanged)

        self._ui._pushButtonSave.clicked.connect(self._saveState)
        self._ui._pushButtonLoad.clicked.connect(self._loadState)

    def _setupUi(self):
        dbl_validator = QtGui.QDoubleValidator()
        dbl_validator.setBottom(0.0)
        self._ui._lineEditWidthScale.setValidator(dbl_validator)
        self._ui._lineEditHeightScale.setValidator(dbl_validator)
        self._ui._lineEditDepthScale.setValidator(dbl_validator)

        dbl_validator = QtGui.QDoubleValidator()
        self._ui._lineEditXOffset.setValidator(dbl_validator)
        self._ui._lineEditYOffset.setValidator(dbl_validator)
        self._ui._lineEditZOffset.setValidator(dbl_validator)

        dimensions = self._model.getImageModel().getDimensionsInPixels()
        self._ui._labelmageWidth.setText(str(dimensions[0]) + ' px')
        self._ui._labelmageHeight.setText(str(dimensions[1]) + ' px')
        self._ui._labelmageDepth.setText(str(dimensions[2]) + ' px')

        scale = self._model.getImageModel().getScale()
        self._ui._lineEditWidthScale.setText(str(scale[0]))
        self._ui._lineEditHeightScale.setText(str(scale[1]))
        self._ui._lineEditDepthScale.setText(str(scale[2]))

        offset = self._model.getImageModel().getOffset()
        self._ui._lineEditXOffset.setText(str(offset[0]))
        self._ui._lineEditYOffset.setText(str(offset[1]))
        self._ui._lineEditZOffset.setText(str(offset[2]))

    def registerDoneExecution(self, callback):
        self._ui.doneButton.clicked.connect(callback)

    def setSerializationLocation(self, location):
        self._serialization_location = location

    def _resetViewClicked(self):
        self._loadViewState()
        self._undoRedoStack.clear()

    def _getNodeFilename(self):
        return os.path.join(self._serialization_location, 'node_state.json')

    def _saveState(self):
        node_model = self._model.getNodeModel()
        str_model = node_model.serialize()
        node_filename = self._getNodeFilename()
        try:
            if not os.path.exists(self._serialization_location):
                os.makedirs(self._serialization_location)
            with open(node_filename, 'w') as f:
                f.write(str_model)
        except IOError:
            pass

    def _loadState(self):
        node_model = self._model.getNodeModel()
        node_filename = self._getNodeFilename()
        try:
            with open(node_filename, 'r') as f:
    #         f = open(node_filename, 'r')
                str_model = f.read()
                node_model.deserialize(str_model)
                node_scene = self._scene.getNodeScene()
                node_scene.clearAllInterpolationPoints()
                for curve_identifier in node_model.getCurveIdentifiers():
                    curve = node_model.getCurveWithIdentifier(curve_identifier)
                    if len(curve) > 1:
                        locations = curve.calculate()
                        node_scene.setInterpolationPoints(curve_identifier, locations)
        except IOError:
            pass

    def _saveViewState(self):
        eye, lookat, up, angle = self._ui._sceneviewer3d.getViewParameters()

        self._viewstate = SegmentationState()
        self._viewstate.setViewParameters(eye, lookat, up, angle)
#         self._viewstate.setPointOnPlane(self._getPointOnPlane())
#         self._viewstate.setPlaneNormal(self._getPlaneNormal())
        self._viewstate.setPlaneRotationMode(self._ui._sceneviewer3d.getActiveModeType())
        self._viewstate.setProjectionMode(self._ui._sceneviewer3d.getProjectionMode())
        self._viewstate.setPlaneNormalGlyphBaseSize(self._ui._doubleSpinBoxNormalArrow.value())
        self._viewstate.setPlaneRotationCentreGlyphBaseSize(self._ui._doubleSpinBoxRotationCentre.value())

    def _loadViewState(self):
        eye, lookat, up, angle = self._viewstate.getViewParameters()
        self._ui._sceneviewer3d.setViewParameters(eye, lookat, up, angle)
#         self._setPlaneEquation(self._viewstate.getPlaneNormal(), self._viewstate.getPointOnPlane())
        self._ui._sceneviewer3d.setActiveModeType(self._viewstate.getPlaneRotationMode())
        self._setProjectionMode(self._viewstate.getProjectionMode())
        base_size = self._viewstate.getPlaneNormalGlyphBaseSize()
        self._ui._doubleSpinBoxNormalArrow.setValue(base_size)
        self._setPlaneNormalGlyphBaseSize(base_size)
        base_size = self._viewstate.getPlaneRotationCentreGlyphBaseSize()
        self._ui._doubleSpinBoxRotationCentre.setValue(base_size)
        self._setPlaneRotationCentreGlyphBaseSize(base_size)

    def _projectionModeChanged(self):
        current_mode = ProjectionMode.PERSPECTIVE if self._ui._radioButtonParallel.isChecked() else ProjectionMode.PARALLEL
        new_mode = ProjectionMode.PARALLEL if self._ui._radioButtonParallel.isChecked() else ProjectionMode.PERSPECTIVE
        c = CommandSetSingleParameterMethod(current_mode, new_mode)
        c.setSingleParameterMethod(self._setProjectionMode)

        self._model.getUndoRedoStack().push(c)

    def _setProjectionMode(self, mode):
        self._ui._radioButtonParallel.setChecked(mode == ProjectionMode.PARALLEL)
        self._ui._radioButtonPerspective.setChecked(mode == ProjectionMode.PERSPECTIVE)
        self._ui._sceneviewer3d.setProjectionMode(mode)

    def _iconSizeChanged(self):
        current = new = 0.0
        spin_box = self.sender()
        if spin_box == self._ui._doubleSpinBoxNormalArrow:
            mode = self._ui._sceneviewer3d.getMode(ViewMode.PLANE_NORMAL)
            glyph = mode.getGlyph()
            current = getGlyphSize(glyph)
            base_size = self._ui._doubleSpinBoxNormalArrow.value()
            new = [base_size, base_size / 4, base_size / 4]
        elif spin_box == self._ui._doubleSpinBoxRotationCentre:
            mode = self._ui._sceneviewer3d.getMode(ViewMode.PLANE_ROTATION)
            glyph = mode.getGlyph()
            current = getGlyphSize(glyph)
            base_size = self._ui._doubleSpinBoxRotationCentre.value()
            new = [base_size, base_size, base_size]
        elif spin_box == self._ui._doubleSpinBoxSegmentationPoint:
            glyph = self._segmentation_point_glyph
            current = getGlyphSize(glyph)
            base_size = self._ui._doubleSpinBoxSegmentationPoint.value()
            new = [base_size, base_size, base_size]

        if current != new:
            c = CommandSetGlyphSize(current, new, glyph)
            c.setSetGlyphSizeMethod(setGlyphSize)
            c.setSpinBox(spin_box)

            self._model.getUndoRedoStack().push(c)

    def _graphicVisibilityChanged(self):
        check_box = self.sender()
        graphic = None
        if check_box == self._ui._checkBoxCoordinateLabels:
            graphic = self._scene.getGraphic(ELEMENT_NODE_LABEL_GRAPHIC_NAME)
        elif check_box == self._ui._checkBoxImagePlane:
            graphic = self._scene.getGraphic(IMAGE_PLANE_GRAPHIC_NAME)
        elif check_box == self._ui._checkBoxImageOutline:
            graphic = self._scene.getGraphic(ELEMENT_OUTLINE_GRAPHIC_NAME)

        c = CommandSetGraphicVisibility(not check_box.isChecked(), check_box.isChecked())
        c.setCheckBox(check_box)
        c.setGraphic(graphic)

        self._model.getUndoRedoStack().push(c)

    def _scaleChanged(self):
        current_scale = self._model.getScale()
        new_scale = current_scale[:]
        line_edit = self.sender()
        if line_edit == self._ui._lineEditWidthScale:
            change_scale_index = 0
            new_scale[0] = float(self._ui._lineEditWidthScale.text())
        elif line_edit == self._ui._lineEditHeightScale:
            change_scale_index = 1
            new_scale[1] = float(self._ui._lineEditHeightScale.text())
        elif line_edit == self._ui._lineEditDepthScale:
            change_scale_index = 2
            new_scale[2] = float(self._ui._lineEditDepthScale.text())

        if new_scale != current_scale:
            c = CommandSetScale(current_scale, new_scale, change_scale_index)
            c.setLineEdit(line_edit)
            c.setSetScaleMethod(self._model.setScale)

            self._model.getUndoRedoStack().push(c)

    def keyPressEvent(self, keyevent):
        if keyevent.key() == 68 and not self._debug_print:
            self._debug_print = True

    def _changeHandler(self, handler_type):
        undo_redo_stack = self._model.getUndoRedoStack()
        undo_redo_stack.beginMacro('Change Handler')
        self._tabs[ViewType.VIEW_2D].setActiveHandler(handler_type)
        self._tabs[ViewType.VIEW_3D].setActiveHandler(handler_type)
        undo_redo_stack.endMacro()

    def _deleteClicked(self):
        if self._tools[ViewMode.SEGMENT_POINT].willDelete():
            self._tools[ViewMode.SEGMENT_POINT].deleteClicked()
        elif self._tools[ViewMode.SEGMENT_CURVE].willDelete():
            self._tools[ViewMode.SEGMENT_CURVE].deleteClicked()

    def keyReleaseEvent(self, keyevent):
        '''
        Special Keys:
        To provide the expected behavior for Qt applications on Mac OS X,
        the Qt::Meta, Qt::MetaModifier, and Qt::META enum values correspond
        to the Control keys on the standard Macintosh keyboard, and the
        Qt::Control, Qt::ControlModifier, and Qt::CTRL enum values 
        correspond to the Command keys.
        '''
        if keyevent.key() == QtCore.Qt.Key.Key_1 and keyevent.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier and not keyevent.isAutoRepeat():
            self._changeHandler(ViewMode.SEGMENT_POINT)
        if keyevent.key() == QtCore.Qt.Key.Key_2 and keyevent.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier and not keyevent.isAutoRepeat():
            self._changeHandler(ViewMode.SEGMENT_CURVE)
        if keyevent.key() == QtCore.Qt.Key.Key_3 and keyevent.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier and not keyevent.isAutoRepeat():
            self._changeHandler(ViewMode.PLANE_NORMAL)
        if keyevent.key() == QtCore.Qt.Key.Key_4 and keyevent.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier and not keyevent.isAutoRepeat():
            self._changeHandler(ViewMode.PLANE_ROTATION)
        if keyevent.key() == QtCore.Qt.Key.Key_Delete and not keyevent.isAutoRepeat():
            self._deleteClicked()
        if keyevent.key() == QtCore.Qt.Key.Key_Backspace and not keyevent.isAutoRepeat():
            self._deleteClicked()

        if keyevent.key() == 68 and not keyevent.isAutoRepeat():
            self._debug_print = False

    def _setupTabs(self):
        self._tabs = {}
        context = self._model.getContext()

        view3d = SceneviewerTab(context, self._model.getUndoRedoStack())
        self._ui._tabWidgetLeft.addTab(view3d, ViewType.VIEW_3D)

        view2d = SceneviewerTab(context, self._model.getUndoRedoStack())
        view2d.setPlane(self._model.getImageModel().getPlane())
        self._ui._tabWidgetLeft.addTab(view2d, ViewType.VIEW_2D)

        self._tabs[ViewType.VIEW_3D] = view3d
        self._tabs[ViewType.VIEW_2D] = view2d

    def _setupTools(self):
        self._tools = {}
        context = self._model.getContext()
        image_model = self._model.getImageModel()
        node_model = self._model.getNodeModel()
        node_scene = self._scene.getNodeScene()
        plane = image_model.getPlane()
        undo_redo_stack = self._model.getUndoRedoStack()

        materialmodule = context.getMaterialmodule()
        yellow_material = materialmodule.findMaterialByName('yellow')
        orange_material = materialmodule.findMaterialByName('orange')
        purple_material = materialmodule.findMaterialByName('purple')
        red_material = materialmodule.findMaterialByName('red')

        view_3d_tab = self._tabs[ViewType.VIEW_3D]
        view_2d_tab = self._tabs[ViewType.VIEW_2D]

        point_tool = point.PointTool(plane, undo_redo_stack)
        point_tool.setModel(node_model)
        point_tool.setScene(node_scene)
        point_tool.setGetDimensionsMethod(image_model.getDimensions)
        w = point_tool.getPropertiesWidget()
        self._ui._toolTab.addItem(w, point_tool.getName())

        normal_tool = normal.NormalTool(plane, undo_redo_stack)
        normal_tool.setGetDimensionsMethod(image_model.getDimensions)
        normal_tool.setDefaultMaterial(yellow_material)
        normal_tool.setSelectedMaterial(orange_material)

        rotation_tool = orientation.OrientationTool(plane, undo_redo_stack)
        rotation_tool.setGetDimensionsMethod(image_model.getDimensions)
        rotation_tool.setDefaultMaterial(purple_material)
        rotation_tool.setSelectedMaterial(red_material)

        reset_rotation_tool_XY = resetorientation.ResetOrientationXYTool(plane, undo_redo_stack)
        reset_rotation_tool_XZ = resetorientation.ResetOrientationXZTool(plane, undo_redo_stack)
        reset_rotation_tool_YZ = resetorientation.ResetOrientationYZTool(plane, undo_redo_stack)

        curve_tool = curve.CurveTool(plane, undo_redo_stack)
        curve_tool.setModel(node_model)
        curve_tool.setScene(node_scene)
        curve_tool.setGetDimensionsMethod(image_model.getDimensions)
        w = curve_tool.getPropertiesWidget()
        self._ui._toolTab.addItem(w, curve_tool.getName())

        view_3d_tab.addHandler(point_tool.getName(), point_tool.getIcon(), point_tool.getHandler(ViewType.VIEW_3D))
        view_3d_tab.addHandler(curve_tool.getName(), curve_tool.getIcon(), curve_tool.getHandler(ViewType.VIEW_3D))
        view_3d_tab.addHandler(normal_tool.getName(), normal_tool.getIcon(), normal_tool.getHandler(ViewType.VIEW_3D))
        view_3d_tab.addHandler(rotation_tool.getName(), rotation_tool.getIcon(), rotation_tool.getHandler(ViewType.VIEW_3D))

        view_3d_tab.add_action(reset_rotation_tool_XY.getName(), reset_rotation_tool_XY.getIcon(), reset_rotation_tool_XY.action)
        view_3d_tab.add_action(reset_rotation_tool_XZ.getName(), reset_rotation_tool_XZ.getIcon(), reset_rotation_tool_XZ.action)
        view_3d_tab.add_action(reset_rotation_tool_YZ.getName(), reset_rotation_tool_YZ.getIcon(), reset_rotation_tool_YZ.action)

        view_2d_tab.addHandler(point_tool.getName(), point_tool.getIcon(), point_tool.getHandler(ViewType.VIEW_2D))
        view_2d_tab.addHandler(curve_tool.getName(), curve_tool.getIcon(), curve_tool.getHandler(ViewType.VIEW_2D))

        # Should we also add the the new tools to this dictionary?:
        self._tools[ViewMode.SEGMENT_POINT] = point_tool
        self._tools[ViewMode.PLANE_NORMAL] = normal_tool
        self._tools[ViewMode.PLANE_ROTATION] = rotation_tool
        self._tools[ViewMode.SEGMENT_CURVE] = curve_tool
