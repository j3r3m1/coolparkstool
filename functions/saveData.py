#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct  4 13:59:31 2021

@author: Jérémy Bernard, University of Gothenburg
"""
import pandas as pd
import numpy as np
from .DataUtil import prefix
from .Obstacles import windRotation
from osgeo.gdal import Grid, GridOptions
from .globalVariables import DELETE_OUTPUT_IF_EXISTS,\
    OUTPUT_RASTER_EXTENSION
import os
    
def saveTable(cursor, tableName, filedir, delete = False, 
              rotationCenterCoordinates = None, rotateAngle = None):
    """ Save a table in .geojson or .shp (the table can be rotated before saving if needed).
    
    Parameters
	_ _ _ _ _ _ _ _ _ _ 
        cursor: conn.cursor
            A cursor object, used to perform spatial SQL queries
		tableName : String
			Name of the table to save
        filedir: String
            Directory (including filename and extension) of the file where to 
            store the table
        delete: Boolean, default False
            Whether or not the file is delete if exist
        rotationCenterCoordinates: tuple of float, default None
            x and y values of the point used as center of rotation
        rotateAngle: float, default None
            Counter clock-wise rotation angle (in degree)

    
    Returns
	_ _ _ _ _ _ _ _ _ _ 	
		output_filedir: String
            Directory (including filename and extension) of the saved file
            (could be different from input 'filedir' since the file may 
             have been renamed if exists)"""
    # Rotate the table if needed
    if rotationCenterCoordinates is not None and rotateAngle is not None:
        tableName = windRotation(cursor = cursor,
                                 dicOfInputTables = {tableName: tableName},
                                 rotateAngle = rotateAngle,
                                 rotationCenterCoordinates = rotationCenterCoordinates)[0][tableName]
    
    # Get extension
    extension = "." + filedir.split(".")[-1]
    filedirWithoutExt = ".".join(filedir.split(".")[0:-1])
    
    # Define the H2GIS function depending on extension
    if extension.upper() == ".GEOJSON":
        h2_function = "GEOJSONWRITE"
    elif extension.upper() == ".SHP":
        h2_function = "SHPWRITE"
    else:
        print("The extension should be .geojson or .shp")
    # Delete files if exists and delete = True
    if delete and os.path.isfile(filedir):
        output_filedir = filedir
        os.remove(filedir)
        if extension.upper() == ".SHP":
            os.remove(filedirWithoutExt+".dbf")
            os.remove(filedirWithoutExt+".shx")
            if os.path.isfile(filedirWithoutExt+".prj"):
                os.remove(filedirWithoutExt+".prj")
    # If delete = False, add a suffix to the file
    elif os.path.isfile(filedir):
        output_filedir = renameFileIfExists(filedir = filedirWithoutExt,
                                            extension = extension) + extension
    else:
        output_filedir = filedir
    # Write files
    cursor.execute("""CALL {0}('{1}','{2}')""".format(h2_function,
                                                      output_filedir,
                                                      tableName))
    return output_filedir

def renameFileIfExists(filedir, extension):
    """ Rename a file with a numbering prefix if exists.
    
    Parameters
	_ _ _ _ _ _ _ _ _ _ 
        filedir: String
            Directory (including filename but without extension) of the file
    
    Returns
	_ _ _ _ _ _ _ _ _ _ 	
		newFileDir: String
            Directory with renamed file"""
    i = 1
    newFileDir = filedir
    while(os.path.isfile(newFileDir + extension)):
        newFileDir = filedir + "({0})".format(i)
        i += 1
    return newFileDir


def saveRasterFile(cursor, outputVectorFile, outputFilePathAndNameBase, 
                   horizOutputUrock, outputRaster, z_i, meshSize, var2save):
    """ Save results in a raster file.
    
    Parameters
	_ _ _ _ _ _ _ _ _ _ 
        outputFilePathAndNameBase: String
            Directory (including filename but without extension) of the file
    
    Returns
	_ _ _ _ _ _ _ _ _ _ 	
		None"""
    outputFilePathAndNameBaseRaster = outputFilePathAndNameBase + var2save
    # If delete = False, add a suffix to the filename
    if (os.path.isfile(outputFilePathAndNameBaseRaster + OUTPUT_RASTER_EXTENSION)) \
        and (not DELETE_OUTPUT_IF_EXISTS):
        outputFilePathAndNameBaseRaster = renameFileIfExists(filedir = outputFilePathAndNameBaseRaster,
                                                             extension = OUTPUT_RASTER_EXTENSION)
    # Whether or not a raster output is given as input, the rasterization process is slightly different
    if outputRaster:
        outputRasterExtent = outputRaster.extent()
        Grid(destName = outputFilePathAndNameBaseRaster + OUTPUT_RASTER_EXTENSION,
             srcDS = outputVectorFile,
             options = GridOptions(format = OUTPUT_RASTER_EXTENSION.split(".")[-1],
                                   zfield = var2save, 
                                   width = outputRaster.width(), 
                                   height = outputRaster.height(),
                                   outputBounds = [outputRasterExtent.xMinimum(),
                                                   outputRasterExtent.yMaximum(),
                                                   outputRasterExtent.xMaximum(),
                                                   outputRasterExtent.yMinimum()],
                                   algorithm = "average:radius1={0}:radius2={0}".format(1.1*meshSize)))
    else:
        cursor.execute(
            """
            SELECT  ST_XMIN({0}) AS XMIN, ST_XMAX({0}) AS XMAX,
                    ST_YMIN({0}) AS YMIN, ST_YMAX({0}) AS YMAX
            FROM    (SELECT ST_ACCUM({0}) AS {0} FROM {1})
            """.format(GEOM_FIELD            , horizOutputUrock[z_i]))
        vectorBounds = cursor.fetchall()[0]
        width = int((vectorBounds[1] - vectorBounds[0]) / meshSize) + 1
        height = int((vectorBounds[3] - vectorBounds[2]) / meshSize) + 1
        Grid(destName = outputFilePathAndNameBaseRaster + OUTPUT_RASTER_EXTENSION,
             srcDS = outputVectorFile,
             options = GridOptions(format = OUTPUT_RASTER_EXTENSION.split(".")[-1],
                                   zfield = var2save, 
                                   width = width, 
                                   height = height,
                                   outputBounds = [vectorBounds[0] - float(meshSize) / 2,
                                                   vectorBounds[3] + float(meshSize) / 2,
                                                   vectorBounds[0] + meshSize * (width - 0.5),
                                                   vectorBounds[3] - meshSize * (height + 0.5)],
                                   algorithm = "average:radius1={0}:radius2={0}".format(1.1*meshSize)))
        