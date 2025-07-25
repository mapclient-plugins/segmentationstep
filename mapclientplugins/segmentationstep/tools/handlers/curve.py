"""
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
"""
from PySide6 import QtCore

from mapclientplugins.segmentationstep.tools.handlers.abstractselection import AbstractSelection
from mapclientplugins.segmentationstep.definitions import ViewMode, DEFAULT_INTERPOLATION_COUNT
from mapclientplugins.segmentationstep.undoredo import CommandCurveNode, CommandMovePlane
from mapclientplugins.segmentationstep.segmentpoint import ControlPointStatus
from mapclientplugins.segmentationstep.maths.algorithms import calculateLinePlaneIntersection
from mapclientplugins.segmentationstep.model.curve import CurveModel

class Curve(AbstractSelection):

    def __init__(self, plane, undo_redo_stack):
        super(Curve, self).__init__(plane, undo_redo_stack)
        self._mode_type = ViewMode.SEGMENT_CURVE
        self._model = None
        self._scene = None
        self._node_status = None
        self._active_curve = None
        self._interpolation_count = DEFAULT_INTERPOLATION_COUNT

    def setModel(self, model):
        self._model = model

    def setScene(self, scene):
        self._scene = scene

    def setInterpolationCount(self, count):
        self._interpolation_count = count

    def enter(self):
        super(Curve, self).enter()

    def leave(self):
        super(Curve, self).leave()

    def mousePressEvent(self, event):
        if self._active_button != QtCore.Qt.MouseButton.NoButton:
            return

        self._active_button = event.button()

        self._start_plane_attitude = None
        self._finshing_curve = False
        self._adding_to_curve = False
        self._modifying_curve = False
        pixel_scale = self._zinc_view.getPixelScale()
        x = event.x() * pixel_scale
        y = event.y() * pixel_scale
        if self._node_status:
            if ((event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier)
                    and event.button() == QtCore.Qt.MouseButton.RightButton):
                node_id = self._node_status.getNodeIdentifier()
                self._active_curve.removeNode(node_id)
                curve_index = self._model.getCurveIdentifier(self._active_curve)
                if len(self._active_curve) > 1:
                    locations = self._active_curve.calculate()
                    self._scene.setInterpolationPoints(curve_index, locations)
                else:
                    self._scene.clearInterpolationPoints(curve_index)

                self._model.removeNode(node_id)
                self._node_status = None
                self._zinc_view.setMouseTracking(False)
                self._finshing_curve = True
            elif ((event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier)
                  and event.button() == QtCore.Qt.MouseButton.LeftButton):
                node = self._zinc_view.getNearestNode(x, y)
                if node and node.isValid():
                    self._closing_curve_node_id = self._node_status.getNodeIdentifier()
                    self._node_status.setNodeIdentifier(node.getIdentifier())
                self._adding_to_curve = True
            else:
                super(Curve, self).mousePressEvent(event)
        elif ((event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier)
              and event.button() == QtCore.Qt.MouseButton.LeftButton):
            # The start of a new curve
            self._active_curve = None
            node = self._zinc_view.getNearestNode(x, y)
            if node and node.isValid():
                # node exists at this location so select it
                group = self._model.getSelectionGroup()
                group.removeAllNodes()
                group.addNode(node)

                node_id = node.getIdentifier()
                self._active_curve = self._model.getCurveForNode(node_id)
                node_location = self._model.getNodeLocation(node)
                plane_attitude = self._model.getNodePlaneAttitude(node_id)
                self._start_plane_attitude = self._plane.getAttitude()
                self._modifying_curve = True
            else:
                # The start of a new curve
                self._active_curve = CurveModel(self._model)
                self._model.insertCurve(self._model.getNextCurveIdentifier(), self._active_curve)
                self._active_curve.setInterpolationCount(self._interpolation_count)
                node_location = None
                plane_attitude = None
                point_on_plane = self._calculatePointOnPlane(x, y)
                region = self._model.getRegion()
                fieldmodule = region.getFieldmodule()
                fieldmodule.beginChange()
                node = self._model.createNode()
                self._model.setNodeLocation(node, point_on_plane)
                group = self._model.getCurveGroup()
                group.addNode(node)
                node_id = node.getIdentifier()
                fieldmodule.endChange()
                self._adding_to_curve = True
                self._active_curve.addNode(node_id)

            self._node_status = ControlPointStatus(node_id, node_location, plane_attitude)
            curve_index = self._model.getCurveIdentifier(self._active_curve)
            self._node_status.setCurveIdentifier(curve_index)
        elif self._node_status is None:
            super(Curve, self).mousePressEvent(event)


    def mouseMoveEvent(self, event):
        if self._node_status is not None:
            pixel_scale = self._zinc_view.getPixelScale()
            x = event.x() * pixel_scale
            y = event.y() * pixel_scale
            self._start_plane_attitude = None
            node = self._model.getNodeByIdentifier(self._node_status.getNodeIdentifier())
            point_on_plane = self._calculatePointOnPlane(x, y)
            self._model.setNodeLocation(node, point_on_plane)
            curve_index = self._model.getCurveIdentifier(self._active_curve)
            if len(self._active_curve) > 1:
                locations = self._active_curve.calculate()
                self._scene.setInterpolationPoints(curve_index, locations)
            if self._modifying_curve:
                pass
            elif not self._adding_to_curve or not self._finshing_curve:
                super(Curve, self).mouseMoveEvent(event)
        else:
            super(Curve, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._active_button != event.button():
            return

        if self._start_plane_attitude is not None and self._node_status is not None:
            group = self._model.getSelectionGroup()
            group.removeAllNodes()
            target_plane_attitude = self._node_status.getPlaneAttitude()
            if target_plane_attitude != self._start_plane_attitude:
                c = CommandMovePlane(self._plane, self._start_plane_attitude, target_plane_attitude)
                self._undo_redo_stack.push(c)
            self._node_status = None
        elif self._node_status is not None and self._adding_to_curve:
            node_id = self._node_status.getNodeIdentifier()
            node1 = self._model.getNodeByIdentifier(node_id)

            group = self._model.getSelectionGroup()
            group.removeNode(node1)
            node_location = self._model.getNodeLocation(node1)
            plane_attitude = self._plane.getAttitude()
            node_status = ControlPointStatus(node_id, node_location, plane_attitude)
            c = CommandCurveNode(self._model, self._node_status, node_status)
            c.setScene(self._scene)

            if self._active_curve.closes(node_id):
                node2 = self._model.getNodeByIdentifier(self._closing_curve_node_id)
            else:
                node2 = self._model.createNode()
                self._model.setNodeLocation(node2, node_location)
                group = self._model.getCurveGroup()
                group.addNode(node2)

            node_id = node2.getIdentifier()
            curve_index = self._model.getCurveIdentifier(self._active_curve)
            self._scene.clearInterpolationPoints(curve_index)
            self._active_curve.addNode(node_id)
            node_status.setCurveIdentifier(curve_index)
            self._node_status.setCurveIdentifier(curve_index)
            self._undo_redo_stack.push(c)
            locations = self._active_curve.calculate()
            self._scene.setInterpolationPoints(curve_index, locations)
            self._node_status = ControlPointStatus(node_id, None, None)
            self._node_status.setCurveIdentifier(curve_index)

            self._zinc_view.setMouseTracking(True)
        elif self._finshing_curve:
            self._active_curve = None
        elif self._modifying_curve:
            node_id = self._node_status.getNodeIdentifier()
            node = self._model.getNodeByIdentifier(node_id)
            node_location = self._model.getNodeLocation(node)
            plane_attitude = self._plane.getAttitude()
            node_status = ControlPointStatus(node_id, node_location, plane_attitude)
            curve_index = self._model.getCurveIdentifier(self._active_curve)
            node_status.setCurveIdentifier(curve_index)
            c = CommandCurveNode(self._model, self._node_status, node_status)
            c.setScene(self._scene)

            group = self._model.getSelectionGroup()
            group.removeNode(node)
            self._node_status = None
            self._undo_redo_stack.push(c)
        elif not self._adding_to_curve:
            super(Curve, self).mouseReleaseEvent(event)

        self._active_button = QtCore.Qt.NoButton

    def _calculatePointOnPlane(self, x, y):
        far_plane_point = self._zinc_view.unproject(x, -y, -1.0)
        near_plane_point = self._zinc_view.unproject(x, -y, 1.0)
        point_on_plane = calculateLinePlaneIntersection(near_plane_point, far_plane_point, self._plane.getRotationPoint(), self._plane.getNormal())
        return point_on_plane


