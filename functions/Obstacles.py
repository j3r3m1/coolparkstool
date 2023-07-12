#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 22 11:05:28 2021

@author: Jérémy Bernard, University of Gothenburg
"""
from . import DataUtil as DataUtil
import pandas as pd
from .globalVariables import * 

def windRotation(cursor, dicOfInputTables, rotateAngle, rotationCenterCoordinates = None,
                 prefix = ""):
    """ Rotates of 'rotateAngle' degrees counter-clockwise the geometries 
    of all tables from the 'rotationCenterCoordinates' specified by the user.
    If none is specified, the center of rotation used is the most North-East
    point of the enveloppe of all geometries contained in all tables.

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

            cursor: conn.cursor
                A cursor object, used to perform spatial SQL queries
            dicOfInputTables: dictionary of String
                Dictionary of String with type of obstacle as key and input 
                table name as value (tables containing the geometries to rotate)
            rotateAngle: float
                Counter clock-wise rotation angle (in degree)
            rotationCenterCoordinates: tuple of float
                x and y values of the point used as center of rotation
            prefix: String, default PREFIX_NAME
                Prefix to add to the output table name
            
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            dicOfRotateTables: dictionary
                Map of initial table names as keys and rotated table names as values
            rotationCenterCoordinates: tuple of float
                x and y values of the point used as center of rotation"""
    print("Rotates geometries from {0} degrees".format(rotateAngle))
    
    # Calculate the rotation angle in radian
    rotateAngleRad = DataUtil.degToRad(rotateAngle)
    
    # If not specified, get the most North-East point of the envelope of all
    # geometries of all tables as the center of rotation
    if rotationCenterCoordinates is None:
        queryUnionTables = " UNION ALL ".join(["""
                                                SELECT {0} FROM ST_EXPLODE('(SELECT {0} FROM {1})')
                                                """.format( GEOM_FIELD,
                                                            t)
                                                for t in dicOfInputTables.values()])
        cursor.execute("""
           SELECT  ST_XMAX(ST_EXTENT({0})),
                   ST_YMAX(ST_EXTENT({0}))
           FROM    ({1})""".format(GEOM_FIELD, queryUnionTables))
        rotationCenterCoordinates = cursor.fetchall()[0]
    
    columnNames = {}
    # Store the column names (except geometry field) of each table into a dictionary
    for i, t in enumerate(dicOfInputTables.values()):
        columnNames[t] = DataUtil.getColumns(cursor = cursor,
                                             tableName = t)
        columnNames[t].remove(GEOM_FIELD)
        
    # Rotate table in one query in order to limit the number of connections
    dicOfRotateTables = {t: dicOfInputTables[t]+"_ROTATED" for t in dicOfInputTables.keys()}
    sqlRotateQueries = ["""
        DROP TABLE IF EXISTS {0};
        CREATE TABLE    {0}
            AS SELECT   ST_MAKEVALID(ST_ROTATE({1}, {2}, {3}, {4})) AS {1},
                        {5}
            FROM        {6}""".format(  dicOfRotateTables[t],\
                                        GEOM_FIELD,\
                                        rotateAngleRad,
                                        rotationCenterCoordinates[0],
                                        rotationCenterCoordinates[1],
                                        ",".join(columnNames[dicOfInputTables[t]]),
                                        dicOfInputTables[t]) for t in dicOfRotateTables.keys()]
    cursor.execute(";".join(sqlRotateQueries))
    
    return dicOfRotateTables, rotationCenterCoordinates
