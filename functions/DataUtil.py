# -*- coding: utf-8 -*-
import zipfile
import os
import shutil
import errno
import numpy as np
import sys
from pathlib import Path
import platform
from packaging import version
from datetime import datetime
import pandas as pd


def decompressZip(dirPath, inputFileName, outputFileBaseName=None, 
                  deleteZip = False):
    """
    Decompress zip file.

    Parameters
    _ _ _ _ _ _ _ _ _ _ 
        dirPath: String
            Directory path where is located the zip file    
        inputFileName: String
            Name of the file to unzip (with .zip at the end)
        outputFileBaseName: String
            Base name of the file to unzip (without extension)
        deleteZip: boolean, default False
            Whether or not the input zip file should be removed

    Returns
    -------
        None
    """
    print("Start decompressing zip file")
    
    with open(os.path.join(dirPath,inputFileName), "rb") as zipsrc:
        zfile = zipfile.ZipFile(zipsrc)
        for member in zfile.infolist():
            print(member.filename+" is being decompressed" )
            if outputFileBaseName is None:
                target_path=os.path.join(dirPath,member.filename)
            else:
                # Initialize output file path
                target_path = os.path.join(dirPath, outputFileBaseName)
                extension = "." + member.filename.split(".")[-1]
                target_path+=extension
            
            # Create a folder if needed
            if target_path.endswith('/'):  # folder entry, create
                try:
                    os.makedirs(target_path)
                except (OSError, IOError) as err:
                    # Windows may complain if the folders already exist
                    if err.errno != errno.EEXIST:
                        raise
                continue
            with open(target_path, 'wb') as outfile, zfile.open(member) as infile:
                shutil.copyfileobj(infile, outfile)
    
    return None

def degToRad(angleDeg, origin = 0, direction = "CLOCKWISE"):
    """Convert angle arrays from degrees to radian.
    
    Parameters
	_ _ _ _ _ _ _ _ _ _ 
		angleDeg : float
			Angle in degrees
		origin : float, default 0
			Origin of the input degree coordinates (given in a reference North clockwise coordinate system)
		direction : {"CLOCKWISE", "COUNTER-CLOCKWISE"}, default "CLOCKWISE"
			Direction where go the input coordinate
    
    Returns
	_ _ _ _ _ _ _ _ _ _ 	
		angle in radian (trigonometric reference).
    """
    if direction == "CLOCKWISE":
        d = 1
    if direction == "COUNTER-CLOCKWISE":
        d = -1
    
    return (angleDeg+d*origin)*np.pi/180

def postfix(tableName, suffix = None, separator = "_"):
    """ Add a suffix to an input table name
    
    Parameters
	_ _ _ _ _ _ _ _ _ _ 
		tableName : String
			Name of the input table
        suffix : String, default None (then current datetime is used as string)
            Suffix to add to the table name
        separator : String, default "_"
            Character to separate tableName from suffix
            
    
    Returns
	_ _ _ _ _ _ _ _ _ _ 	
		The input table name with the suffix"""
    if suffix is None:
        suffix = datetime.now().strftime("%Y%m%d%H%M%S")
    
    return tableName+separator+suffix

def prefix(tableName, prefix = "", separator = "_"):
    """ Add a suffix to an input table name
    
    Parameters
	_ _ _ _ _ _ _ _ _ _ 
		tableName : String
			Name of the input table
        prefix : String
            Prefix to add to the table name
        separator : String, default "_"
            Character to separate prefix from tableName 
    
    Returns
	_ _ _ _ _ _ _ _ _ _ 	
		The input table name with the prefix"""
    if prefix == "":
        return tableName
    else:
        return prefix+separator+tableName

def getColumns(cursor, tableName):
    """ Get the column name of a table into a list
    
    Parameters
	_ _ _ _ _ _ _ _ _ _ 
        cursor: conn.cursor
            A cursor object, used to perform spatial SQL queries
		tableName : String
			Name of the input table
    
    Returns
	_ _ _ _ _ _ _ _ _ _ 	
		columnNames: list
            A list of the table column names"""
    cursor.execute("""SELECT * FROM {0}""".format(tableName))
    columnNames = [info[0] for info in cursor.description]
    
    return columnNames

def readFunction(extension):
    """ Return the name of the right H2GIS function to use depending of the file extension
    
    Parameters
	_ _ _ _ _ _ _ _ _ _ 
        extension: String
            Extension of the vector file (shp or geojson)
    
    Returns
	_ _ _ _ _ _ _ _ _ _ 	
		h2gisFunctionName: String
            Return the name of the H2GIS function to use"""
    if extension.lower() == "shp":
        return "SHPREAD"
    elif extension.lower() == "geojson":
        return "GEOJSONREAD"
    elif extension.lower() == "csv":
        return "CSVREAD"
    
