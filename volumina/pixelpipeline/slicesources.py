from PyQt4.QtCore import QObject, pyqtSignal
from asyncabcs import SourceABC, RequestABC
import numpy as np
import volumina
from volumina.slicingtools import SliceProjection, is_pure_slicing, intersection, sl
from volumina.colorama import Fore

projectionAlongTXC = SliceProjection( abscissa = 2, ordinate = 3, along = [0,1,4] )
projectionAlongTYC = SliceProjection( abscissa = 1, ordinate = 3, along = [0,2,4] )
projectionAlongTZC = SliceProjection( abscissa = 1, ordinate = 2, along = [0,3,4] )

#*******************************************************************************
# S l i c e R e q u e s t                                                      *
#*******************************************************************************

class SliceRequest( object ):
    def __init__( self, domainArrayRequest, sliceProjection ):
        self._ar = domainArrayRequest
        self._sp = sliceProjection
        
    def wait( self ):
        return self._sp(self._ar.wait())

    def getResult(self):
        return self._sp(self._ar.getResult())

    def notify( self, callback, **kwargs ):
        self._ar.notify(self._onNotify, package = (callback, kwargs))
        return self

    def cancel( self ):
        self._ar.cancel()

    def submit( self ):
        self._ar.submit()
        return self
        
    def adjustPriority(self, delta):
        self._ar.adjustPriority(delta)
        return self

    def _onNotify( self, result, package ):
        callback, kwargs = package
        callback(self._sp(result), **kwargs)
assert issubclass(SliceRequest, RequestABC)

#*******************************************************************************
# S l i c e S o u r c e                                                        *
#*******************************************************************************

class SliceSource( QObject ):
    areaDirty = pyqtSignal( object )
    isDirty = pyqtSignal( object )
    throughChanged = pyqtSignal( tuple, tuple ) # old, new
    idChanged = pyqtSignal( object, object ) # old, new
    
    @property
    def id( self ):
        return (self,tuple(self._through))

    @property
    def through( self ):
        return self._through
    @through.setter
    def through( self, value ):
        if value != self._through:
            old = self._through
            old_id = self.id
            self._through = value
            self.throughChanged.emit(tuple(old), tuple(value))
            self.idChanged.emit(old_id, self.id)
    
    def __init__(self, datasource, sliceProjection = projectionAlongTZC):
        assert isinstance(datasource, SourceABC) , 'wrong type: %s' % str(type(datasource)) 
        super(SliceSource, self).__init__()

        self.sliceProjection = sliceProjection
        self._datasource = datasource
        self._datasource.isDirty.connect(self._onDatasourceDirty)
        self._through = len(sliceProjection.along) * [0]

    def setThrough( self, index, value ):
        assert index < len(self.through)
        through = list(self.through)
        through[index] = value
        self.through = through

    def request( self, slicing2D ):
        assert len(slicing2D) == 2
        slicing = self.sliceProjection.domain(self.through, slicing2D[0], slicing2D[1])
        
        if volumina.verboseRequests:
            volumina.printLock.acquire()
            print Fore.RED + "SliceSource requests '%r' from data source '%s'" % (slicing, self._datasource.name) + Fore.RESET
            volumina.printLock.release()
        return SliceRequest(self._datasource.request(slicing), self.sliceProjection)
        
    def setDirty( self, slicing ):
        assert isinstance(slicing, tuple)
        if not is_pure_slicing(slicing):
            raise Exception('dirty region: slicing is not pure')
        self.areaDirty.emit( slicing )

    def _onDatasourceDirty( self, ds_slicing ):
        # embedding of slice in datasource space
        embedding = self.sliceProjection.domain(self.through)
        inter = intersection(embedding, ds_slicing)

        if inter: # there is an intersection
            dirty_area = [None] * 2
            dirty_area[0] = inter[self.sliceProjection.abscissa]
            dirty_area[1] = inter[self.sliceProjection.ordinate]
            self.setDirty(tuple(dirty_area))

        # Even if no intersection with the current slice projection, mark this area
        #  dirty in all parallel slices that may not be visible at the moment.
        dirty_area = [None] * 2
        dirty_area[0] = ds_slicing[self.sliceProjection.abscissa]
        dirty_area[1] = ds_slicing[self.sliceProjection.ordinate]
        self.isDirty.emit( tuple(dirty_area) )
assert issubclass(SliceSource, SourceABC)



#*******************************************************************************
# S y n c e d S l i c e S o u r c e s                                          *
#*******************************************************************************

class SyncedSliceSources( QObject ):
    throughChanged = pyqtSignal( tuple, tuple ) # old , new
    idChanged = pyqtSignal( object, object )

    @property
    def id( self ):
        return (self, tuple(self._through))

    @property
    def through( self ):
        return self._through
    @through.setter
    def through( self, value ):
        if value != self._through:
            old = self._through
            old_id = self.id
            self._through = value
            for src in self._srcs:
                src.through = value
            self.throughChanged.emit(tuple(old), tuple(value))
            self.idChanged.emit(old, self.id)

    def __init__(self, through = None, slicesrcs = []):
        super(SyncedSliceSources, self).__init__()
        self._srcs = set(slicesrcs)
        self._through = through

    def __len__( self ):
        return len(self._srcs)

    def __iter__( self ):
        return iter(self._srcs)

    def setThrough( self, index, value ):
        assert index < len(self.through)
        through = list(self.through)
        through[index] = value
        self.through = through

    def add( self, sliceSrc ):
        assert isinstance( sliceSrc, SliceSource ), 'wrong type: %s' % str(type(sliceSrc))
        sliceSrc.through = self.through
        self._srcs.add( sliceSrc )

    def remove( self, sliceSrc ):
        assert isinstance( sliceSrc, SliceSource )
        self._srcs.remove( sliceSrc )



import unittest as ut
#*******************************************************************************
# S l i c e S o u r c e T e s t                                                *
#*******************************************************************************

class SliceSourceTest( ut.TestCase ):
    def setUp( self ):
        import numpy as np
        from datasources import ArraySource
        self.raw = np.random.randint(0,100,(10,3,3,128,3))
        self.a = ArraySource(self.raw)
        self.ss = SliceSource( self.a, projectionAlongTZC )
        
    def testRequest( self ):
        self.ss.setThrough(0, 1)
        self.ss.setThrough(2, 2)
        self.ss.setThrough(1, 127)

        sl = self.ss.request((slice(None), slice(None))).wait()
        self.assertTrue(np.all(sl == self.raw[1,:,:,127,2]))

        sl_bounded = self.ss.request((slice(0, 3), slice(1, None))).wait()
        self.assertTrue(np.all(sl_bounded == self.raw[1,0:3,1:,127,2]))

    def testDirtynessPropagation( self ):
        self.ss.setThrough(0, 1)
        self.ss.setThrough(2, 2)
        self.ss.setThrough(1, 127)

        self.triggered = False
        def check1( dirty_area ):
            self.triggered = True
            self.assertEqual(dirty_area, sl[:,1:2])
        self.ss.isDirty.connect(check1)
        self.a.setDirty(sl[1:2,:,1:2,127:128,2:3])
        self.ss.isDirty.disconnect(check1)
        self.assertTrue(self.triggered)
        del self.triggered

        def check2( dirty_area ):
            assert False
        self.ss.isDirty.connect(check2)
        self.a.setDirty(sl[1:2,:,1:2,127:128,3:4])
        self.ss.isDirty.disconnect(check2)

#*******************************************************************************
# i f   _ _ n a m e _ _   = =   " _ _ m a i n _ _ "                            *
#*******************************************************************************

if __name__ == '__main__':
    ut.main()
