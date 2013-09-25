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
import os, re

import numpy

from PySide import QtCore, QtOpenGL, QtGui

from opencmiss.zinc.context import Context
from opencmiss.zinc.graphic import Graphic
from opencmiss.zinc.sceneviewer import SceneViewerInput, SceneViewer
from opencmiss.zinc.field import Field
from opencmiss.zinc.element import Element, ElementBasis
from opencmiss.zinc.graphicsmaterial import GraphicsMaterial

from segmentationstep.undoredo import CommandAdd

def tryint(s):
    try:
        return int(s)
    except:
        return s

def alphanum_key(s):
    """ Turn a string into a list of string and number chunks.
        "z23a" -> ["z", 23, "a"]
    """
    return [ tryint(c) for c in re.split('([0-9]+)', s) ]

class ZincScene(QtOpenGL.QGLWidget):

    # init start
    def __init__(self, parent=None):
        '''
        Call the super class init functions, create a Zinc context and set the scene viewer handle to None.
        '''

        QtOpenGL.QGLWidget.__init__(self, parent)
        self._initZincContext()
        self._imageDataLocation = None
        self._slider_value = 0
        self._component = 0
        self._action_transfrom = True
        self._undoRedoStack = QtGui.QUndoStack(self)

    def setImageDataLocation(self, imageDataLocation):
        self._imageDataLocation = imageDataLocation

    def _initZincContext(self):
        self._context = Context("digitiser")
        self._scene_viewer = None

    def initializeGL(self):
        '''
        Initialise the Zinc scene, create the finite element, and the surface to visualise it.  
        '''

        # From the context get the default scene veiwer package and set up a scene_viewer.
        scene_viewer_package_ = self._context.getDefaultSceneViewerPackage()
        self._scene_viewer = scene_viewer_package_.createSceneViewer(SceneViewer.BUFFERING_MODE_DOUBLE, SceneViewer.STEREO_MODE_ANY)

        # ## childRegionCreate start
        self.root_region = self._context.getDefaultRegion()

        # create a number of independant 3D meshes - one for each image.
        # automatically alter the range depending on the number of slices.
        # for i in range(0, self.number_of_images):
        # ## childRegionCreate end

        # Get the default graphics module from the context and enable renditions
        graphics_module = self._context.getDefaultGraphicsModule()
        graphics_module.enableRenditions(self.root_region)
        graphics_module.defineStandardMaterials()
        # Create a filter for visibility flags which will allow us to see our graphic.
        graphics_filter = graphics_module.createFilterVisibilityFlags()

        # Create a scene and set the _surface_region tree for it to show.  We also set the graphics filter for the scene
        # otherwise nothing will be visible.
        scene = graphics_module.createScene()
        scene.setRegion(self.root_region)
        scene.setFilter(graphics_filter)
        # Set the scene to our scene viewer.
        self._scene_viewer.setScene(scene)

        # function calls
        # self._()
        self.createMaterialUsingImageField()
        self.createSurfaceRegion()
        self.createFiniteElements()
        self.createSurfaceGraphics()
        self.createNodeRegion()
        self.createNodeGraphics()

        self._scene_viewer.viewAll()

    def createMaterialUsingImageField(self):
        ''' 
        Use an image field in a grpahics material to create a n OpenGL texture
        '''
        # create a graphics material from the graphics module, assign it a name
        # and set flag to true
        graphics_module = self._context.getDefaultGraphicsModule()
        self._material = graphics_module.createMaterial()
        self._material.setName('texture_block')
        self._material.setAttributeInteger(GraphicsMaterial.ATTRIBUTE_IS_MANAGED, 1)

        # Get a handle to the root _surface_region
        root_region = self._context.getDefaultRegion()

        # The field module allows us to create a field image to
        # store the image data into.
        field_module = root_region.getFieldModule()

        # Create an image field. A temporary xi source field is created for us.
        image_field = field_module.createImage()
        image_field.setName('image_field')
        image_field.setFilterMode(image_field.FILTER_LINEAR)

        # Create a stream information object that we can use to read the
        # image file from disk
        stream_information = image_field.createStreamInformation()
        # specify depth of texture block i.e. number of images
