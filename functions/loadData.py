#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 20 14:29:14 2021

@author: Jérémy Bernard, University of Gothenburg
"""

from .globalVariables import *
from . import DataUtil
import os

def loadFile(cursor, filePath, tableName, srid = None, srid_repro = None):
    """ Load a file in the database according to its extension
    
		Parameters
		_ _ _ _ _ _ _ _ _ _ 

            cursor: conn.cursor
                A cursor object, used to perform spatial SQL queries
            filePath: String
                Path of the file to load
            tableName: String
                Name of the table for the loaded file
            srid: int, default None
                SRID of the loaded file (if known)
            srid_repro: int, default None
                SRID if you want to reproject the data
            
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            None"""
    print("Load table '{0}'".format(tableName))    

    # Get the input building file extension and the appropriate h2gis read function name
    fileExtension = filePath.split(".")[-1]
    readFunction = DataUtil.readFunction(fileExtension)
    
    if readFunction == "CSVREAD":
        cursor.execute("""
           DROP TABLE IF EXISTS {0};
           CREATE TABLE {0} 
               AS SELECT * FROM {2}('{1}');
            """.format( tableName, filePath, readFunction))
    else: # Import and then copy into a new table to remove all constraints (primary keys...)
        cursor.execute("""
           DROP TABLE IF EXISTS TEMPO, {0};
            CALL {2}('{1}','TEMPO');
            CREATE TABLE {0}
                AS SELECT *
                FROM TEMPO;
            """.format( tableName, filePath, readFunction))
    
    if srid_repro:
        reproject_function = "ST_TRANSFORM("
        reproject_srid = ", {0})".format(srid_repro)
    else:
        reproject_function = ""
        reproject_srid = ""
    
    if srid:
        listCols = DataUtil.getColumns(cursor, tableName)
        listCols.remove(GEOM_FIELD)
        listCols_sql = ",".join(listCols)
        if listCols_sql != "":
            listCols_sql += ","
        
        cursor.execute("""
           DROP TABLE IF EXISTS TEMPO_LOAD;
           CREATE TABLE TEMPO_LOAD
               AS SELECT {0} {4}ST_SETSRID({1}, {2}){5} AS {1}
               FROM {3};
           DROP TABLE {3};
           ALTER TABLE TEMPO_LOAD RENAME TO {3}
           """.format(listCols_sql, 
                       GEOM_FIELD, 
                       srid,
                       tableName,
                       reproject_function,
                       reproject_srid))
        