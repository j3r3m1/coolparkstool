# -*- coding: utf-8 -*-
from .globalVariables import *
import os

from qgis.PyQt.QtGui import QColor
from qgis.core import (QgsProject, 
                       QgsGradientColorRamp,
                       QgsGradientStop,
                       QgsColorRampShader,
                       QgsRasterShader, 
                       QgsRasterLayer,
                       QgsSingleBandPseudoColorRenderer,
                       QgsProcessingContext)
# from qgis.utils import iface

def loadCoolParksRaster(filepath,
                        specific_scale,
                        subgroup,
                        raster_min,
                        raster_max,
                        feedback,
                        context):
    loadedRaster = \
        QgsRasterLayer(filepath,
                       filepath.split(os.sep)[-1],
                       "gdal")
    if not loadedRaster.isValid():
        feedback.pushWarning("Raster layer failed to load!")
    else:
        context.addLayerToLoadOnCompletion(loadedRaster.id(),
                                           QgsProcessingContext.LayerDetails(filepath.split(os.sep)[-1],
                                                                             QgsProject.instance(),
                                                                             ''))
        context.temporaryLayerStore().addMapLayer(loadedRaster)
        
        loadedRaster = createRasterStyle(loadedRaster = loadedRaster,
                                         raster_min = raster_min,
                                         raster_max = raster_max,
                                         specific_scale = specific_scale)
        
        # # Add the layer to the group
        # subgroup.addLayer(loadedRaster)

# def loadCoolParksVector(filepath,
#                         variable,
#                         subgroup,
#                         vector_min,
#                         vector_max,
#                         feedback,
#                         context):
#     loadedVector = \
#         QgsVectorLayer(filepath, 
#                        filepath.split(os.sep)[-1],
#                        "ogr")
#     if not loadedVector.isValid():
#         feedback.pushWarning("Vector layer failed to load!")
#     else:
#         context.addLayerToLoadOnCompletion(loadedVector.id(),
#                                            QgsProcessingContext.LayerDetails(filepath.split(os.sep)[-1],
#                                                                              QgsProject.instance(),
#                                                                              ''))
#         context.temporaryLayerStore().addMapLayer(loadedVector)
        
#         loadedRaster = createRasterStyle(loadedVector = loadedVector,
#                                          raster_min = vector_min,
#                                          raster_max = vector_max,
#                                          specific_scale = specific_scale)

def createRasterStyle(loadedRaster,
                      raster_min,
                      raster_max,
                      specific_scale):
    if specific_scale:
        # Calculate the position of 0 on the color ramp
        zero_position = (0 - raster_min) / (raster_max - raster_min)
        
        # Create a custom color ramp
        custom_ramp = QgsGradientColorRamp(color1 = QColor(0, 0, 255),
                                           color2 = QColor(255, 0, 0),
                                           stops = [QgsGradientStop(zero_position, QColor(255, 255, 255))])
    else:
        custom_ramp = QgsGradientColorRamp(color1 = QColor(0, 0, 255),
                                           color2 = QColor(255, 0, 0),
                                           stops = [QgsGradientStop(0.5, QColor(255, 255, 255))])
    
    # Create a color ramp shader
    color_ramp_shader = QgsColorRampShader(colorRamp = custom_ramp)
    
    # Create a raster shader
    raster_shader = QgsRasterShader()
    raster_shader.setRasterShaderFunction(color_ramp_shader)
    
    # # Get the active QGIS project
    # project = QgsProject.instance()
    # raster_layer_map = project.mapLayersByName(baseName)[0]
    
    # Create a single band pseudo-color renderer
    renderer = QgsSingleBandPseudoColorRenderer(loadedRaster.dataProvider(), 1, raster_shader)
    
    # Apply the renderer to the raster layer
    loadedRaster.setRenderer(renderer)
    
    # Refresh the layer to see the changes
    loadedRaster.triggerRepaint()
    
    # Reset min and max if needed
    if specific_scale:
        loadedRaster.renderer().setClassificationMin(raster_min)
        loadedRaster.renderer().setClassificationMax(raster_max)
    
    return loadedRaster