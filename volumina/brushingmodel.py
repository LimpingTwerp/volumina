#!/usr/bin/env python
from PyQt4.QtCore import pyqtSignal, QObject, Qt, QSize, QPointF, QRectF, \
                         QRect, QPoint, QSizeF
from PyQt4.QtGui  import QPen, QGraphicsScene, QColor, \
                         QImage, QPainter, QGraphicsLineItem, QBrush

import numpy
import qimage2ndarray

#*******************************************************************************
# B r u s h i n g M o d e l                                                    *
#*******************************************************************************

class BrushingModel(QObject):
    brushSizeChanged     = pyqtSignal(int)
    brushColorChanged    = pyqtSignal(QColor)
    brushStrokeAvailable = pyqtSignal(QPointF, object)
    drawnNumberChanged   = pyqtSignal(int)
    
    minBrushSize       = 1
    maxBrushSize       = 61
    defaultBrushSize   = 3
    defaultDrawnNumber = 1
    defaultColor       = Qt.white
    erasingColor       = Qt.black
    erasingNumber      = 100
    
    def __init__(self):
        QObject.__init__(self)
        self.sliceRect = None
        self.bb    = QRect() #bounding box enclosing the drawing
        self.brushSize = self.defaultBrushSize
        self.drawColor = self.defaultColor
        self._temp_color = None
        self._temp_number = None
        self.drawnNumber = self.defaultDrawnNumber

        self.pos = None
        self.erasing = False
        
        self.drawOnto = None
        
        #an empty scene, where we add all drawn line segments
        #a QGraphicsLineItem, and which we can use to then
        #render to an image
        self.scene = QGraphicsScene()

    def toggleErase(self):
        self.erasing = not(self.erasing)
        if self.erasing:
            self.setErasing()
        else:
            self.disableErasing()

    def setErasing(self):
        self.erasing = True
        self._temp_color = self.drawColor
        self._temp_number = self.drawnNumber
        self.setBrushColor(self.erasingColor)
        self.brushColorChanged.emit(self.erasingColor)
        self.setDrawnNumber(self.erasingNumber)
    
    def disableErasing(self):
        self.erasing = False
        self.setBrushColor(self._temp_color)
        self.brushColorChanged.emit(self.drawColor)
        self.setDrawnNumber(self._temp_number)

    def setBrushSize(self, size):
        self.brushSize = size
        self.brushSizeChanged.emit(self.brushSize)
    
    def setDrawnNumber(self, num):
        print "Setting Drawnnumer", num
        self.drawnNumber = num
        self.drawnNumberChanged.emit(num)
        
    def getBrushSize(self):
        return self.brushSize
    
    def brushSmaller(self):
        b = self.brushSize
        if b > self.minBrushSize:
            self.setBrushSize(b-1)
        
    def brushBigger(self):
        b = self.brushSize
        if self.brushSize < self.maxBrushSize:
            self.setBrushSize(b+1)
        
    def setBrushColor(self, color):
        self.drawColor = color
        self.brushColorChanged.emit(self.drawColor)
    
    def beginDrawing(self, pos, sliceRect):
        self.sliceRect = sliceRect
        self.scene.clear()
        self.bb = QRect()
        self.pos = QPointF(pos.x()+0.0001, pos.y()+0.0001)
        line = self.moveTo(pos)
        return line

    def endDrawing(self, pos):
        self.moveTo(pos)

        tempi = QImage(QSize(self.bb.width(), self.bb.height()), QImage.Format_ARGB32_Premultiplied) #TODO: format
        tempi.fill(0)
        painter = QPainter(tempi)
        self.scene.render(painter, target=QRectF(), source=QRectF(QPointF(self.bb.x(), self.bb.y()), QSizeF(self.bb.width(), self.bb.height())))
        painter.end()
        
        ndarr = qimage2ndarray.rgb_view(tempi)[:,:,0]
        labels = numpy.where(ndarr>0,numpy.uint8(self.drawnNumber),numpy.uint8(0))
        labels = labels.swapaxes(0,1)
        assert labels.shape[0] == self.bb.width()
        assert labels.shape[1] == self.bb.height()

        self.brushStrokeAvailable.emit(QPointF(self.bb.x(), self.bb.y()), labels)

    def dumpDraw(self, pos):
        res = self.endDrawing(pos)
        self.beginDrawing(pos, self.sliceRect)
        return res

    def moveTo(self, pos):
        oldX, oldY = self.pos.x(), self.pos.y()
        x,y = pos.x(), pos.y()
        
        #print "BrushingModel.moveTo(pos=%r)" % (pos) 
        line = QGraphicsLineItem(oldX, oldY, x, y)
        line.setPen(QPen( QBrush(Qt.white), self.brushSize, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.scene.addItem(line)

        #update bounding Box 
        if not self.bb.isValid():
            self.bb = QRect(QPoint(x,y), QSize(1,1))
        #grow bounding box
        self.bb.setLeft(  min(self.bb.left(),   max(0,                   x-self.brushSize/2-1) ) )
        self.bb.setRight( max(self.bb.right(),  min(self.sliceRect[0]-1, x+self.brushSize/2+1) ) )
        self.bb.setTop(   min(self.bb.top(),    max(0,                   y-self.brushSize/2-1) ) )
        self.bb.setBottom(max(self.bb.bottom(), min(self.sliceRect[1]-1, y+self.brushSize/2+1) ) )
        
        #update/move position
        self.pos = pos
