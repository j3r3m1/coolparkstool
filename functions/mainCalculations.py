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
import processing
from shapely.geometry import Polygon
from qgis.core import QgsCoordinateReferenceSystem, QgsProcessingException
from qgis.analysis import QgsNativeAlgorithms
from osgeo import gdal

from . import coolparks_prepare as prep_fct
from . import coolparks_calc as calc_fct
from .globalVariables import *
from . import H2gisConnection
from . import Obstacles
from .DataUtil import getColumns, round_to
from . import saveData
    

def prepareData(plugin_directory, 
                buildingFilePath,
                parkBoundaryFilePath,
                parkCanopyFilePath,
                parkGroundFilePath,
                srid,
                build_height,
                build_age,
                build_wwr,
                build_shutter,
                build_nat_ventil,
                default_build_height = BUILDING_DEFAULT_HEIGHT,
                default_build_age = BUILDING_DEFAULT_AGE,
                default_build_wwr = BUILDING_DEFAULT_WINDOWS_WALL_RATIO,
                default_build_shutter = BUILDING_DEFAULT_SHUTTER,
                default_build_nat_ventil = BUILDING_DEFAULT_NAT_VENTIL,
                nAlongWind = N_ALONG_WIND_PARK,
                nCrossWind = N_CROSS_WIND_PARK,
                feedback = None,
                output_directory = TEMPO_DIRECTORY,
                prefix = DEFAULT_SCENARIO):
    
    # Define the entire output directory path
    final_output_dir = output_directory+os.sep+prefix+os.sep+OUTPUT_PREPROCESSOR_FOLDER
    
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
    
    if feedback:
        feedback.setProgressText('Load and test input data')
        if feedback.isCanceled():
            feedback.setProgressText("Calculation cancelled by user")
            return {}
    # Load park boundaries, park ground and canopy layers and building tables
    tempo_park_canopy, tempo_park_ground, tempo_build = \
        prep_fct.loadInputData(cursor = cursor, 
                               parkBoundaryFilePath = parkBoundaryFilePath,
                               parkGroundFilePath = parkGroundFilePath, 
                               parkCanopyFilePath = parkCanopyFilePath, 
                               buildingFilePath = buildingFilePath, 
                               srid = srid)
        
    # Modify and filter input data
    distance_max =  prep_fct.modifyInputData(cursor = cursor, 
                                             tempo_park_canopy = tempo_park_canopy, 
                                             tempo_park_ground = tempo_park_ground, 
                                             tempo_build = tempo_build,
                                             build_height = build_height,
                                             build_age = build_age,
                                             build_wwr = build_wwr,
                                             build_shutter = build_shutter,
                                             build_nat_ventil = build_nat_ventil,
                                             default_build_height = default_build_height, 
                                             default_build_age = default_build_age,
                                             default_build_wwr = default_build_wwr,
                                             default_build_shutter = default_build_shutter,
                                             default_build_nat_ventil = default_build_nat_ventil)
    
    # Test input data
    prep_fct.testInputData(cursor = cursor)
    
    
    if feedback:
        feedback.setProgressText('Calculates building indicators')
        if feedback.isCanceled():
            feedback.setProgressText("Calculation cancelled by user")
            return {}
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
                       filedir = f"""{final_output_dir+os.sep}{OUTPUT_BUILD_INDIC}.geojson""", 
                       delete = True)
    
    # ----------------------------------------------------------------------
    # FOR EACH WIND DIRECTION
    # ----------------------------------------------------------------------        
    for it, d in enumerate(np.arange(0, 360, 360 / N_DIRECTIONS)):
        if feedback:
            feedback.setProgressText(f'Geography characterization for direction {d}° ({it+1}/{N_DIRECTIONS})')
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
                                               nCrossWindTot = nCrossWind,
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
        # 10. SAVE OUTPUTS
        # ----------------------------------------------------------------------
        tablesAndId = {grid : ["ID_COL", ID_UPSTREAM],
                       city_all_indic : ["ID", ID_UPSTREAM],
                       rect_park_frac : ["ID", ID_UPSTREAM]}
        output_grid = prep_fct.joinTables(cursor = cursor, 
                                          tablesAndId = tablesAndId,
                                          outputTableName = prefix + "grid_geom_n_indic" + str(d).replace(".", "_"))
        # Separate the grid geometry from the grid indicators
        all_cols_without_geom = getColumns(cursor = cursor,
                                           tableName = output_grid)
        all_cols_without_geom.remove(GEOM_FIELD)
        cursor.execute(f"""
                       DROP TABLE IF EXISTS {OUTPUT_GRID + str(d).replace(".", "_")};
                       CREATE TABLE {OUTPUT_GRID + str(d).replace(".", "_")}
                           AS SELECT ID, {GEOM_FIELD}
                           FROM {output_grid};
                       CALL CSVWRITE('{final_output_dir+os.sep}{OUTPUT_GRID}_{str(d).replace(".", "_")}.csv',
                                     '(SELECT {",".join(all_cols_without_geom)} FROM {output_grid})');
                       """)
        saveData.saveTable(cursor = cursor,
                           tableName = OUTPUT_GRID + str(d).replace(".", "_"), 
                           filedir = f"""{final_output_dir+os.sep}{OUTPUT_GRID}_{str(d).replace(".", "_")}.geojson""", 
                           delete = True, 
                           rotationCenterCoordinates = rotationCenterCoordinates, 
                           rotateAngle = -d)
        saveData.saveTable(cursor = cursor,
                           tableName = city_all_indic, 
                           filedir = f"""{final_output_dir+os.sep}{OUTPUT_CITY_INDIC}_{str(d).replace(".", "_")}.geojson""", 
                           delete = True, 
                           rotationCenterCoordinates = rotationCenterCoordinates, 
                           rotateAngle = -d)
        saveData.saveTable(cursor = cursor,
                           tableName = rect_park_frac, 
                           filedir = f"""{final_output_dir+os.sep}{OUTPUT_PARK_INDIC}_{str(d).replace(".", "_")}.geojson""", 
                           delete = True, 
                           rotationCenterCoordinates = rotationCenterCoordinates, 
                           rotateAngle = -d)
    
    # Save also the park  in the output folder
    saveData.saveTable(cursor = cursor,
                       tableName = PARK_BOUNDARIES_TAB, 
                       filedir = f"""{final_output_dir+os.sep+PARK_BOUNDARIES_TAB}.geojson""", 
                       delete = True)        
        
    return cursor, city_all_indic