#        stream_information.setAttributeInteger(stream_information.IMAGE_ATTRIBUTE_, self.number_of_images)

        # Load images onto an invidual texture blocks.
        directory = self._imageDataLocation.location()
        files = os.listdir(directory)
        files.sort(key=alphanum_key)
        for filename in files:
            # We are reading in a file from the local disk so our resource is a file.
            stream_information.createResourceFile(os.path.join(directory, filename))

        # Actually read in the image file into the image field.
        image_field.read(stream_information)
        self._material.setImageField(1, image_field)

    def create3DFiniteElement(self, field_module, finite_element_field, node_coordinate_set):
        '''
        Create finite element from a template
        '''
        # Find a special node set named 'cmiss_nodes'
        nodeset = field_module.findNodesetByName('cmiss_nodes')
        node_template = nodeset.createNodeTemplate()

        # Set the finite element coordinate field for the nodes to use
        node_template.defineField(finite_element_field)
        field_cache = field_module.createCache()

        node_identifiers = []
        # Create eight nodes to define a cube finite element
        for node_coordinate in node_coordinate_set:
            node = nodeset.createNode(-1, node_template)
            node_identifiers.append(node.getIdentifier())
            # Set the node coordinates, first set the field cache to use the current node
            field_cache.setNode(node)
            # Pass in floats as an array
            finite_element_field.assignReal(field_cache, node_coordinate)

        # Use a 3D mesh to to create the 3D finite element.
        mesh = field_module.findMeshByDimension(3)
        element_template = mesh.createElementTemplate()
        element_template.setShapeType(Element.SHAPE_CUBE)
        element_node_count = 8
        element_template.setNumberOfNodes(element_node_count)
        # Specify the dimension and the interpolation function for the element basis function
        linear_basis = field_module.createElementBasis(3, ElementBasis.FUNCTION_LINEAR_LAGRANGE)
        # the indecies of the nodes in the node template we want to use.
        node_indexes = [1, 2, 3, 4, 5, 6, 7, 8]


        # Define a nodally interpolated element field or field component in the
        # element_template
        element_template.defineFieldSimpleNodal(finite_element_field, -1, linear_basis, node_indexes)

        for i, node_identifier in enumerate(node_identifiers):
            node = nodeset.findNodeByIdentifier(node_identifier)
            element_template.setNode(i + 1, node)

        mesh.defineElement(-1, element_template)

    def createSurfaceRegion(self):
        self._surface_region = self.root_region.createChild('surface')

    def createSurfaceGraphics(self):
        '''
        To visualize the 3D finite element that we have created for each _surface_region, we use a 
        surface graphic then set a _material for that surface to use.
        '''
        graphics_module = self._context.getDefaultGraphicsModule()
        # we iterate over the regions that we kept a handle to and use an index to get a
        # matching list of graphic _material names
        # for i, _surface_region in enumerate(self.regions_):
        rendition = graphics_module.getRendition(self._surface_region)
        field_module = self._surface_region.getFieldModule()
        # search the graphic module for the current graphic _material
        self._material = graphics_module.findMaterialByName('texture_block')

        rendition.beginChange()
        # Create a surface graphic and set it's coordinate field to the finite element coordinate field
        # named coordinates
        outline = rendition.createGraphic(Graphic.GRAPHIC_LINES)
        finite_element_field = field_module.findFieldByName('coordinates')
        outline.setCoordinateField(finite_element_field)

        # Create three isosurface planes in the x, y and z directions whose positions in the texture block
        # can be altered using sliders
        # ## x component
        self._iso_graphic = rendition.createGraphicIsoSurface()
        self._iso_graphic.setCoordinateField(finite_element_field)
        self._iso_graphic.setMaterial(self._material)
        xi_field = field_module.findFieldByName('xi')
        self._iso_graphic.setTextureCoordinateField(xi_field)
        # set the yz scalar field to our isosurface
        self._iso_graphic.setScalarField(self._scalar_field[0])
        # define the initial position of the isosurface on the texture block
        self._iso_graphic.setIsoValues([0.0])  # Range(1, self.initial_positions[0], self.initial_positions[0])

        # Outline the isosurface plane with a green border
        self._iso_line = rendition.createGraphicIsoSurface()
        self._iso_line.setCoordinateField(finite_element_field)
        self.setIsoLineMaterial('green')
        self._iso_line.setUseElementType(Graphic.USE_ELEMENT_FACES)
        self._iso_line.setScalarField(self._scalar_field[0])
        self._iso_line.setIsoValues([0.0])  # (1, self.initial_positions[0], self.initial_positions[0])


        rendition.endChange()

    def createNodeRegion(self):
        self._points_region = self.root_region.createChild('points')
        field_module = self._points_region.getFieldModule()
        field_module.beginChange()
        # Create a finite element field with 3 components to represent 3 dimensions
        finite_element_field = field_module.createFiniteElement(3)

        # Set the name of the field
        finite_element_field.setName('coordinates')
        # Set the attribute is managed to 1 so the field module will manage the field for us
        finite_element_field.setAttributeInteger(Field.ATTRIBUTE_IS_MANAGED, 1)
        finite_element_field.setAttributeInteger(Field.ATTRIBUTE_IS_COORDINATE, 1)
        field_module.endChange()

    def createNodeGraphics(self):
        graphics_module = self._context.getDefaultGraphicsModule()
        rendition = graphics_module.getRendition(self._points_region)
        field_module = self._points_region.getFieldModule()
        coordinate_field = field_module.findFieldByName('coordinates')
        rendition.beginChange()
        node_graphic = rendition.createGraphic(Graphic.GRAPHIC_NODE_POINTS)
        node_graphic.setCoordinateField(coordinate_field)
        node_graphic.setGlyphType(Graphic.GLYPH_TYPE_SPHERE)
        node_graphic.setGlyphSize([0.01, 0.01, 0.01])
        rendition.endChange()

    def setIsoLineMaterial(self, name):
        graphics_module = self._context.getDefaultGraphicsModule()
        material = graphics_module.findMaterialByName(name)
        self._iso_line.setMaterial(material)


    def getPointCloud(self):
        point_cloud = []
        field_module = self._points_region.getFieldModule()
        field_module.beginChange()
        field_cache = field_module.createCache()
        coordinate_field = field_module.findFieldByName('coordinates')
        nodeset = field_module.findNodesetByName('cmiss_nodes')
        template = nodeset.createNodeTemplate()
        template.defineField(coordinate_field)

        node_iterator = nodeset.createNodeIterator()
        node = node_iterator.next()
        while node.isValid():
            field_cache.setNode(node)
            position = coordinate_field.evaluateReal(field_cache, 3)[1]
            node = node_iterator.next()
            point_cloud.append(position)


        field_module.endChange()

        return point_cloud

    def createFiniteElements(self):
        '''
        Create finite element meshes for each of the images
        '''
        # Define the coordinates for each 3D element
        node_coordinate_set = [[0, 0, 0], [1, 0, 0], [0, 0, 1], [1, 0, 1], [0, 1, 0], [1, 1, 0], [0, 1, 1], [1, 1, 1]]
        field_module = self._surface_region.getFieldModule()
        field_module.beginChange()

        # Create a finite element field with 3 components to represent 3 dimensions
        finite_element_field = field_module.createFiniteElement(3)

        # Set the name of the field
        finite_element_field.setName('coordinates')
        # Set the attribute is managed to 1 so the field module will manage the field for us
        finite_element_field.setAttributeInteger(Field.ATTRIBUTE_IS_MANAGED, 1)
        finite_element_field.setAttributeInteger(Field.ATTRIBUTE_IS_COORDINATE, 1)

        self.create3DFiniteElement(field_module, finite_element_field, node_coordinate_set)

        field_module.defineAllFaces()
        field_module.endChange()

        # Create the three scalar fields in the x, y, z directions
        # ## x component
        self._scalar_field = []
        sf = field_module.createComponent(finite_element_field, 0)
        sf.setAttributeInteger(Field.ATTRIBUTE_IS_MANAGED, 1)
        self._scalar_field.append(sf)
        sf = field_module.createComponent(finite_element_field, 1)
        sf.setAttributeInteger(Field.ATTRIBUTE_IS_MANAGED, 1)
        self._scalar_field.append(sf)
        sf = field_module.createComponent(finite_element_field, 2)
        sf.setAttributeInteger(Field.ATTRIBUTE_IS_MANAGED, 1)
        self._scalar_field.append(sf)

    def setSliderValue(self, value):
        self._slider_value = value
        self._iso_graphic.setIsoValues([value / 100])
        self._iso_line.setIsoValues([value / 100])

        self.updateGL()

    def setFieldComponent(self, component):
        self._component = component
        self._iso_graphic.setScalarField(self._scalar_field[component])
        self._iso_line.setScalarField(self._scalar_field[component])
        self._iso_graphic.setIsoValues([self._slider_value / 100])
        self._iso_line.setIsoValues([self._slider_value / 100])

        self.updateGL()

    def actionButtonClicked(self):
        self._action_transfrom = not self._action_transfrom
        if self._action_transfrom:
            self.setIsoLineMaterial('green')
        else:
            self.setIsoLineMaterial('red')

        self.updateGL()


    def destroy(self):
        '''
        Destroys the contents inside the scene
        '''

        del self._scene_viewer
        del self._context

        self._initZincContext()

        newContext = QtOpenGL.QGLContext(self.format(), self)
        newContext.create()
        newContext.makeCurrent()
        self.setContext(newContext, None, True)
        self.makeCurrent()

    def paintGL(self):
        '''
        Render the scene for this scene viewer.  The QGLWidget has already set up the
        correct OpenGL buffer for us so all we need do is render into it.  The scene viewer
        will clear the background so any OpenGL drawing of your own needs to go after this
        API call.
        '''
        self._scene_viewer.renderScene()


    def resizeGL(self, width, height):
        '''
        Respond to widget resize events.
        '''
        self._scene_viewer.setViewportSize(width, height)

    def getPlaneCoordinate2(self, x, y):
        size = self.size()
        width = size.width()
        height = size.height()
        _, eyex, eyey, eyez, lookatx, lookaty, lookatz, upx, upy, upz = self._scene_viewer.getLookatParameters()
        _, left, right, bottom, top, near_plane, far_plane = self._scene_viewer.getViewingVolume()
