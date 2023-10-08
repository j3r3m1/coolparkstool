# -*- coding: utf-8 -*-
from .globalVariables import *
from .DataUtil import trunc_to

from qgis.PyQt.QtGui import QColor
from qgis.core import (QgsProject, 
                       QgsApplication,
                       QgsGradientColorRamp,
                       QgsGradientStop,
                       QgsColorRampShader,
                       QgsRasterShader, 
                       QgsRasterLayer,
                       QgsVectorLayer,
                       QgsSingleBandPseudoColorRenderer,
                       QgsProcessingContext,
                       QgsSymbol,
                       QgsRendererRange,
                       QgsGraduatedSymbolRenderer)
# from qgis.utils import iface

import numpy as np
import pandas as pd
import os

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

def loadCoolParksVector(filepath,
                        layername,
                        variable,
                        subgroup,
                        vector_min,
                        vector_max,
                        feedback,
                        context,
                        valueZero = None,
                        opacity = DEFAULT_OPACITY):
    loadedVector = \
        QgsVectorLayer(filepath, 
                       filepath.split(os.sep)[-1],
                       "ogr")
    if not loadedVector.isValid():
        feedback.pushWarning("Vector layer failed to load!")
    else:
        context.addLayerToLoadOnCompletion(loadedVector.id(),
                                            QgsProcessingContext.LayerDetails(layername,
                                                                              QgsProject.instance(),
                                                                              ''))
        context.temporaryLayerStore().addMapLayer(loadedVector)
        
        # For building informations, the variable and the intervals are not defined
        if variable:
            loadedVector = createVectorStyleAndIntervals(loadedVector = loadedVector,
                                                         variable = variable,
                                                         valueMin = vector_min,
                                                         valueMax = vector_max,
                                                         valueZero = valueZero,
                                                         opacity = opacity)
        # Else a different function is used (using the defined intervals)
        else:
            loadedVector = createVectorStyle(loadedVector = loadedVector,
                                             valueMin = vector_min,
                                             valueMax = vector_max,
                                             valueZero = valueZero,
                                             opacity = opacity)            

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


def createVectorStyle(loadedVector,
                      valueMin,
                      valueMax,
                      valueZero = None,
                      opacity = DEFAULT_OPACITY):
    
    # Get the minimum and maximum values of each interval
    intervals = pd.DataFrame({"ELEV_MIN": [feature["ELEV_MIN"] \
                                           for feature in loadedVector.getFeatures()], 
                              "ELEV_MAX": [feature["ELEV_MAX"] \
                                           for feature in loadedVector.getFeatures()]})
    
    # Get the interval range in normal condition (first and last can be smaller...)
    interval_range = intervals.loc[1,"ELEV_MAX"]-intervals.loc[1,"ELEV_MIN"]
    
    # Get the number of intervals (might be lower than what is normally needed due to limited data range)
    nb_intervals = intervals.index.size
    
    # Extend the range of the first and last interval if needed
    if intervals.loc[0,"ELEV_MAX"]-intervals.loc[0,"ELEV_MIN"] != interval_range:
        intervals.loc[0,"ELEV_MIN"] = intervals.loc[0,"ELEV_MAX"] - interval_range
    if intervals.loc[nb_intervals-1,"ELEV_MAX"]-intervals.loc[nb_intervals-1,"ELEV_MIN"] != interval_range:
        intervals.loc[nb_intervals-1,"ELEV_MAX"] = intervals.loc[nb_intervals-1,"ELEV_MIN"] + interval_range
    
    # If the number of intervals is lower than expected, add some
    i = 0
    while intervals.loc[i,"ELEV_MIN"] > valueMin:
        intervals.loc[i-1,"ELEV_MIN"] = intervals.loc[i,"ELEV_MIN"] - interval_range
        intervals.loc[i-1,"ELEV_MAX"] = intervals.loc[i,"ELEV_MIN"]
        i -= 1
    i = nb_intervals - 1
    while intervals.loc[i,"ELEV_MAX"] < valueMax:
        intervals.loc[i+1,"ELEV_MAX"] = intervals.loc[i,"ELEV_MAX"] + interval_range
        intervals.loc[i+1,"ELEV_MIN"] = intervals.loc[i,"ELEV_MAX"]
        i += 1
    intervals.sort_index(inplace = True)
    intervals.index = intervals.index - intervals.index[0]
    
    if valueZero is None:
        valueZero = intervals.mean().mean()
    
    # Get the zero interval
    interval_zero = intervals[(intervals["ELEV_MIN"] < valueZero)\
                              * (intervals["ELEV_MAX"] > valueZero)]
    index_zero = interval_zero.index[0]
    
    # Get the intervals that are below the zero interval
    intervals_below = intervals[intervals["ELEV_MIN"] < interval_zero.loc[index_zero,
                                                                          "ELEV_MIN"]]
    nb_interval_below = intervals_below.index.size
    
    # Get the intervals that are below the zero interval
    intervals_above = intervals[intervals["ELEV_MAX"] > interval_zero.loc[interval_zero.index[0],
                                                                          "ELEV_MAX"]]
    nb_interval_above = intervals_above.index.size
    
    # Calculate the intervals ranges
    myRangeList = []
    
    for ind in intervals_below.index:
        myMin = intervals_below.loc[ind, "ELEV_MIN"]
        myMax = intervals_below.loc[ind, "ELEV_MAX"]
        
        i = ind - index_zero
        
        myLabel_i = f'[{myMin}, {myMax}['
        myColour_i = QColor(int(255 + i  * 255 / nb_interval_below), 
                            int(255 + i  * 255 / nb_interval_below),
                            255)
        mySymbol_i = QgsSymbol.defaultSymbol(loadedVector.geometryType())
        mySymbol_i.setColor(myColour_i)
        mySymbol_i.setOpacity(opacity)
        myRange_i = QgsRendererRange(myMin, myMax, mySymbol_i, myLabel_i)
        myRangeList.append(myRange_i)


    # For the zeroValue interval
    myMin = interval_zero.loc[index_zero, "ELEV_MIN"]
    myMax = interval_zero.loc[index_zero, "ELEV_MAX"]
    
    myLabel_i = f'[{myMin}, {myMax}['
    myColour_i = QColor(255, 255, 255)
    mySymbol_i = QgsSymbol.defaultSymbol(loadedVector.geometryType())
    mySymbol_i.setColor(myColour_i)
    mySymbol_i.setOpacity(opacity)
    myRange_i = QgsRendererRange(myMin, myMax, mySymbol_i, myLabel_i)
    myRangeList.append(myRange_i)


    # For intervals being lower than the zeroValue
    for ind in intervals_above.index:
        myMin = intervals_above.loc[ind, "ELEV_MIN"]
        myMax = intervals_above.loc[ind, "ELEV_MAX"]
        
        i = ind - index_zero
        
        myLabel_i = f'[{myMin}, {myMax}['
        myColour_i = QColor(255, 
                            255 - int(i * 255 / nb_interval_above), 
                            255 - int(i * 255 / nb_interval_above))
        mySymbol_i = QgsSymbol.defaultSymbol(loadedVector.geometryType())
        mySymbol_i.setColor(myColour_i)
        mySymbol_i.setOpacity(opacity)
        myRange_i = QgsRendererRange(myMin, myMax, mySymbol_i, myLabel_i)
        myRangeList.append(myRange_i)
        
    myRenderer = QgsGraduatedSymbolRenderer('', myRangeList)
    myClassificationMethod = QgsApplication.classificationMethodRegistry().method("EqualInterval")
    myRenderer.setClassificationMethod(myClassificationMethod)
    myRenderer.setClassAttribute("ELEV_MIN")
    loadedVector.setRenderer(myRenderer)
    
    return loadedVector