def calcParkInfluence(weatherFilePath, 
                      preprocessOutputPath,
                      prefix = DEFAULT_WEATHER,
                      feedback = None,
                      startDate = START_DATE,
                      endDate = END_DATE,
                      wdir = "wdir10",
                      wspeed = "ws10",
                      tair = "t2m",
                      rh = "r2m",
                      pa = "sp"):
    # Define the entire input and output directory paths
    final_output_dir = preprocessOutputPath+os.sep+OUTPUT_PROCESSOR_FOLDER+os.sep+prefix
    final_input_dir = preprocessOutputPath+os.sep+OUTPUT_PREPROCESSOR_FOLDER
    
    # Get the number of directions used for the calculations (for example reading the write metadata)
    ndir = N_DIRECTIONS
    dirs = np.arange(0, 360, 360./ndir)
    
    # Load grid info for each direction
    gridFileDic = {d: f"""{OUTPUT_GRID}_{str(float(d)).replace(".", "_")}""" 
                           for d in dirs}
    grids = {i: gpd.read_file(final_input_dir + os.sep + gridFileDic[i] + ".geojson") 
                    for i in gridFileDic.keys()}
    grid_indic = {i: pd.read_csv(final_input_dir + os.sep + gridFileDic[i] + ".csv",
                                 na_values = [DEFAULT_D_PARK_INPUT, DEFAULT_D_PARK_OUTPUT, DEFAULT_D_PARK]) 
                    for i in gridFileDic.keys()}
    
    # For each direction, identify points that are before the park, within the park or after the park
    grid_ind_city_before, grid_ind_park, grid_ind_city_after = \
        calc_fct.identify_point_position(grid_indic)
    
    # Fill missing ID_UPSTREAM since grid points may have not intersect some upstream city geometries
    grid_ind_city_before = calc_fct.remove_null_upstream(grid_indic = grid_ind_city_before, start = 1)
    grid_ind_park = calc_fct.remove_null_upstream(grid_indic = grid_ind_park, start = 1)
    grid_ind_city_after = calc_fct.remove_null_upstream(grid_indic = grid_ind_city_after, start = 2)
    
    # Rename the columns in the park indic dataframe (needed to have strings in SQL, int needed in Python)
    for d in grid_ind_park.keys():
        frac_cols = grid_ind_park[d].columns[grid_ind_park[d].columns.str.contains("FRAC_")]
        grid_ind_park[d].rename({col: int(col.split("_")[1]) for col in frac_cols}, 
                                axis = 1, 
                                inplace = True)

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

    # For each time period (day - 0PM - and night - 11 PM)
    output_t_path = {}
    output_dt_path = {}
    for tp in [DAY_TIME, NIGHT_TIME]:
        if feedback:
            if tp == NIGHT_TIME:
                feedback.setProgressText("Calculate night-time park effect")
            else:
                feedback.setProgressText("Calculate day-time park effect")
            if feedback.isCanceled():
                feedback.setProgressText("Calculation cancelled by user")
                return {}
        # Spatial variations of air temperature and deltaT generated by the park
        # are averaged only at the end. Thus need to sum by wind direction
        # and also to sum the wight (nb of days in wind each direction)
        weights = pd.Series({d: 0 for d in dirs}) # Weights used for averaging the effect of the park over the entire period
        grid_sum_tair = pd.DataFrame(columns = grid_indic.keys(), 
                                     index = range(0, max([grid_indic[i].index.size for i in grid_indic.keys()])))
        grid_sum_tair.loc[:,:] = 0
        grid_sum_deltatair = grid_sum_tair.copy(deep = True)
        
        selected_dates = pd.date_range(start = datetime.datetime(year, start_month, start_day, tp),
                                       end = datetime.datetime(year, end_month, end_day),
                                       freq = pd.offsets.Day(1))
        df_met_sel = df_met.reindex(selected_dates).dropna()
        
        # Calculates the DPV
        df_met_sel[DPV] = calc_fct.dpv_calc(df_met_sel)
        
        # Normalize the meteorological cooling factors (wind speed and dpv) in order to have them between -1 and 1
        df_ws_norm = calc_fct.normalize_factor(value = df_met_sel[WSPEED], 
                                               value_min = COOLING_FACTORS[tp].loc["min","ws"], 
                                               value_max = COOLING_FACTORS[tp].loc["max","ws"])
        df_dpv_norm = calc_fct.normalize_factor(value = df_met_sel[DPV], 
                                                value_min = COOLING_FACTORS[tp].loc["min","dpv"], 
                                                value_max = COOLING_FACTORS[tp].loc["max","dpv"])
        
        
        # For each day, sum the effect of the park on the air temperature
        # (sum on a different grid depending on wind direction)
        for d in df_met_sel.index:
            wd = df_met_sel.loc[d, WDIR]
            print(wd)
            wd_range = [i for i in dirs if (wd >= i and wd < i + 360./ndir)][0]
            weights[wd_range] += 1
            
            grid_sum_tair[wd_range], grid_sum_deltatair[wd_range] = \
                calc_fct.air_cooling_and_diffusion(grid_sum_tair = grid_sum_tair[wd_range],
                                                   grid_sum_deltatair = grid_sum_deltatair[wd_range],
                                                   grid_ind_city_before = grid_ind_city_before[wd_range],
                                                   grid_ind_park = grid_ind_park[wd_range],
                                                   grid_ind_city_after = grid_ind_city_after[wd_range],
                                                   tair = df_met_sel.loc[d, T_AIR],
                                                   ws_norm = df_ws_norm[d],
                                                   dpv_norm = df_dpv_norm[d],
                                                   max_dist = MAX_DIST[tp],
                                                   day_hour = tp)
        
        # Get the maximum extent of the grids
        xmin = min([grids[i].geometry.x.min() for i in grid_sum_tair.columns])
        xmax = max([grids[i].geometry.x.max() for i in grid_sum_tair.columns]) 
        ymin = min([grids[i].geometry.y.min() for i in grid_sum_tair.columns])
        ymax = max([grids[i].geometry.y.max() for i in grid_sum_tair.columns]) 
        epsg = grids[0].crs.to_epsg()
        
        # Calculate the output raster grid size
        output_grid_size = ((ymax-ymin) * (xmax-xmin) / NB_OUTPUT_CELL)**0.5
        
        # Create the polygon use to keep values (outside the park)
        gdf_all = gpd.GeoSeries([Polygon([(xmin, ymin), (xmax, ymin), 
                                          (xmax, ymax), (xmin, ymax),
                                          (xmin, ymin)])]).set_crs(epsg)
        gdf_park = gpd.read_file(os.path.join(final_input_dir, PARK_BOUNDARIES_TAB + ".geojson"))
        gdf_city = gdf_all.difference(gdf_park)
        gdf_city.to_file(TEMPO_DIRECTORY + os.sep + "city.geojson",
                         driver = "GeoJSON")
        
        # Calculates mean value for each wind direction, join grid point geometry and save into a file
        output_file = {}
        output_T_file = {}
        output_dT_file = {}
        rlayer_T = {}
        rlayer_dT = {}
        raster_t_list = []
        raster_dt_list = []
        average_formula_t = ""
        average_formula_dt = ""
        i = 0
        weight_sum = weights.sum()
        for wd in grid_sum_tair.columns:
            if weights[wd] != 0:
                grid_tair = grids[wd].join((grid_sum_tair[wd] / weights[wd]).rename("tair").astype(float))
                grid_deltat = grids[wd].join((grid_sum_deltatair[wd] / weights[wd]).rename("tair").astype(float))
                output_T_file[wd] = f"""{OUTPUT_T}_{str(float(wd)).replace(".", "_")}"""
                output_dT_file[wd] = f"""{OUTPUT_DT}_{str(float(wd)).replace(".", "_")}"""
                grid_tair.to_file(TEMPO_DIRECTORY + os.sep + output_T_file[wd] + ".geojson",
                                  driver = "GeoJSON")
                grid_deltat.to_file(TEMPO_DIRECTORY + os.sep + output_dT_file[wd] + ".geojson",
                                    driver = "GeoJSON")
                
                # Interpolate and save the data in a raster file (same extent for all wind directions)
                processing.run("qgis:tininterpolation", 
                               {'INTERPOLATION_DATA':f'{TEMPO_DIRECTORY + os.sep + output_T_file[wd] + ".geojson"}::~::0::~::1::~::0',
                                'METHOD':0,
                                'EXTENT':f'{xmin-100},{xmax+100},{ymin-100},{ymax+100} [EPSG:{epsg}]',
                                'PIXEL_SIZE':f'{output_grid_size}',
                                'OUTPUT':f'{final_output_dir + os.sep + output_T_file[wd]}_{str(tp)}h.tif'})
                processing.run("qgis:tininterpolation", 
                               {'INTERPOLATION_DATA':f'{TEMPO_DIRECTORY + os.sep + output_dT_file[wd] + ".geojson"}::~::0::~::1::~::0',
                                'METHOD':0,
                                'EXTENT':f'{xmin-100},{xmax+100},{ymin-100},{ymax+100} [EPSG:{epsg}]',
                                'PIXEL_SIZE':f'{output_grid_size}',
                                'OUTPUT':f'{TEMPO_DIRECTORY + os.sep + output_dT_file[wd]}'})                
                processing.run("gdal:cliprasterbymasklayer", 
                               {'INPUT':f'{TEMPO_DIRECTORY + os.sep + output_dT_file[wd]}',
                                'MASK':TEMPO_DIRECTORY + os.sep + "city.geojson",
                                'SOURCE_CRS':QgsCoordinateReferenceSystem(f'EPSG:{epsg}'),
                                'TARGET_CRS':None,
                                'TARGET_EXTENT':None,
                                'NODATA':None,
                                'ALPHA_BAND':False,
                                'CROP_TO_CUTLINE':True,
                                'KEEP_RESOLUTION':True,
                                'SET_RESOLUTION':False,
                                'X_RESOLUTION':None,
                                'Y_RESOLUTION':None,
                                'MULTITHREADING':False,
                                'OPTIONS':'','DATA_TYPE':0,
                                'EXTRA':'',
                                'OUTPUT':f'{final_output_dir + os.sep + output_dT_file[wd]}_{str(tp)}h.tif'})
                
                raster_t_list.append(f'{final_output_dir + os.sep + output_T_file[wd]}_{str(tp)}h.tif')
                raster_dt_list.append(f'{final_output_dir + os.sep + output_dT_file[wd]}_{str(tp)}h.tif')
                
                average_formula_t += f' + {output_T_file[wd]}_{str(tp)}h@1 * {weights[wd]} / {weight_sum}'
                average_formula_dt += f' + {output_dT_file[wd]}_{str(tp)}h@1 * {weights[wd]} / {weight_sum}'
                
                # # Average the temperature using grid from all directions
                # raster_t_buf = gdal.Open(f'{final_output_dir + os.sep + output_T_file[wd]}_{str(tp)}h.tif')
                # raster_dt_buf = gdal.Open(f'{final_output_dir + os.sep + output_dT_file[wd]}_{str(tp)}h.tif')
                
                # array_t_buf = raster_t_buf.ReadAsArray()
                # array_dt_buf = raster_dt_buf.ReadAsArray()
                # array_t_buf[array_t_buf == -9999] = np.nan
                # array_dt_buf[array_dt_buf == -9999] = np.nan
                # if i==0:
                #     t_final = array_t_buf * weights[wd] / weight_sum
                #     dt_final = array_dt_buf * weights[wd] / weight_sum
                    
                #     x_count_t, y_count_t = raster_t_buf.RasterXSize, raster_t_buf.RasterYSize
                #     x_count_dt, y_count_dt = raster_dt_buf.RasterXSize, raster_dt_buf.RasterYSize
                #     geotransform = raster_t_buf.GetGeoTransform()
                #     projection = raster_t_buf.GetProjection()
                # else:
                #     t_final += array_t_buf * weights[wd] / weight_sum
                #     dt_final += array_dt_buf * weights[wd] / weight_sum
                # i += 1
                
                # # Release memory to avoid error due to gdal
                # raster_t_buf = None
                # raster_dt_buf = None
                # array_t_buf = None
                # array_dt_buf = None

        output_t_path[tp] = f'{final_output_dir + os.sep + OUTPUT_T}_{str(tp)}h'
        output_dt_path[tp] = f'{final_output_dir + os.sep + OUTPUT_DT}_{str(tp)}h'
        
        # Average the deltaT and T using all directions
        processing.run("qgis:rastercalculator", 
                       {'EXPRESSION':average_formula_t,
                        'LAYERS':raster_t_list,
                        'CELLSIZE':0,'EXTENT':None,'CRS':None,'OUTPUT':output_t_path[tp]})
        processing.run("qgis:rastercalculator", 
                       {'EXPRESSION':average_formula_dt,
                        'LAYERS':raster_dt_list,
                        'CELLSIZE':0,'EXTENT':None,'CRS':None,'OUTPUT':output_dt_path[tp]})        
        
        # # Save the final air temperature as a raster and as a contour
        # calc_fct.save_raster(array = t_final, 
        #                      path = output_t_path[tp], 
        #                      x_count = x_count_t+1,
        #                      y_count = y_count_t+1,
        #                      geotransform = geotransform,
        #                      projection = projection)
        
        raster_t_final = gdal.Open(f'{output_t_path[tp]}')
        array_t_final = raster_t_final.ReadAsArray()
        array_t_final = array_t_final[array_t_final>-9999]
        interval_isovalues_T = round_to((np.nanmax(array_t_final)-np.nanmin(array_t_final)) / NB_ISOVALUES,
                                                 2)
        
        # Release memory to avoid error due to gdal
        raster_t_final = None
        array_t_final = None
                
        processing.run("gdal:contour_polygon", 
                       {'INPUT':output_t_path[tp],
                        'BAND':1,
                        'INTERVAL':f'{interval_isovalues_T}',
                        'CREATE_3D':False,
                        'IGNORE_NODATA':False,
                        'NODATA':None,
                        'OFFSET':f'{0 + interval_isovalues_T / 2}',
                        'EXTRA':'','FIELD_NAME_MIN':'ELEV_MIN',
                        'FIELD_NAME_MAX':'ELEV_MAX',
                        'OUTPUT': output_t_path[tp] + ".geojson"})
        
        # # Save the final delta air temperature as a raster and as a contour
        # calc_fct.save_raster(array = dt_final, 
        #                      path = output_dt_path[tp], 
        #                      x_count = x_count_dt,
        #                      y_count = y_count_dt,
        #                      geotransform = geotransform,
        #                      projection = projection)
        
        raster_dt_final = gdal.Open(f'{output_dt_path[tp]}')
        array_dt_final = raster_dt_final.ReadAsArray()
        array_dt_final = array_dt_final[array_dt_final>-9999]
        interval_isovalues_dT = round_to((np.nanmax(array_dt_final)-np.nanmin(array_dt_final)) / NB_ISOVALUES,
                                                 2)
        
        # Release memory to avoid error due to gdal
        raster_dt_final = None
        array_dt_final = None
        
        processing.run("gdal:contour_polygon", 
                       {'INPUT':output_dt_path[tp],
                        'BAND':1,
                        'INTERVAL':f'{interval_isovalues_dT}',
                        'CREATE_3D':False,
                        'IGNORE_NODATA':False,
                        'NODATA':None,
                        'OFFSET':f'{0 + interval_isovalues_dT / 2}',
                        'EXTRA':'','FIELD_NAME_MIN':'ELEV_MIN',
                        'FIELD_NAME_MAX':'ELEV_MAX',
                        'OUTPUT': output_dt_path[tp] + ".geojson"})        
        
        # Save the weights
        weights.to_csv(f'{final_output_dir + os.sep + WIND_DIR_RATE}_{str(tp)}h.csv')
        
    return output_t_path, output_dt_path


