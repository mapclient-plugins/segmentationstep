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
from opencmiss.zinc.status import OK

from mapclientplugins.segmentationstep.model.abstractmodel import AbstractModel
from mapclientplugins.segmentationstep.zincutils import createFiniteElementField
from mapclientplugins.segmentationstep.segmentpoint import SegmentPointStatus

class NodeModel(AbstractModel):

    def __init__(self, context, plane):
        super(NodeModel, self).__init__(context)
        self._plane = plane
        self._plane_attitudes = {}
        self._nodes = {}
        self._curves = {}
        self._setupNodeRegion()
        self._on_plane_conditional_field = self._createOnPlaneConditionalField()
        self._on_plane_point_cloud_field = self._createOnPlanePointCloudField()
        self._on_plane_curve_field = self._createOnPlaneCurveField()
        self._on_plane_interpolation_point_field = self._createOnPlaneInterpolation()

    def _setupNodeRegion(self):
        self._region = self._context.getDefaultRegion().createChild('point_cloud')
#         scene = self._region.getScene()
        self._coordinate_field = createFiniteElementField(self._region)
        fieldmodule = self._region.getFieldmodule()
        fieldmodule.beginChange()
        nodeset = fieldmodule.findNodesetByName('nodes')

        self._scale_field = fieldmodule.createFieldConstant([1.0, 1.0, 1.0])
        self._scaled_coordinate_field = self._coordinate_field * self._scale_field

        # Setup the selection fields
        self._selection_group_field = fieldmodule.createFieldGroup()
        selectiongroup = self._selection_group_field.createFieldNodeGroup(nodeset)
        self._group = selectiongroup.getNodesetGroup()

        # Setup the point cloud fields
        self._point_cloud_group_field = fieldmodule.createFieldGroup()
        pointcloudgroup = self._point_cloud_group_field.createFieldNodeGroup(nodeset)
        self._point_cloud_group = pointcloudgroup.getNodesetGroup()

        # Setup the curve fields
        self._curve_group_field = fieldmodule.createFieldGroup()
        curvegroup = self._curve_group_field.createFieldNodeGroup(nodeset)
        self._curve_group = curvegroup.getNodesetGroup()

        datapointset = fieldmodule.findNodesetByName('datapoints')
        self._interpolation_point_group_field = fieldmodule.createFieldGroup()
        segmentationpointgroup = self._curve_group_field.createFieldNodeGroup(datapointset)
        self._interpolation_point_group = segmentationpointgroup.getNodesetGroup()

        fieldmodule.endChange()

    def _createOnPlaneConditionalField(self):
        fieldmodule = self._region.getFieldmodule()
        fieldmodule.beginChange()

        alias_normal_field = fieldmodule.createFieldAlias(self._plane.getNormalField())
        alias_point_field = fieldmodule.createFieldAlias(self._plane.getRotationPointField())

        plane_equation_field = self._createPlaneEquationField(fieldmodule, self._scaled_coordinate_field, alias_normal_field, alias_point_field)
        tolerance_field = fieldmodule.createFieldConstant(0.5)
        abs_field = fieldmodule.createFieldAbs(plane_equation_field)
        on_plane_field = fieldmodule.createFieldLessThan(abs_field, tolerance_field)

        fieldmodule.endChange()
        return on_plane_field

    def _createOnPlanePointCloudField(self):
        fieldmodule = self._region.getFieldmodule()
        fieldmodule.beginChange()
        and_field = fieldmodule.createFieldAnd(self._on_plane_conditional_field, self._point_cloud_group_field)
        fieldmodule.endChange()

        return and_field

    def _createOnPlaneCurveField(self):
        fieldmodule = self._region.getFieldmodule()
        fieldmodule.beginChange()
        and_field = fieldmodule.createFieldAnd(self._on_plane_conditional_field, self._curve_group_field)
        fieldmodule.endChange()

        return and_field

    def _createOnPlaneInterpolation(self):
        fieldmodule = self._region.getFieldmodule()
        fieldmodule.beginChange()
        and_field = fieldmodule.createFieldAnd(self._on_plane_conditional_field, self._interpolation_point_group_field)
        fieldmodule.endChange()

        return and_field

    def _createPlaneEquationField(self, fieldmodule, coordinate_field, plane_normal_field, point_on_plane_field):
        d = fieldmodule.createFieldDotProduct(plane_normal_field, point_on_plane_field)
        plane_equation_field = fieldmodule.createFieldDotProduct(coordinate_field, plane_normal_field) - d

        return plane_equation_field

    def setScale(self, scale):
        '''
        Don't call this 'setScale' method directly let the main model do that
        this way we can ensure that the two scale fields have the same
        values.
        '''
        fieldmodule = self._region.getFieldmodule()
        fieldcache = fieldmodule.createFieldcache()
        self._scale_field.assignReal(fieldcache, scale)

    def getPointCloudGroupField(self):
        return self._point_cloud_group_field

    def getPointCloudGroup(self):
        return self._point_cloud_group

    def getCurveGroupField(self):
        return self._curve_group_field

    def getCurveGroup(self):
        return self._curve_group

    def getInterpolationPointGroup(self):
        return self._interpolation_point_group

    def getOnPlanePointCloudField(self):
        return self._on_plane_point_cloud_field

    def getOnPlaneInterpolationField(self):
        return self._on_plane_conditional_field

    def getOnPlaneCurveField(self):
        return self._on_plane_curve_field

    def getOnPlaneSegmentationPointField(self):
        return self._on_plane_conditional_field

    def getSelectionGroupField(self):
        return self._selection_group_field

    def getSelectionGroup(self):
        return self._group

    def isSelected(self, node):
        return self._group.containsNode(node)

    def getCurrentSelection(self):
        selection = []
        ni = self._group.createNodeiterator()
        node = ni.next()
        while node.isValid():
            selection.append(node.getIdentifier())
            node = ni.next()

        return selection

    def setSelection(self, selection):
        fieldmodule = self._region.getFieldmodule()
        nodeset = fieldmodule.findNodesetByName('nodes')
        fieldmodule.beginChange()
        self._selection_group_field.clear()
        for node_id in selection:
            node = nodeset.findNodeByIdentifier(node_id)
            self._group.addNode(node)

        fieldmodule.endChange()

    def getNodeByIdentifier(self, node_id):
        fieldmodule = self._region.getFieldmodule()
        nodeset = fieldmodule.findNodesetByName('nodes')
        node = nodeset.findNodeByIdentifier(node_id)
        return node

    def getNodePlaneAttitude(self, node_id):
        return self._nodes[node_id]

    def getNodeStatus(self, node_id):
        node = self.getNodeByIdentifier(node_id)
        node_status = SegmentPointStatus(node_id, self.getNodeLocation(node), self.getNodePlaneAttitude(node_id))
        return node_status

    def _addId(self, plane_attitude, node_id):
        if plane_attitude in self._plane_attitudes:
            self._plane_attitudes[plane_attitude].append(node_id)
        else:
            self._plane_attitudes[plane_attitude] = [node_id]

    def _removeId(self, plane_attitude, node_id):
        index = self._plane_attitudes[plane_attitude].index(node_id)
        del self._plane_attitudes[plane_attitude][index]
        if len(self._plane_attitudes[plane_attitude]) == 0:
            del self._plane_attitudes[plane_attitude]

    def getElementByIdentifier(self, element_id):
        fieldmodule = self._region.getFieldmodule()
        mesh = fieldmodule.findMeshByDimension(1)
        if element_id is None:
            element_id = -1
        return mesh.findElementByIdentifier(element_id)

    def getCurveCount(self):
        return len(self._curves)

    def insertCurve(self, curve_identifier, curve):
        self._curves[curve_identifier] = curve

    def popCurve(self, curve_identifier):
        if curve_identifier in self._curves:
            curve = self._curves[curve_identifier]
            del self._curves[curve_identifier]
            node_ids = curve.getNodes()
            for node_id in node_ids:
                self.removeNode(node_id)
            curve.removeAllNodes()

    def getCurveIndex(self, curve):
        for curve_identifier in self._curves:
            if curve == self._curves[curve_identifier]:
                return curve_identifier

        return None

    def getCurveAtIndex(self, index):
        return self._curves[index]

    def getCurveForNode(self, node_id):
        for curve_identifier in self._curves:
            curve = self._curves[curve_identifier]
            if node_id in curve:
                return curve

        return None

    def addNode(self, node_id, location, plane_attitude):
        if node_id is -1:
            node = self._createNodeAtLocation(location)
            node_id = node.getIdentifier()
        self._addId(plane_attitude, node_id)
        self._nodes[node_id] = plane_attitude

        return node_id

    def addNodes(self, node_statuses):
        fieldmodule = self._region.getFieldmodule()
        fieldmodule.beginChange()

        node_ids = []
        for node_status in node_statuses:
            node_id = self.addNode(node_status.getNodeIdentifier(), node_status.getLocation(), node_status.getPlaneAttitude())
            node_ids.append(node_id)

        fieldmodule.endChange()

    def modifyNode(self, node_id, location, plane_attitude):
        current_plane_attitude = self._nodes[node_id]
        node = self.getNodeByIdentifier(node_id)
        self.setNodeLocation(node, location)
        if current_plane_attitude != plane_attitude:
            self._removeId(current_plane_attitude, node_id)
            self._addId(plane_attitude, node_id)
            self._nodes[node_id] = plane_attitude

    def setNodeLocation(self, node, location):
        fieldmodule = self._region.getFieldmodule()
        fieldcache = fieldmodule.createFieldcache()
        fieldmodule.beginChange()
        fieldcache.setNode(node)
        self._coordinate_field.assignReal(fieldcache, location)
        fieldmodule.endChange()

    def getNodeLocation(self, node):
        fieldmodule = self._region.getFieldmodule()
        fieldcache = fieldmodule.createFieldcache()
        fieldmodule.beginChange()
        fieldcache.setNode(node)
        result, location = self._coordinate_field.evaluateReal(fieldcache, 3)
        fieldmodule.endChange()

        if result == OK:
            return location

        return None

    def removeElement(self, element_id):
        fieldmodule = self._region.getFieldmodule()
        fieldmodule.beginChange()
        mesh = fieldmodule.findMeshByDimension(1)
        element = mesh.findElementByIdentifier(element_id)
        mesh.destroyElement(element)
        fieldmodule.endChange()

    def createDatapoint(self, location=None):
        return self._createNodeAtLocation(location, 'datapoints')

    def removeDatapoint(self, datapoint):
        nodeset = datapoint.getNodeset()
        nodeset.destroyNode(datapoint)

    def removeNodes(self, node_statuses):
        fieldmodule = self._region.getFieldmodule()
        fieldmodule.beginChange()

        for node_status in node_statuses:
            self.removeNode(node_status.getNodeIdentifier())

        fieldmodule.endChange()

    def removeNode(self, node_id):
        if node_id in self._nodes:
            plane_attitude = self._nodes[node_id]
            self._removeId(plane_attitude, node_id)
            del self._nodes[node_id]

        node = self.getNodeByIdentifier(node_id)
        nodeset = node.getNodeset()
        nodeset.destroyNode(node)

    def createNodes(self, node_statuses, group=None):
        node_ids = []
        for node_status in node_statuses:
            node_id = self.addNode(-1, node_status.getLocation(), node_status.getPlaneAttitude())
            if group is not None:
                node = self.getNodeByIdentifier(node_id)
                group.addNode(node)
            node_ids.append(node_id)

        return node_ids

    def createNode(self):
        '''
        Create a node with the models coordinate field.
        '''
        fieldmodule = self._region.getFieldmodule()
        fieldmodule.beginChange()

        nodeset = fieldmodule.findNodesetByName('nodes')
        template = nodeset.createNodetemplate()
        template.defineField(self._coordinate_field)

        scene = self._region.getScene()
        selection_field = scene.getSelectionField()
        if not selection_field.isValid():
            scene.setSelectionField(self._selection_group_field)

        self._selection_group_field.clear()

        node = nodeset.createNode(-1, template)
        self._group.addNode(node)

        fieldmodule.endChange()

        return node

    def _createNodeAtLocation(self, location, dataset='nodes'):
        '''
        Creates a node at the given location without
        adding it to the current selection.
        '''
        fieldmodule = self._region.getFieldmodule()
        fieldmodule.beginChange()

        nodeset = fieldmodule.findNodesetByName(dataset)
        template = nodeset.createNodetemplate()
        template.defineField(self._coordinate_field)
        node = nodeset.createNode(-1, template)
        self.setNodeLocation(node, location)
        fieldmodule.endChange()

        return node
