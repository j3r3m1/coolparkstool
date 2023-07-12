#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 13 12:30:25 2023

@author: Jérémy Bernard, chercheur associé au Lab-STICC
"""

import tempfile
import numpy as np
import os
import time
from pathlib import Path
import geopandas as gpd
import pandas as pd
import datetime

from . import coolparks_prepare as prep_fct
from . import coolparks_calc as calc_fct
from .globalVariables import *
from . import H2gisConnection
from . import Obstacles
from . import DataUtil
from . import saveData
    

def prepareData(plugin_directory, 
                buildingFilePath,
                parkBoundaryFilePath,
                parkCanopyFilePath,
                parkGroundFilePath,
                srid,
                build_height,
                build_age,
                build_renovation,
                build_wwr,
                default_build_height = BUILDING_DEFAULT_HEIGHT,
                default_build_age = BUILDING_DEFAULT_AGE,
                default_build_renov = BUILDING_DEFAULT_RENOVATION,
                default_build_wwr = BUILDING_DEFAULT_WINDOWS_WALL_RATIO,
                nAlongWind = N_ALONG_WIND_PARK,
                nCrossWind = N_CROSS_WIND_PARK,
                nCrossWindOut = N_CROSS_WIND_OUTSIDE,
                feedback = None,
                output_directory = TEMPO_DIRECTORY,
                prefix = ""):
    
    # Define temporary tables
    city_all_indic = "CITY_ALL_INDIC"
    
    ############################################################################
    ################################ SCRIPT ####################################
    ############################################################################
    # ----------------------------------------------------------------------
    # 1. SET H2GIS DATABASE ENVIRONMENT AND LOAD DATA
    # ----------------------------------------------------------------------
    if feedback:
        feedback.setProgressText('Creates an H2GIS Instance and load data')
        if feedback.isCanceled():
            feedback.setProgressText("Calculation cancelled by user")
            return {}
    

    dBDir = os.path.join(plugin_directory, 'functions')
    #print(dBDir)
    if ADD_SUFFIX_NAME:
        suffix = str(time.time()).replace(".", "_")
    else:
        suffix = ""
    cursor, conn, localH2InstanceDir = \
        H2gisConnection.startH2gisInstance(dbDirectory = dBDir,
                                           dbInstanceDir = TEMPO_DIRECTORY,
                                           suffix = suffix)
   
    # Load park boundaries, park ground and canopy layers and building tables
    tempo_park_canopy, tempo_park_ground, tempo_build = \
        prep_fct.loadInputData(cursor = cursor, 
                               parkBoundaryFilePath = parkBoundaryFilePath,
                               parkGroundFilePath = parkGroundFilePath, 
                               parkCanopyFilePath = parkCanopyFilePath, 
                               buildingFilePath = buildingFilePath, 
                               srid = srid)
        
    # Modify and filter input data
    prep_fct.modifyInputData(cursor = cursor, 
                             tempo_park_canopy = tempo_park_canopy, 
                             tempo_park_ground = tempo_park_ground, 
                             tempo_build = tempo_build,
                             build_height = build_height,
                             build_age = build_age,
                             build_renovation = build_renovation,
                             build_wwr = build_wwr,
                             default_build_height = default_build_height, 
                             default_build_age = default_build_age,
                             default_build_renov = default_build_renov,
                             default_build_wwr = default_build_wwr)
    
    # Test input data
    prep_fct.testInputData(cursor = cursor)
        
    # Calculates blocks from building geometries
    buildings, blocks = prep_fct.createsBlocks(cursor = cursor,
                                               inputBuildings = BUILDINGS_TAB)
    
    # Calculates buildings indicators
    building_indic = prep_fct.calc_build_indic(cursor = cursor,
                                               buildings = buildings,
                                               blocks = blocks,
                                               prefix = prefix)
    
    # Save building indicators
    saveData.saveTable(cursor = cursor,
                       tableName = building_indic, 
                       filedir = f"""{output_directory+os.sep+prefix+os.sep}{OUTPUT_BUILD_INDIC}.geojson""", 
                       delete = True)
    # ----------------------------------------------------------------------
    # FOR EACH WIND DIRECTION
    # ----------------------------------------------------------------------        
    for d in np.arange(0, 360, 360 / N_DIRECTIONS):
        if feedback:
            feedback.setProgressText('Geography characterization for direction {0}°'.format(d))
            if feedback.isCanceled():
                cursor.close()
                feedback.setProgressText("Calculation cancelled by user")
                return {}
        
        # ----------------------------------------------------------------------
        # 2. ROTATE PARK AND BUILDINGS
        # ---------------------------------------------------------------------- 
        # Define a set of obstacles in a dictionary before the rotation
        dicOfTables = { BUILDINGS_TAB         : buildings,
                        PARK_BOUNDARIES_TAB   : PARK_BOUNDARIES_TAB,
                        PARK_CANOPY           : PARK_CANOPY,
                        PARK_GROUND           : PARK_GROUND,
                        BLOCK_TAB             : blocks}
        
        # Rotate obstacles
        dicRotatedTables, rotationCenterCoordinates = \
            Obstacles.windRotation(cursor = cursor,
                                   dicOfInputTables = dicOfTables,
                                   rotateAngle = d,
                                   rotationCenterCoordinates = None,
                                   prefix = prefix)
    
        
        # ----------------------------------------------------------------------
        # 3. DIVIDE PARKS AND SURROUNDING IN ALONG-WIND "CORRIDORS"
        # ----------------------------------------------------------------------
        rect_park, rect_city, grid, crosswind_lines, dx = \
            prep_fct.creates_units_of_analysis(cursor = cursor, 
                                               park_boundary_tab = dicRotatedTables[PARK_BOUNDARIES_TAB],
                                               srid = srid, 
                                               nCrossWind = nCrossWind,
                                               nCrossWindOut = nCrossWindOut, 
                                               wind_dir = d)
        
        # ----------------------------------------------------------------------
        # 4. CALCULATES FRACTION OF EACH COMBINATION OF GROUND / CANOPY TYPES
        # ----------------------------------------------------------------------
        rect_park_frac = prep_fct.calc_park_fractions(cursor = cursor,
                                                      rect_park = rect_park,
                                                      ground_cover = dicRotatedTables[PARK_GROUND],
                                                      canopy_cover = dicRotatedTables[PARK_CANOPY],
                                                      wind_dir = d)
        
        # ----------------------------------------------------------------------
        # 5. CALCULATES FRACTION OF BLOCKS AND DENSITY NUMBER
        # ----------------------------------------------------------------------
        rect_city_indic1 = prep_fct.calc_rect_block_indic(cursor = cursor,
                                                          blocks = dicRotatedTables[BLOCK_TAB],
                                                          rect_city = rect_city,
                                                          wind_dir = d)

        # ----------------------------------------------------------------------
        # 6. CALCULATES MEAN BUILDING HEIGHT
        # ----------------------------------------------------------------------
        rect_city_indic2 = prep_fct.calc_rect_build_height(cursor = cursor,
                                                           buildings = dicRotatedTables[BUILDINGS_TAB],
                                                           rect_city = rect_city,
                                                           wind_dir = d)    
        
        # ----------------------------------------------------------------------
        # 7. CALCULATES STREET INDICATORS
        # ----------------------------------------------------------------------
        rect_city_indic3 = prep_fct.calc_street_indic(cursor = cursor,
                                                      blocks = dicRotatedTables[BLOCK_TAB],
                                                      rect_city = rect_city,
                                                      crosswind_lines = crosswind_lines,
                                                      wind_dir = d)
            
        # ----------------------------------------------------------------------
        # 8. CALCULATES FACADE FRACTION INDICATOR
        # ----------------------------------------------------------------------
        rect_city_indic4 = prep_fct.generic_facade_indicators(cursor = cursor,
                                                              buildings = dicRotatedTables[BUILDINGS_TAB],
                                                              rsu = rect_city,
                                                              indic = FREE_FACADE_FRACTION,
                                                              wind_dir = d)

        # ----------------------------------------------------------------------
        # 9. GATHER ALL CITY INDICATORS
        # ----------------------------------------------------------------------
        tablesAndId = {rect_city_indic1 : ["ID", ID_UPSTREAM],
                       rect_city_indic2 : ["ID", ID_UPSTREAM],
                       rect_city_indic3 : ["ID", ID_UPSTREAM],
                       rect_city_indic4 : ["ID", ID_UPSTREAM]}
        city_all_indic = prep_fct.joinTables(cursor = cursor, 
                                             tablesAndId = tablesAndId,
                                             outputTableName = prefix + OUTPUT_CITY_INDIC + str(d).replace(".", "_"))
        
        # ----------------------------------------------------------------------
        # 10. GATHER ALL INFO INTO THE GRID AND SAVE GRID, PARK AND URBAN INDIC TABLES
        # ----------------------------------------------------------------------
        tablesAndId = {grid : ["ID_COL", ID_UPSTREAM],
                       city_all_indic : ["ID", ID_UPSTREAM],
                       rect_park_frac : ["ID", ID_UPSTREAM]}
        output_grid = prep_fct.joinTables(cursor = cursor, 
                                          tablesAndId = tablesAndId,
                                          outputTableName = prefix + OUTPUT_GRID + str(d).replace(".", "_"))
        saveData.saveTable(cursor = cursor,
                           tableName = output_grid, 
                           filedir = f"""{output_directory+os.sep+prefix+os.sep}{OUTPUT_GRID}_{str(d).replace(".", "_")}.geojson""", 
                           delete = True, 
                           rotationCenterCoordinates = rotationCenterCoordinates, 
                           rotateAngle = -d)
        saveData.saveTable(cursor = cursor,
                           tableName = city_all_indic, 
                           filedir = f"""{output_directory+os.sep+prefix+os.sep}{OUTPUT_CITY_INDIC}_{str(d).replace(".", "_")}.geojson""", 
                           delete = True, 
                           rotationCenterCoordinates = rotationCenterCoordinates, 
                           rotateAngle = -d)
        saveData.saveTable(cursor = cursor,
                           tableName = rect_park_frac, 
                           filedir = f"""{output_directory+os.sep+prefix+os.sep}{OUTPUT_PARK_INDIC}_{str(d).replace(".", "_")}.geojson""", 
                           delete = True, 
                           rotationCenterCoordinates = rotationCenterCoordinates, 
                           rotateAngle = -d)
        
    return cursor, city_all_indic

def calcParkInfluence(weatherFilePath, 
                      scenarioOutputPath,
                      startDate = START_DATE,
                      endDate = END_DATE,
                      wdir = "wdir10",
                      wspeed = "ws10",
                      tair = "t2m",
                      rh = "r2m",
                      pa = "sp"):
    # Get the number of directions used for the calculations (for example reading the write metadata)
    ndir = N_DIRECTIONS
    dirs = np.arange(0, 360, 360./ndir)
    
    # Load grid info for each direction
    gridFileDic = {d: f"""{OUTPUT_GRID}_{str(float(d)).replace(".", "_")}.geojson""" 
                           for d in dirs}
    grids = {i: gpd.read_file(scenarioOutputPath + os.sep + gridFileDic[i]) 
                    for i in gridFileDic.keys()}
    grid_indic = {i: grids[i].drop("geometry", axis = 1)
                    for i in gridFileDic.keys()}
    grids = {i: grids[i][["ID", "geometry"]]
                    for i in gridFileDic.keys()}

    # Read date and select only useful dates and times for analysis
    df_met = pd.read_csv(weatherFilePath, 
                         skiprows = 11, 
                         index_col = 0, 
                         parse_dates = True)[[wdir, wspeed, tair, rh, pa]]
    year = df_met.index.year.unique()[0]
    start_day = int(START_DATE.split("/")[0])
    start_month = int(START_DATE.split("/")[1])
    end_day = int(END_DATE.split("/")[0])
    end_month = int(END_DATE.split("/")[1])

    # Convert variables into generic names
    df_met.rename(columns = {wdir: WDIR, 
                             wspeed: WSPEED, 
                             tair: T_AIR, 
                             rh: RH, 
                             pa: P_ATMO}, inplace = True)

    weights = {d: 0 for d in dirs} # Weights used for averaging the effect of the park over the entire period
    grid_values = pd.DataFrame(columns = grid_indic.keys(), 
                               index = range(0, max([grid_indic[i].index.size for i in grid_indic.keys()])))
    # For each time period (day - 0PM - and night - 0 AM)
    for tp in [0, 12]:
        selected_dates = pd.date_range(start = datetime.datetime(year, start_month, start_day, tp),
                                       end = datetime.datetime(year, end_month, end_day),
                                       freq = pd.offsets.Day(1))
        df_met_sel = df_met.reindex(selected_dates)
        
        # Calculates the DPV
        df_met_sel[DPV] = calc_fct.dpv_calc(df_met_sel)
        
        # For each day, sum the effect of the park on the air temperature
        # (sum on a different grid depending on wind direction)
        for d in df_met_sel.index:
            wd = df_met_sel.loc[d, WDIR]
            wd_range = [i for i in dirs if (wd >= i and wd < i + 360./ndir)][0]
            weights[wd_range] += 1
            
            grid_values[wd_range] = \
                calc_fct.air_cooling_and_diffusion(grid_values = grid_values[wd_range],
                                                   grid_indic = grid_indic,
                                                   tair = df_met_sel.loc[d, T_AIR],
                                                   ws = df_met_sel.loc[d, WSPEED],
                                                   dpv = df_met_sel.loc[d, DPV])
            