def calcBuildingImpact(preprocessOutputPath,
                       prefix = DEFAULT_WEATHER):
    # Define the entire input and output directory paths
    final_output_dir = preprocessOutputPath+os.sep+OUTPUT_PROCESSOR_FOLDER+os.sep+prefix
    final_input_dir = preprocessOutputPath+os.sep+OUTPUT_PREPROCESSOR_FOLDER
    
    
    # Recover data from previous steps
    buildingPath = os.path.join(final_input_dir, OUTPUT_BUILD_INDIC + ".geojson")
    output_dt_path = {tp: f'{final_output_dir + os.sep + OUTPUT_DT}_{str(tp)}h'\
                      for tp in [DAY_TIME, NIGHT_TIME]}
    
    # Get the centroid of each building
    centroid = processing.run("native:centroids",
                              {'INPUT':buildingPath,
                               'ALL_PARTS':False,
                               'OUTPUT':'TEMPORARY_OUTPUT'})
    
    # Apply the same method for day and night data
    for i, tp in enumerate(output_dt_path):
        # Fill deltaT nan values since some pixels near the park containing buildings might be nan
        filled = processing.run("grass7:r.fillnulls",
                                {'input':output_dt_path[tp],
                                 'method':0,'tension':40,'smooth':0.1,'edge':3,'npmin':600,
                                 'segmax':300,'lambda':0.01,'output':'TEMPORARY_OUTPUT',
                                 'GRASS_REGION_PARAMETER':None,
                                 'GRASS_REGION_CELLSIZE_PARAMETER':0,
                                 'GRASS_RASTER_FORMAT_OPT':'',
                                 'GRASS_RASTER_FORMAT_META':''})
        
        # Assign to each building the deltaT value of the pixel intersecting the building centroid
        if i == 0:
            input_vector = centroid['OUTPUT']
            output_vector = 'TEMPORARY_OUTPUT'
        else:
            input_vector = build_indep_var['OUTPUT']
            output_vector = f'{TEMPO_DIRECTORY + os.sep}tmp_deltaT.geojson'
        build_indep_var = processing.run("native:rastersampling",
                                         {'INPUT':input_vector,
                                          'RASTERCOPY':filled['output'],
                                          'COLUMN_PREFIX':f'{DELTA_T + str(tp)}h',
                                          'OUTPUT':output_vector})
        
    # Load the independent variables
    df_points = gpd.read_file(build_indep_var['OUTPUT'])\
                       .drop("geometry", axis = 1)\
                           .set_index(ID_FIELD_BUILD)
                           
    # Calculates the amplification factor for each building
    deltaT_list = [f'{DELTA_T + str(tp)}h1' for tp in output_dt_path.keys()]
    df_points[BUILDING_AMPLIF_FACTOR] = df_points[deltaT_list].mean(axis = 1) / BASIC_COOLING
    df_points.drop(deltaT_list, axis = 1, inplace = True)
    
    # Calculate the absolute and relative impacts of the park on the buildings
    df_impacts = calc_fct.calc_build_impact(df_indic = df_points,
                                            deltaT_cols = [f'{DELTA_T + str(tp)}h' \
                                                           for tp in output_dt_path])
    
    # Join the independent variables and impacts of the park on the buildings 
    # to the building geometry
    gdf_build = gpd.read_file(buildingPath)[[ID_FIELD_BUILD, "geometry", HEIGHT_FIELD]].set_index(ID_FIELD_BUILD)
    gdf_build = gdf_build.join(df_impacts)
    
    # Save the results in a vector layer
    output_vector = f'{final_output_dir+ os.sep + BUILD_INDEP_VAR}.geojson'
    gdf_build.to_file(output_vector,
                      driver = "GeoJSON")
    