def createIndex(tableName, fieldName, isSpatial):
    """ Return the SQL query needed to create an index on a given field of a
    given table. The index should be indicated as spatial if the field is
    a geometry field.
    
    Parameters
	_ _ _ _ _ _ _ _ _ _ 
        tableName: String
            Name of the table
        fieldName: String
            Name of the field the index will be created on
        isSpatial: boolean
            Whether or not the index is a spatial index (should be True if
                                                         the field is a geometry field)
    
    Returns
	_ _ _ _ _ _ _ _ _ _ 	
		query: String
            Return the SQL query needed to create the index"""
    spatialKeyWord = ""
    if isSpatial:
        spatialKeyWord = " SPATIAL "
    query = "CREATE {0} INDEX IF NOT EXISTS id_{1}_{2} ON {2}({1});".format(spatialKeyWord,
                                                                           fieldName,
                                                                           tableName)
    return query

def radToDeg(data, origin = 90, direction = "CLOCKWISE"):
    """Convert angle arrays from radian to degree.
    
    Parameters
	_ _ _ _ _ _ _ _ _ _ 
		data : pd.Series()
			Array containing the angle values to convert from radian to degree.
		origin : float
			Origin of the output coordinate (given in a reference trigonometric coordinate)
		direction : {"CLOCKWISE", "COUNTER-CLOCKWISE"}, default "CLOCKWISE"
			Direction where go the output coordinate
    
    Returns
	_ _ _ _ _ _ _ _ _ _ 	
		Array containing the data in degree coordinate.
    """
    if direction == "CLOCKWISE":
        degree = (360 - data * 180 / np.pi) + origin
    if direction == "COUNTER-CLOCKWISE":
        degree = (data * 180 / np.pi) - origin
    
    degree[degree>360] = degree[degree>360] - 360
    degree[degree<0] = degree[degree<0] + 360
    
    return degree

def windDirectionFromXY(windSpeedEast, windSpeedNorth):
    """
    Calculates wind direction from wind speeds in carthesian coordinates.
    
    Parameters
    _ _ _ _ _ _ _ _ _ _ 
        windSpeedEast: pd.Series
            Wind speed along a West->East axis (m/s)
        windSpeedNorth: pd.Series
            Wind speed along a South->North axis (m/s)
    
    Returns
    -------
        pd.Series containing the wind direction from East counterclockwise.
    """
    # Calculate the angle in Radian in a [-pi/2, pi/2]
    radAngle = np.zeros(windSpeedEast.shape)
    radAngle[windSpeedEast==0] = 0
    if type(windSpeedEast) == type(pd.Series()):
        radAngle[windSpeedEast!=0] = np.arctan(windSpeedNorth[windSpeedEast!=0]\
                                               .divide(windSpeedEast[windSpeedEast!=0]))
    else:
        radAngle[windSpeedEast!=0] = np.arctan(windSpeedNorth[windSpeedEast!=0]
                                               /windSpeedEast[windSpeedEast!=0])
    
    # Add or subtract pi.2 for left side trigonometric circle vectors
    radAngle[(windSpeedEast<=0)&(windSpeedNorth>0)] = \
        radAngle[(windSpeedEast<=0)&(windSpeedNorth>0)] + np.pi
    radAngle[(windSpeedEast<0)&(windSpeedNorth<=0)] = \
        radAngle[(windSpeedEast<0)&(windSpeedNorth<=0)] + np.pi
    radAngle[(windSpeedEast>=0)&(windSpeedNorth<0)] = \
        radAngle[(windSpeedEast>=0)&(windSpeedNorth<0)] + 2*np.pi
    
    return radAngle

def round_to(number, ndecim):
    return round(number, ndecim - int(np.floor(np.log10(abs(number))) + 1))

def trunc_to(x, sign_nb, upper = True):
	"""Return a truncated decimal (or integer) number with "sign_nb" significative numbers
	
		Parameters
	_ _ _ _ _ _ _ _ _ _ 
	
			x : number (float, int, etc.)
				Number we want to set the number of significative numbers
			sign_nb : int
				Number of significative number we want to keep for x
			upper : boolean, default False
				Whether or not the truncature is done to the upper value (ex : trunc_to(0.1235, 2, up = False) = 0.12 trunc_to(0.1235, 2, up = True) = 0.13
				
		Returns
	_ _ _ _ _ _ _ _ _ _ 
	
			Return a decimal (or integer) number with "sign_nb" significative numbers"""
			
	if x==0 or np.isnan(x):
		return x
	else:
		shift_nb = -int(np.floor(np.log10(abs(x))))+sign_nb-1
		if upper is True:
			add_up = 1. / 10 ** shift_nb
		else:
			add_up = 0
		return round_to(np.trunc(x * 10 ** shift_nb) / 10 ** shift_nb + add_up, sign_nb)