#        print(volume)

        eye = numpy.array([eyex, eyey, eyez])
        lookat = numpy.array([lookatx, lookaty, lookatz])
        up = numpy.array([upx, upy, upz])

        hclip = numpy.array([(x - width / 2.0) / (width / 2.0), (y - height / 2.0) / (height / 2.0), 0.0, 1.0])
        pr = numpy.array([[1.0 / right, 0.0, 0.0, 0.0], [0.0, 1.0 / top, 0.0, 0.0], [0.0, 0.0, -2.0 / (far_plane - near_plane), -(far_plane + near_plane) / (far_plane - near_plane)], [0.0, 0.0, 0.0, 1.0]])
        pr_inv = numpy.linalg.inv(pr)

        heye = numpy.dot(pr_inv, hclip)

        zaxis = lookat - eye
        zaxis = zaxis / numpy.linalg.norm(zaxis)
#        print(zaxis)
        xaxis = numpy.cross(up, zaxis)
        xaxis = xaxis / numpy.linalg.norm(xaxis)
        yaxis = numpy.cross(zaxis, xaxis)
        yaxis = yaxis / numpy.linalg.norm(yaxis)


#        print(xaxis)
#        print(yaxis)
#        print(zaxis)

#        print(heye)

        mv_rot = numpy.array([xaxis, yaxis, zaxis])