def createVectorStyleAndIntervals(loadedVector,
                                  variable,
                                  valueMin,
                                  valueMax,
                                  valueZero = None,
                                  opacity = DEFAULT_OPACITY):
    
    if valueZero is None:
        valueZero = (valueMax + valueMin) / 2
    interval_size = trunc_to((valueMax - valueMin) / NB_ISOVALUES, 1, True)
    
    # Calculate the intervals ranges
    myRangeList = []
    
    # For intervals being lower than the zeroValue
    nb_interval_below_deci = ((valueZero - interval_size / 2) - (valueMin)) / interval_size
    nb_interval_below = np.trunc(nb_interval_below_deci)
    if nb_interval_below < nb_interval_below_deci:
        nb_interval_below += 1
    for i in np.arange(-nb_interval_below, 0):
        myMin = valueZero - interval_size / 2 + i * interval_size
        myMax = myMin + interval_size
        
        myLabel_i = f'[{myMin}, {myMax}['
        myColour_i = QColor(int(255 + i  * 255 / nb_interval_below), 
                            int(255 + i * 255 / nb_interval_below),
                            255)
        mySymbol_i = QgsSymbol.defaultSymbol(loadedVector.geometryType())
        mySymbol_i.setColor(myColour_i)
        mySymbol_i.setOpacity(opacity)
        myRange_i = QgsRendererRange(myMin, myMax, mySymbol_i, myLabel_i)
        myRangeList.append(myRange_i)
    
    
    # For the zeroValue interval
    myMin = valueZero - interval_size / 2
    myMax = myMin + interval_size
    
    myLabel_i = f'[{myMin}, {myMax}['
    myColour_i = QColor(255,255,255)
    mySymbol_i = QgsSymbol.defaultSymbol(loadedVector.geometryType())
    mySymbol_i.setColor(myColour_i)
    mySymbol_i.setOpacity(opacity)
    myRange_i = QgsRendererRange(myMin, myMax, mySymbol_i, myLabel_i)
    myRangeList.append(myRange_i)
    
    
    # For intervals being higher than the zeroValue
    nb_interval_above_deci = ((valueMax) - (valueZero + interval_size / 2)) / interval_size
    nb_interval_above = np.trunc(nb_interval_above_deci)
    if nb_interval_above < nb_interval_above_deci:
        nb_interval_above += 1
    for i in np.arange(0, nb_interval_above):
        myMin = valueZero + interval_size / 2 + i * interval_size
        myMax = myMin + interval_size
        
        myLabel_i = f'[{myMin}, {myMax}['
        myColour_i = QColor(255, 
                            255 - int((i + 1) * 255 / nb_interval_above), 
                            255 - int((i + 1) * 255 / nb_interval_above))
        mySymbol_i = QgsSymbol.defaultSymbol(loadedVector.geometryType())
        mySymbol_i.setColor(myColour_i)
        mySymbol_i.setOpacity(opacity)
        myRange_i = QgsRendererRange(myMin, myMax, mySymbol_i, myLabel_i)
        myRangeList.append(myRange_i)
        
    myRenderer = QgsGraduatedSymbolRenderer('', myRangeList)
    myClassificationMethod = QgsApplication.classificationMethodRegistry().method("EqualInterval")
    myRenderer.setClassificationMethod(myClassificationMethod)
    myRenderer.setClassAttribute(variable)
    loadedVector.setRenderer(myRenderer)
    
    return loadedVector