def compareScenarios(refScenarioDirectory, 
                     altScenarioDirectory,
                     change,
                     outputDirectory):
    # Create the name for the folder that will be used to save results comparison
    ref_scenario_name = Path(refScenarioDirectory).parent.parent.name
    ref_scenario_name += f'-{Path(refScenarioDirectory).name}'
    alt_scenario_name = Path(altScenarioDirectory).parent.parent.name
    alt_scenario_name += f'-{Path(altScenarioDirectory).name}'
    comparison_name = alt_scenario_name + "_VS_" + ref_scenario_name
    finalDirectory = outputDirectory + os.sep + comparison_name
    
    # Creates the output folder if it does not exist
    if not os.path.exists(outputDirectory):
        os.mkdir(outputDirectory)
    if os.path.exists(outputDirectory + os.sep + comparison_name):
        raise QgsProcessingException(f'{comparison_name} folder already exists in {outputDirectory}')
    else:
        os.mkdir(finalDirectory)
    
    # Read Building energy and comfort files
    BUILD_ref = refScenarioDirectory + os.sep + BUILD_INDEP_VAR + ".geojson"
    BUILD_alt = altScenarioDirectory + os.sep + BUILD_INDEP_VAR + ".geojson"
    gdf_build_ref = gpd.read_file(BUILD_ref)
    gdf_build_alt = gpd.read_file(BUILD_alt)
    
    # Add and calculate a floor area column for each building
    gdf_build_ref[FLOOR_AREA] = gdf_build_ref.area * np.trunc(gdf_build_ref[HEIGHT_FIELD] / BUILDING_DEFAULT_FLOOR_HEIGHT)
    gdf_build_alt[FLOOR_AREA] = gdf_build_alt.area * np.trunc(gdf_build_alt[HEIGHT_FIELD] / BUILDING_DEFAULT_FLOOR_HEIGHT)
    
    # Calculate the building energy and comfort differences
    list_var_abs = [ENERGY_IMPACT_ABS, THERM_COMFORT_IMPACT_ABS]
    list_var_rel = [ENERGY_IMPACT_REL, THERM_COMFORT_IMPACT_REL]
    diff_build = pd.DataFrame(columns = list_var_abs + list_var_rel)
    tempo_build_nrj_ref = gdf_build_ref[ENERGY_IMPACT_ABS].divide(gdf_build_ref[ENERGY_IMPACT_REL])
    tempo_build_tc_ref = gdf_build_ref[THERM_COMFORT_IMPACT_ABS].divide(gdf_build_ref[THERM_COMFORT_IMPACT_REL])
    diff_build[list_var_abs] = gdf_build_alt[list_var_abs].subtract(gdf_build_ref[list_var_abs])
    diff_build[ENERGY_IMPACT_REL] = diff_build[ENERGY_IMPACT_ABS].divide(tempo_build_nrj_ref) * 100
    diff_build[THERM_COMFORT_IMPACT_REL] = diff_build[THERM_COMFORT_IMPACT_ABS].divide(tempo_build_tc_ref) * 100
    diff_build_extremums = {var: (diff_build[var].min(), diff_build[var].max())\
                            for var in diff_build.columns}
    
    
    # Calculate the global energy impact for ref and alt (the reference for % is without park)
    nrj_ref_tot = (gdf_build_ref[ENERGY_IMPACT_ABS].divide(gdf_build_ref[ENERGY_IMPACT_REL])\
                   .mul(gdf_build_ref[FLOOR_AREA])).sum()
    nrj_impact_ref_tot = (gdf_build_ref[ENERGY_IMPACT_ABS].mul(gdf_build_ref[FLOOR_AREA])).sum()
    nrj_alt_tot = (gdf_build_alt[ENERGY_IMPACT_ABS].divide(gdf_build_alt[ENERGY_IMPACT_REL])\
                   .mul(gdf_build_alt[FLOOR_AREA])).sum()
    nrj_impact_alt_tot = (gdf_build_alt[ENERGY_IMPACT_ABS].mul(gdf_build_alt[FLOOR_AREA])).sum()
    
    # Calculate the mean thermal impact weighted by the area of building
    tc_ref_tot = (gdf_build_ref[THERM_COMFORT_IMPACT_ABS].divide(gdf_build_ref[THERM_COMFORT_IMPACT_REL])\
                  .mul(gdf_build_ref[FLOOR_AREA])).sum()/(gdf_build_ref[FLOOR_AREA].sum())
    tc_impact_ref_tot = (gdf_build_ref[THERM_COMFORT_IMPACT_ABS]\
                  .mul(gdf_build_ref[FLOOR_AREA])).sum()/(gdf_build_ref[FLOOR_AREA].sum())
    tc_alt_tot = (gdf_build_alt[THERM_COMFORT_IMPACT_ABS].divide(gdf_build_alt[THERM_COMFORT_IMPACT_REL])\
                  .mul(gdf_build_alt[FLOOR_AREA])).sum()/(gdf_build_alt[FLOOR_AREA].sum())
    tc_impact_alt_tot = (gdf_build_alt[THERM_COMFORT_IMPACT_ABS]\
                  .mul(gdf_build_alt[FLOOR_AREA])).sum()/(gdf_build_alt[FLOOR_AREA].sum())
    
    # Write global results into a file
    dict_build_glob = {"ENERGY_IMPACT_REF" : f'{round_to(-nrj_impact_ref_tot, NB_SIGN_DIGITS)}kWh/year '+\
                                               f'({round_to(-nrj_impact_ref_tot / nrj_ref_tot * 100, NB_SIGN_DIGITS)}%)',
                       "THERM_COMFORT_REF" : f'{round_to(-tc_impact_ref_tot, NB_SIGN_DIGITS)}°C.h/year '+\
                                               f'({round_to(-tc_impact_ref_tot / tc_ref_tot * 100, NB_SIGN_DIGITS)}%)',
                       "ENERGY_IMPACT_ALT" : f'{round_to(-nrj_impact_alt_tot, NB_SIGN_DIGITS)}kWh/year '+\
                                               f'({round_to(-nrj_impact_alt_tot / nrj_alt_tot * 100, NB_SIGN_DIGITS)}%)',
                       "THERM_COMFORT_ALT" : f'{round_to(-tc_impact_alt_tot, NB_SIGN_DIGITS)}°C.h/year '+\
                                               f'({round_to(-tc_impact_alt_tot / tc_alt_tot * 100, NB_SIGN_DIGITS)}%)'}
    pd.Series(dict_build_glob)\
        .to_csv(finalDirectory + os.sep + "Global_building_effect.csv")
    
    if change == "weather" or change == "park composition" or change == 'buildings characteristics':
        diff_build_path = finalDirectory + os.sep + BUILD_INDEP_VAR + ".geojson"
        gpd.GeoDataFrame(pd.concat([diff_build, gdf_build_ref.geometry], axis = 1))\
            .to_file(diff_build_path,
                     driver = "GeoJSON")
    else:
        diff_build_path = None
        diff_build_extremums = None
    
    
    diff_deltaT_path = {}
    diff_T_path = {}
    dict_deltaT_glob = {}
    for tp in [DAY_TIME, NIGHT_TIME]:
        if change == 'buildings characteristics':
            diff_deltaT_path[tp] = None
            diff_T_path[tp] = None
            # Calculate the mean of each deltaT scenario + the scenario difference
            deltaT_ref_path = refScenarioDirectory + os.sep + OUTPUT_DT + "_" + str(tp) + "h"
            raster_dt_ref = gdal.Open(f'{deltaT_ref_path}')
            dt_array_ref = raster_dt_ref.ReadAsArray()
            val_ref = round_to(np.nanmean(dt_array_ref[(dt_array_ref>-9999) * (dt_array_ref<9999)] ), NB_SIGN_DIGITS)
            dict_deltaT_glob[tp] = {REF_SCEN: str(val_ref),
                                    ALT_SCEN: str(val_ref),
                                    DIFF_SCEN: str(0)}
        else:
            deltaT_ref_path = refScenarioDirectory + os.sep + OUTPUT_DT + "_" + str(tp) + "h"
            deltaT_alt_path = altScenarioDirectory + os.sep + OUTPUT_DT + "_" + str(tp) + "h"   
            T_ref_path = refScenarioDirectory + os.sep + OUTPUT_T + "_" + str(tp) + "h" 
            T_alt_path = altScenarioDirectory + os.sep + OUTPUT_T + "_" + str(tp) + "h"
            
            # Calculate the deltaT difference
            diff_deltaT_path[tp] = finalDirectory + os.sep + OUTPUT_DT + "_" + str(tp) + "h"
            diff_T_path[tp] = None
            processing.run("gdal:rastercalculator", 
                           {'INPUT_A':deltaT_alt_path,
                            'BAND_A':1,
                            'INPUT_B':deltaT_ref_path,
                            'BAND_B':1,
                            'INPUT_C':None,
                            'BAND_C':None,
                            'INPUT_D':None,
                            'BAND_D':None,
                            'INPUT_E':None,
                            'BAND_E':None,
                            'INPUT_F':None,
                            'BAND_F':None,
                            'FORMULA':'A -B',
                            'NO_DATA':None,
                            'RTYPE':5,
                            'OPTIONS':'',
                            'EXTRA':'',
                            'OUTPUT': diff_deltaT_path[tp]})
            
            # Calculate the mean of each deltaT scenario + the scenario difference
            raster_dt_ref = gdal.Open(f'{deltaT_ref_path}')
            raster_dt_alt = gdal.Open(f'{deltaT_alt_path}')
            raster_dt_diff = gdal.Open(f'{diff_deltaT_path[tp]}')
            dt_array_ref = raster_dt_ref.ReadAsArray()
            dt_array_alt = raster_dt_alt.ReadAsArray()
            dt_array_diff = raster_dt_diff.ReadAsArray()
            val_ref = round_to(np.nanmean(dt_array_ref[(dt_array_ref>-9999) * (dt_array_ref<9999)] ), NB_SIGN_DIGITS)
            val_alt = round_to(np.nanmean(dt_array_alt[(dt_array_alt>-9999) * (dt_array_alt<9999)]), NB_SIGN_DIGITS)
            val_diff = round_to(np.nanmean(dt_array_diff[(dt_array_diff>-9999) * (dt_array_diff<9999)]), NB_SIGN_DIGITS)
            
            dict_deltaT_glob[tp] = {REF_SCEN: str(val_ref),
                                    ALT_SCEN: str(val_alt),
                                    DIFF_SCEN: str(val_diff)}
                                         
            # Release memory to avoid error due to gdal
            raster_dt_ref = None
            raster_dt_alt = None
            raster_dt_diff = None    
                
            if change == "park_composition":
                diff_deltaT_path[tp] = None
                diff_T_path[tp] = finalDirectory + os.sep + OUTPUT_T + "_" + str(tp) + "h"
                # Calculate the air temperature difference
                processing.run("gdal:rastercalculator", 
                               {'INPUT_A':T_alt_path,
                                'BAND_A':1,
                                'INPUT_B':T_ref_path,
                                'BAND_B':1,
                                'INPUT_C':None,
                                'BAND_C':None,
                                'INPUT_D':None,
                                'BAND_D':None,
                                'INPUT_E':None,
                                'BAND_E':None,
                                'INPUT_F':None,
                                'BAND_F':None,
                                'FORMULA':'A -B',
                                'NO_DATA':None,
                                'RTYPE':5,
                                'OPTIONS':'',
                                'EXTRA':'',
                                'OUTPUT': diff_T_path[tp]})
            
    return finalDirectory, dict_build_glob, diff_build_path, diff_deltaT_path,\
        diff_T_path, diff_build_extremums, dict_deltaT_glob