#        print(mv_rot)
        mv_rot = numpy.transpose(mv_rot)
#        print(mv_rot)

        mv_tr = numpy.array([numpy.dot(-xaxis, eye), numpy.dot(-yaxis, eye), numpy.dot(-zaxis, eye)])

        mv = numpy.array([[0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]])
        for i in [0, 1, 2]:
            for j in [0, 1, 2]:
                mv[i, j] = mv_rot[i, j]

        mv[0, 3] = mv_tr[0]
        mv[1, 3] = mv_tr[1]
        mv[2, 3] = mv_tr[2]

#        print(mv_tr)
#        print(mv)

        mv_inv = numpy.linalg.inv(mv)

        hposition = numpy.dot(mv_inv, heye)

        return [hposition[0] / hposition[3], hposition[1] / hposition[3], hposition[2] / hposition[3]]


    def unproject(self, x, y, z):
        return self._scene_viewer.unproject(x, y, z)[1:]

    def getPlaneCoordinate(self, x, y):
        unproject_near = self.unproject(x, y, 0.0)
        unproject_far = self.unproject(x, y, 1.0)

        p0 = numpy.array([0.0, 0.0, 0.0])
        p0[self._component] = self._slider_value / 100.0

        n = numpy.array([0, 0, 0])
        n[self._component] = 1.0

        l0 = numpy.array(unproject_near)
        l = numpy.array(unproject_far) - l0
        num = numpy.dot(p0 - l0, n)
        den = numpy.dot(l, n)

        if -0.0001 < den < 0.0001:
            return None

        d = num / den
        pos = d * l + l0

        return [pos[0], pos[1], pos[2]]

    def addNode(self, x, y):

        position = self.getPlaneCoordinate(x, y)
        if position:
            field_module = self._points_region.getFieldModule()
            self._undoRedoStack.push(CommandAdd(field_module, position, self.updateGL))

    def mousePressEvent(self, mouseevent):
        '''
        Inform the scene viewer of a mouse press event.
        '''
        if self._action_transfrom:
            scene_input = self._scene_viewer.getInput()
            scene_input.setPosition(mouseevent.x(), mouseevent.y())
            scene_input.setType(SceneViewerInput.INPUT_EVENT_TYPE_BUTTON_PRESS)
            if mouseevent.button() == QtCore.Qt.LeftButton:
                scene_input.setButtonNumber(1)
            elif mouseevent.button() == QtCore.Qt.MiddleButton:
                scene_input.setButtonNumber(2)
            elif mouseevent.button() == QtCore.Qt.RightButton:
                scene_input.setButtonNumber(3)

            self._scene_viewer.processInput( scene_input)
        else:
            self.addNode(mouseevent.x(), mouseevent.y())

    def mouseReleaseEvent(self, mouseevent):
        '''
        Inform the scene viewer of a mouse release event.
        '''
        if self._action_transfrom:
            scene_input = self._scene_viewer.getInput()
            scene_input.setPosition(mouseevent.x(), mouseevent.y())
            scene_input.setType(SceneViewerInput.INPUT_EVENT_TYPE_BUTTON_RELEASE)
            if mouseevent.button() == QtCore.Qt.LeftButton:
                scene_input.setButtonNumber(1)
            elif mouseevent.button() == QtCore.Qt.MiddleButton:
                scene_input.setButtonNumber(2)
            elif mouseevent.button() == QtCore.Qt.RightButton:
                scene_input.setButtonNumber(3)

            self._scene_viewer.processInput( scene_input)

    def mouseMoveEvent(self, mouseevent):
        '''
        Inform the scene viewer of a mouse move event and update the OpenGL scene to reflect this
        change to the viewport.
        '''
        if self._action_transfrom:
            scene_input = self._scene_viewer.getInput()
            scene_input.setPosition(mouseevent.x(), mouseevent.y())
            scene_input.setType(SceneViewerInput.INPUT_EVENT_TYPE_MOTION_NOTIFY)
            if mouseevent.type() == QtCore.QEvent.Leave:
                scene_input.setPosition(-1, -1)

            self._scene_viewer.processInput( scene_input)

            # The viewport has been changed so update the OpenGL scene.
            self.updateGL()


