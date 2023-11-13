# -*- coding: utf-8 -*-
from .globalVariables import *

from . import DataUtil
from . import loadData

import string

def creates_units_of_analysis(cursor, park_boundary_tab, srid,
                                nCrossWindTot, wind_dir, distance_max):
    """ Creates many units used for analysis:
            - the along-wind corridors used to average park characteristics
    and city morphology and organisation
            - the grid used for the calculation
            - cross-wind lines that will be used to characterize street size and number

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

			cursor: conn.cursor
				A cursor object, used to perform queries        
            park_boundary_tab: String
                Table name where park boundaries are saved
            srid: int
                EPSG code that will be assigned to corridors geometries
            nCrossWindTot: int
                Number of cross-wind cells within the park
            wind_dir: float
                wind direction (clock-wise, ° from North)
            distance_max: float
                Maximum distance where the park can have an impact outside its boundaries
        
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            rec_coord_park_upstream: String
                Name of the table where are saved park corridors
            rec_coord_city_upstream: String
                Name of the table where are saved city corridors
            grid: String
                Name of the table used for grid calculation
            crosswind_line: String
                Name of the table where are saved crosswind lines
                """    
    
    # Calculates the number of corridors inside the park
    nCrossWind = int(nCrossWindTot / 3)
    
    # Temporary tables (and prefix for temporary tables)
    rec_ini = DataUtil.postfix("RECT_INI")
    line_ini = DataUtil.postfix("LINE_INI")
    rec_park = DataUtil.postfix("RECT_PARK")
    rec_city = DataUtil.postfix("RECT_CITY")
    rec_city_coord = DataUtil.postfix("RECT_CITY_COORD")
    rec_park_coord = DataUtil.postfix("RECT_PARK_COORD")
    grid_ini = DataUtil.postfix("GRID_INI")
    grid_ini2 = DataUtil.postfix("GRID_INI2")
    grid_ini3 = DataUtil.postfix("GRID_INI3")
    grid_ini4 = DataUtil.postfix("GRID_INI4")
    
    # Output table names
    rec_coord_park_upstream = DataUtil.postfix("RECT_COORD_PARK_UPSTREAM", str(wind_dir).replace(".", "_"))
    rec_coord_city_upstream = DataUtil.postfix("RECT_COORD_CITY_UPSTREAM", str(wind_dir).replace(".", "_"))
    grid = DataUtil.postfix("GRID", str(wind_dir).replace(".", "_"))
    crosswind_line = DataUtil.postfix("CROSSWIND_LINE", str(wind_dir).replace(".", "_"))
    
    
    # Calculates the cross-wind and along-wind size of the park bounding box
    # as well as lower left corner
    cursor.execute(
        """
        SELECT  ST_XMAX({0})-ST_XMIN({0}) AS X_SIZE,
                ST_YMAX({0})-ST_YMIN({0}) AS Y_SIZE,
                ST_XMIN({0}) AS XMIN,
                ST_YMIN({0}) AS YMIN
        FROM {1}
        """.format(GEOM_FIELD                   , park_boundary_tab))
    park_bb_xsize, park_bb_ysize, park_bb_xmin, park_bb_ymin = cursor.fetchall()[0]
    dx = park_bb_xsize / nCrossWind
    if dx < MIN_CELL_SIZE:
        nCrossWind = int(park_bb_xsize / MIN_CELL_SIZE)
        dx = park_bb_xsize / nCrossWind
    
    # The total number of corridors outside the park
    nCrossWindOut = nCrossWind * 2
    
    # Creates rectangles and lines along 
    list_rect = ["""('POLYGON(({0} {1}, {0} {2}, {3} {2}, {3} {1}, {0} {1}))',
                    {4})
                 """.format(park_bb_xmin + dx * i - dx * nCrossWindOut / 2,
                            park_bb_ymin - park_bb_ysize,
                            park_bb_ymin + 2 * park_bb_ysize,
                            park_bb_xmin + dx * (i + 1) - dx * nCrossWindOut / 2,
                            i + 1)
                     for i in range(0, nCrossWind + nCrossWindOut)]
    list_lines = ["""('LINESTRING({0} {1}, {0} {2})', {3})
                 """.format(park_bb_xmin + dx * (i + 0.5) - dx * nCrossWindOut / 2,
                            park_bb_ymin - park_bb_ysize,
                            park_bb_ymin + 2 * park_bb_ysize,
                            i + 1)
                     for i in range(0, nCrossWind + nCrossWindOut)]
    cursor.execute(
        """
        DROP TABLE IF EXISTS TEMPO, {0};
        CREATE TABLE TEMPO({1} GEOMETRY, ID INT);
        INSERT INTO TEMPO VALUES {2};
        CREATE TABLE {0}
            AS SELECT ST_SETSRID({1}, {3}) AS {1}, ID
            FROM TEMPO;
        DROP TABLE IF EXISTS TEMPO;
        """.format( rec_ini                 , GEOM_FIELD, 
                    ", ".join(list_rect)    , srid))
    cursor.execute(
        """
        DROP TABLE IF EXISTS TEMPO, {0};
        CREATE TABLE TEMPO({1} GEOMETRY, ID INT);
        INSERT INTO TEMPO VALUES {2};
        CREATE TABLE {0}
            AS SELECT ST_SETSRID({1}, {3}) AS {1}, ID
            FROM TEMPO;
        DROP TABLE IF EXISTS TEMPO;
        """.format( line_ini                , GEOM_FIELD, 
                    ", ".join(list_lines)   , srid))                     
    
    # Calculation of the longest transect within the park
    cursor.execute(
        """
        SELECT MAX(ST_LENGTH(ST_COLLECTIONEXTRACT(ST_INTERSECTION(a.{0}, b.{0}), 2))) AS L
        FROM {1} AS a, {2} AS b
        """.format( GEOM_FIELD          , line_ini,
                    park_boundary_tab))
    Lpark = cursor.fetchall()[0][0]
    
    # Round this transect length to the upper multiple of corridor width
    Lpark = np.ceil(Lpark / dx) * dx
    Lpark = max(Lpark, distance_max)
    
    # Calculation of the intersection between rectangles and park and rectangles and city
    cursor.execute(
        """
        DROP TABLE IF EXISTS {0}, {1};
        CREATE TABLE {0}
            AS SELECT   ST_NORMALIZE(ST_MAKEVALID({2})) AS {2}, ID, EXPLOD_ID AS {6}
            FROM ST_EXPLODE('(SELECT    ST_COLLECTIONEXTRACT(ST_INTERSECTION(a.{2}, 
                                                                             b.{2}), 
                                                             3) AS {2},
                                        a.ID
                              FROM {3} AS a, {4} AS b)')
            WHERE NOT ST_ISEMPTY({2});
        CREATE TABLE {1}
            AS SELECT ST_NORMALIZE(ST_MAKEVALID({2})) AS {2}, ID, EXPLOD_ID AS {6}
            FROM ST_EXPLODE('(SELECT ST_COLLECTIONEXTRACT( ST_INTERSECTION(a.{2}, 
                                                                           ST_DIFFERENCE(ST_BUFFER(b.{2}, 
                                                                                                   {5}), 
                                                                                         b.{2})),
                                                          3) AS {2},
                                      a.ID
                              FROM {3} AS a, {4} AS b)')
            WHERE NOT ST_ISEMPTY({2});             
        """.format( rec_park                            , rec_city,
                    GEOM_FIELD                          , rec_ini,
                    park_boundary_tab                   , Lpark,
                    ID_UPSTREAM))
                  
    # Identification of coordinates of beginning and end of city rectangles
    cursor.execute(
        f""" 
        {DataUtil.createIndex(tableName=line_ini, 
                              fieldName="ID",
                              isSpatial=False)};
        {DataUtil.createIndex(tableName=rec_city, 
                              fieldName="ID",
                              isSpatial=False)};
        DROP TABLE IF EXISTS {rec_city_coord};
        CREATE TABLE {rec_city_coord}
            AS SELECT   a.ID, 
                        b.{GEOM_FIELD},
                        b.{ID_UPSTREAM},
                        ST_YMIN(ST_INTERSECTION(a.{GEOM_FIELD}, ST_EXTERIORRING(b.{GEOM_FIELD}))) AS YMIN,
                        ST_YMAX(ST_INTERSECTION(a.{GEOM_FIELD}, ST_EXTERIORRING(b.{GEOM_FIELD}))) AS YMAX
            FROM {line_ini} AS a RIGHT JOIN {rec_city} AS b
            ON a.ID = b.ID
            WHERE ST_INTERSECTS(a.{GEOM_FIELD}, b.{GEOM_FIELD})
        """)
        
    # Identification of coordinates of beginning and end of parks
    cursor.execute(
        f""" 
        {DataUtil.createIndex(tableName=line_ini, 
                              fieldName="ID",
                              isSpatial=False)};
        {DataUtil.createIndex(tableName=rec_park, 
                              fieldName="ID",
                              isSpatial=False)};
        DROP TABLE IF EXISTS {rec_park_coord};
        CREATE TABLE {rec_park_coord}
            AS SELECT   a.ID, 
                        b.{GEOM_FIELD},
                        b.{ID_UPSTREAM},
                        ST_YMIN(ST_INTERSECTION(a.{GEOM_FIELD}, ST_EXTERIORRING(b.{GEOM_FIELD}))) AS YMIN,
                        ST_YMAX(ST_INTERSECTION(a.{GEOM_FIELD}, ST_EXTERIORRING(b.{GEOM_FIELD}))) AS YMAX,
                        ST_AREA(b.{GEOM_FIELD}) AS CORRIDOR_AREA
            FROM {line_ini} AS a RIGHT JOIN {rec_park} AS b
            ON a.ID = b.ID
            WHERE ST_INTERSECTS(a.{GEOM_FIELD}, b.{GEOM_FIELD})
        """)

    # Creates the grid used for the calculations
    cursor.execute(
        f""" 
        DROP TABLE IF EXISTS {grid_ini};
        CREATE TABLE {grid_ini}
            AS SELECT   ID, {N_ALONG_WIND_PARK}+1-ID_ROW AS ID_ROW, ID_COL,
                        {GEOM_FIELD}
            FROM ST_MakeGridPoints((SELECT ST_ENVELOPE(ST_ACCUM({GEOM_FIELD})) AS {GEOM_FIELD} FROM {rec_city_coord}), 
                                   {dx}, 
                                   (3*{park_bb_ysize})/({N_ALONG_WIND_PARK})) AS {GEOM_FIELD}
            WHERE   ID_COL <= (SELECT MAX(ID) FROM {rec_city_coord})
                    AND ID_ROW <= {N_ALONG_WIND_PARK};
        """)
    

    # The nb of columns might be different depending on park size in a given direction
    # thus ID_COL may start above 1 (while need to start from 1)
    cursor.execute(f"SELECT MIN(ID) FROM {rec_city_coord}")
    MIN_ID_COL = cursor.fetchall()[0][0]
    
    # Keep only rectangles that intersects points
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS RECT_PARK_OK;
        CREATE TABLE RECT_PARK_OK
            AS SELECT   a.ID - {MIN_ID_COL} + 1 AS ID,
                        a.{GEOM_FIELD},
                        a.{ID_UPSTREAM},
                        MAX(a.YMAX) AS YMAX,
                        MAX(a.YMIN) AS YMIN,
                        MAX(a.CORRIDOR_AREA) AS CORRIDOR_AREA
            FROM {rec_park_coord} AS a LEFT JOIN {grid_ini} AS b
            ON a.ID - {MIN_ID_COL} + 1 = b.ID_COL
            WHERE ST_INTERSECTS(a.{GEOM_FIELD}, b.{GEOM_FIELD})
            GROUP BY a.ID, a.{ID_UPSTREAM};
        DROP TABLE IF EXISTS RECT_CITY_OK;
        CREATE TABLE RECT_CITY_OK
            AS SELECT   a.ID - {MIN_ID_COL} + 1 AS ID,
                        a.{GEOM_FIELD},
                        a.{ID_UPSTREAM},
                        MAX(a.YMAX) AS YMAX,
                        MAX(a.YMIN) AS YMIN
            FROM {rec_city_coord} AS a LEFT JOIN {grid_ini} AS b
            ON a.ID - {MIN_ID_COL} + 1 = b.ID_COL
            WHERE ST_INTERSECTS(a.{GEOM_FIELD}, b.{GEOM_FIELD})
            GROUP BY a.ID, a.{ID_UPSTREAM};        
        """)

    # For city and park rectangles, start ID_UPSTREAM from 1 in the North
    cursor.execute(
        """
        {6};{7};{8};
        DROP TABLE IF EXISTS {0}, {1};
        CREATE TABLE {0}
            AS SELECT   b.ID,
                        MAX(b.{9})+1-a.{9}-MIN(b.{9})+1 AS {9},
                        a.{2},
                        a.YMIN,
                        a.YMAX,
                        a.CORRIDOR_AREA
            FROM {4} AS a RIGHT JOIN {4} AS b ON a.ID = b.ID
            GROUP BY b.ID, a.YMIN;
        CREATE TABLE {1}
            AS SELECT   b.ID,
                        MAX(b.{9})+1-a.{9}-MIN(b.{9})+1 AS {9},
                        a.{2},
                        a.YMIN,
                        a.YMAX
            FROM {5} AS a RIGHT JOIN {5} AS b ON a.ID = b.ID
            GROUP BY b.ID, a.YMIN;
        """.format(rec_coord_park_upstream          , rec_coord_city_upstream,
                   GEOM_FIELD                       , line_ini,
                   "RECT_PARK_OK"                   , "RECT_CITY_OK",
                   DataUtil.createIndex(tableName=line_ini, 
                                        fieldName="ID",
                                        isSpatial=False),
                   DataUtil.createIndex(tableName="RECT_PARK_OK", 
                                        fieldName="ID",
                                        isSpatial=False),
                   DataUtil.createIndex(tableName="RECT_CITY_OK", 
                                        fieldName="ID",
                                        isSpatial=False),
                   ID_UPSTREAM))
        
    # Calculates the distance from each grid cell to the input and output of the park
    cursor.execute("{0};{1}".format(DataUtil.createIndex(tableName=rec_coord_park_upstream, 
                                                         fieldName="ID",
                                                         isSpatial=False),
                                    DataUtil.createIndex(tableName=grid_ini, 
                                                         fieldName="ID_COL",
                                                         isSpatial=False)))
    cursor.execute(
        f""" 
        DROP TABLE IF EXISTS {grid_ini2};
        CREATE TABLE {grid_ini2}
            AS SELECT   a.ID,
                        b.{ID_UPSTREAM},
                        ST_Y(a.{GEOM_FIELD})-b.YMIN AS {D_PARK_OUTPUT},
                        b.YMAX-ST_Y(a.{GEOM_FIELD}) AS {D_PARK_INPUT},
                        b.CORRIDOR_AREA
            FROM {grid_ini} AS a LEFT JOIN {rec_coord_park_upstream} AS b
            ON a.ID_COL = b.ID
            WHERE   ST_Y(a.{GEOM_FIELD}) > b.YMIN AND
                    ST_Y(a.{GEOM_FIELD}) <= b.YMAX;
        """)
        
    # Calculates the distance from each grid cell from the output of the park
    cursor.execute("{0};{1}".format(DataUtil.createIndex(tableName=rec_coord_city_upstream, 
                                                         fieldName="ID",
                                                         isSpatial=False),
                                    DataUtil.createIndex(tableName=grid_ini, 
                                                         fieldName="ID_COL",
                                                         isSpatial=False)))
    cursor.execute(
        f""" 
        DROP TABLE IF EXISTS {grid_ini3};
        CREATE TABLE {grid_ini3}
            AS SELECT   a.ID,
                        b.{ID_UPSTREAM},
                        b.YMAX-ST_Y(a.{GEOM_FIELD}) AS {D_PARK}
            FROM {grid_ini} AS a LEFT JOIN {rec_coord_city_upstream} AS b
            ON a.ID_COL = b.ID
            WHERE   ST_Y(a.{GEOM_FIELD}) > b.YMIN AND
                    ST_Y(a.{GEOM_FIELD}) <= b.YMAX
                    AND b.{ID_UPSTREAM} > 1;
        """)
        
    # Creates the final grid in two steps...
    cursor.execute("{0};{1}".format(DataUtil.createIndex(tableName=grid_ini2, 
                                                         fieldName="ID",
                                                         isSpatial=False),
                                    DataUtil.createIndex(tableName=grid_ini, 
                                                         fieldName="ID",
                                                         isSpatial=False)))
    cursor.execute(
        f""" 
        DROP TABLE IF EXISTS {grid_ini4};
        CREATE TABLE {grid_ini4}
            AS SELECT   a.*,
                        COALESCE(b.{ID_UPSTREAM}, 1) AS {ID_UPSTREAM},
                        COALESCE(b.{D_PARK_INPUT}, {DEFAULT_D_PARK_INPUT}) AS {D_PARK_INPUT},
                        COALESCE(b.{D_PARK_OUTPUT}, {DEFAULT_D_PARK_OUTPUT}) AS {D_PARK_OUTPUT},
                        COALESCE(b.CORRIDOR_AREA / ((ABS(b.{D_PARK_OUTPUT}) + ABS(b.{D_PARK_INPUT})) * {dx}),
                                 {DEFAULT_CORRIDOR_AREA}) AS {CORRIDOR_PARK_FRAC}                        
            FROM {grid_ini} AS a LEFT JOIN {grid_ini2} AS b
            ON a.ID = b.ID;
        """)
    cursor.execute("{0};{1}".format(DataUtil.createIndex(tableName=grid_ini3, 
                                                         fieldName="ID",
                                                         isSpatial=False),
                                    DataUtil.createIndex(tableName=grid_ini4, 
                                                         fieldName="ID",
                                                         isSpatial=False)))
    all_cols = DataUtil.getColumns(cursor = cursor,
                                   tableName = grid_ini4)
    all_cols.remove(ID_UPSTREAM)
    cursor.execute(
        f""" 
        DROP TABLE IF EXISTS {grid};
        CREATE TABLE {grid}
            AS SELECT   a.{", a.".join(all_cols)},
                        COALESCE(b.{ID_UPSTREAM}, a.{ID_UPSTREAM}) AS {ID_UPSTREAM},
                        COALESCE(b.{D_PARK}, {DEFAULT_D_PARK}) AS {D_PARK}
            FROM {grid_ini4} AS a LEFT JOIN {grid_ini3} AS b
            ON a.ID = b.ID;
        """)
   
                  
    # Creates cross wind lines
    list_crosswind_lines = ["""('LINESTRING({0} {1}, {2} {1})', {3})
                 """.format(park_bb_xmin - dx * nCrossWindOut / 2,
                            park_bb_ymin - park_bb_ysize + i * CROSSWIND_LINE_DIST,
                            park_bb_xmin + park_bb_xsize + dx * nCrossWindOut / 2,
                            i + 1)
                     for i in range(0, int(3 * park_bb_ysize / CROSSWIND_LINE_DIST))]
    cursor.execute(
        """
        DROP TABLE IF EXISTS TEMPO, {0};
        CREATE TABLE TEMPO({1} GEOMETRY, ID INT);
        INSERT INTO TEMPO VALUES {2};
        CREATE TABLE {0}
            AS SELECT ST_SETSRID({1}, {3}) AS {1}, ID
            FROM TEMPO;
        DROP TABLE IF EXISTS TEMPO;
        """.format( crosswind_line                      , GEOM_FIELD, 
                    ", ".join(list_crosswind_lines)     , srid))
                  
    # Delete temporary tables if not debug mode              
    if not DEBUG:
        cursor.execute(
            """
            DROP TABLE IF EXISTS {0}, {1}, {2}, {3}, {4}
            """.format( rec_ini                 , line_ini,
                        rec_park                , rec_city,
                        rec_city_coord          , "RECT_PARK_OK",
                        "RECT_CITY_OK"          , rec_park_coord))
    
    return rec_coord_park_upstream, rec_coord_city_upstream, grid, crosswind_line, dx

def loadInputData(cursor, parkBoundaryFilePath, parkGroundFilePath, 
                  parkCanopyFilePath, buildingFilePath, srid, 
                  canopy_cover_type, ground_cover_type, build_height,
                  build_age, build_wwr, build_shutter, build_nat_ventil):
    """ Load input data and makes some few tests.

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

			cursor: conn.cursor
				A cursor object, used to perform queries        
            parkBoundaryFilePath: String
                File path for park boundary input data
            parkGroundFilePath: String
                File path for park ground input data
            parkCanopyFilePath: String
                File path for park canopy input data
            buildingFilePath: String
                File path for buildings input data
            srid: int
                EPSG code that will be assigned to each input data
            canopy_cover_type: string
                Canopy cover type column name
            ground_cover_type: string
                Ground cover type column name
            build_height: string
                Building height column name
            build_age: string
                Building age column name
            build_wwr: string
                Building wind to wall ratio column name
            build_shutter: string
                Building shutter column name
            build_nat_ventil: string
                Building natural ventilation column name
        
		Returns
		_ _ _ _ _ _ _ _ _ _ 

			tempo_park_canopy: String
				Name of the park canopy temporary table
			tempo_park_ground: String
				Name of the park ground temporary table
			tempo_build: String
				Name of the bulding temporary table"""    
    # Temporary tables (and prefix for temporary tables)
    tempo_park_canopy = DataUtil.postfix("TEMPO_PARK_CANOPY")
    tempo_park_ground = DataUtil.postfix("TEMPO_PARK_GROUND")
    tempo_build = DataUtil.postfix("TEMPO_BUILD")
    
    # Load files in the H2GIS database
    # loadData.loadFile(cursor = cursor, 
    #                   filePath = parkBoundaryFilePath, 
    #                   tableName = PARK_BOUNDARIES_TAB, 
    #                   srid = 4326, 
    #                   srid_repro = srid)
    loadData.loadFile(cursor = cursor, 
                      filePath = parkBoundaryFilePath, 
                      tableName = PARK_BOUNDARIES_TAB, 
                      srid = srid, 
                      srid_repro = None)
    
    loadData.loadFile(cursor = cursor, 
                      filePath = buildingFilePath, 
                      tableName = tempo_build, 
                      srid = srid, 
                      srid_repro = None)
    
    loadData.loadFile(cursor = cursor, 
                      filePath = parkCanopyFilePath, 
                      tableName = "TEMPO_PARK_CANOPY", 
                      srid = srid, 
                      srid_repro = None)
    
    loadData.loadFile(cursor = cursor, 
                      filePath = parkGroundFilePath, 
                      tableName = "TEMPO_PARK_GROUND", 
                      srid = srid, 
                      srid_repro = None)
    
    # Alter column names
    dict_cols = {"TEMPO_PARK_CANOPY": {canopy_cover_type: TYPE},
                 "TEMPO_PARK_GROUND": {ground_cover_type: TYPE},
                 tempo_build: {build_height: HEIGHT_FIELD,
                               build_age: BUILDING_AGE,
                               build_wwr: BUILDING_WWR,
                               build_shutter: BUILDING_SHUTTER,
                               build_nat_ventil: BUILDING_NATURAL_VENT_RATE}}
    for t in dict_cols.keys():
        for old_col, new_col in dict_cols[t].items():
            if old_col:
                cursor.execute(
                    f"""
                    ALTER TABLE {t} RENAME COLUMN {old_col} TO {new_col};
                    """)
    
    return tempo_park_canopy, tempo_park_ground, tempo_build


def modifyInputData(cursor, tempo_park_canopy, tempo_park_ground, tempo_build,
                    build_height, build_age, build_wwr, build_shutter, build_nat_ventil,
                    default_build_height, default_build_age, 
                    default_build_wwr, default_build_shutter,
                    default_build_nat_ventil):
    """ Modify or fill input data (buildings as well as park ground and canopy layers)
    to have all needed data for the next steps.

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

			cursor: conn.cursor
				A cursor object, used to perform queries
			tempo_park_canopy: String
				Name of the park canopy temporary table
			tempo_park_ground: String
				Name of the park ground temporary table
			tempo_build: String
				Name of the bulding temporary table
            build_height: String
                Name of the building height field
            build_age: String
                Name of the building age field
            build_wwr: String
                Name of the building windows-to-wall ratio field
            build_shutter: String
                Name of the building shutter opening field
            build_nat_ventil: String
                Name of the building natural ventilation rate field
            default_build_height: int
                Default building height value
            default_build_age: int
                Default building age (construction year)
            default_build_wwr: float
                Default building windows-to-wall ratio
            default_build_shutter: float
                Default building shutter opening
            default_build_nat_ventil: float
                Default building natural ventilation rate (vol/h)
            
        
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            distance_max: float
                Maximum distance where the park can have an impact outside its boundaries"""    
    # Explode the potential multipolygons in canopy and ground park data and replace string types by numbers
    sql_ctype_conv = ["WHEN {0} = ''{1}'' THEN {2} ".format(TYPE,
                                                            S_CANOPY[i],
                                                            i)
                          for i in S_CANOPY.index] + ["ELSE NULL END"]
    sql_gtype_conv = ["WHEN {0} = ''{1}'' THEN {2} ".format(TYPE,
                                                            S_GROUND[i],
                                                            i)
                          for i in S_GROUND.index] + ["ELSE NULL END"]
    cursor.execute(
        """
        DROP TABLE IF EXISTS {0}, {1}, TEMPO_PARK_CANOPY_1, TEMPO_PARK_GROUND_1;
        CREATE TABLE TEMPO_PARK_CANOPY_1
            AS SELECT   ST_NORMALIZE(ST_PRECISIONREDUCER(ST_COLLECTIONEXTRACT(ST_INTERSECTION(a.{2}, b.{2}),
                                                                              3),
                                                         3)) AS {2},
                        a.{4}
            FROM ST_EXPLODE('(SELECT {2}, CASE {3} AS {4} 
                              FROM TEMPO_PARK_CANOPY)') AS a,
                   {6} AS b
            WHERE NOT ST_ISEMPTY(a.{2}) AND a.{4} IS NOT NULL;
        CREATE TABLE {0}({2} GEOMETRY, 
                         {4} INTEGER, 
                         ID SERIAL)
            AS SELECT {2} AS {2},
                      {4} AS {4},
                      NULL AS ID
            FROM TEMPO_PARK_CANOPY_1
            WHERE NOT ST_ISEMPTY({2});
        CREATE TABLE TEMPO_PARK_GROUND_1
            AS SELECT   ST_NORMALIZE(ST_PRECISIONREDUCER(ST_COLLECTIONEXTRACT(ST_INTERSECTION(a.{2}, b.{2}), 
                                                                              3),
                                                         3)) AS {2}, 
                        a.{4}
            FROM    ST_EXPLODE('(SELECT {2}, CASE {5} AS {4} 
                               FROM TEMPO_PARK_GROUND)') AS a,
                    {6} AS b
            WHERE NOT ST_ISEMPTY(a.{2}) AND a.{4} IS NOT NULL;
        CREATE TABLE {1}({2} GEOMETRY, 
                         {4} INTEGER, 
                         ID SERIAL)
            AS SELECT {2} AS {2},
                      {4} AS {4},
                      NULL AS ID
            FROM TEMPO_PARK_GROUND_1
            WHERE NOT ST_ISEMPTY({2});
        """.format( PARK_CANOPY             , PARK_GROUND,
                    GEOM_FIELD              , " ".join(sql_ctype_conv),
                    TYPE                    , " ".join(sql_gtype_conv),
                    PARK_BOUNDARIES_TAB))
    
    # Filter only buildings which are at a given distance from park boundaries
    # AND filter out small buildings
    cursor.execute(
        f"""
        SELECT SQRT(POWER(ST_XMAX({GEOM_FIELD})-ST_XMIN({GEOM_FIELD}),2)
                    +POWER(ST_YMAX({GEOM_FIELD})-ST_YMIN({GEOM_FIELD}),2))
        FROM {PARK_BOUNDARIES_TAB}
        """)
    distance_max = cursor.fetchall()[0][0]
    distance_max = max(distance_max, MIN_PARK_BUFFER_DIST)
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS TEMPO_BUILDING_1;
        CREATE TABLE TEMPO_BUILDING_1
            AS SELECT a.*
            FROM {tempo_build} AS a, {PARK_BOUNDARIES_TAB} AS b
            WHERE ST_DWITHIN(a.{GEOM_FIELD}, 
                             b.{GEOM_FIELD},
                             {distance_max})
                 AND ST_AREA(a.{GEOM_FIELD}) > {BUILDING_MINIMUM_SIZE}
        """)
    
    # Fill missing building info with default values
    if build_height and build_height != "":
        sql_height = f"COALESCE({build_height}, {default_build_height})"
    else:
        sql_height = f"{default_build_height}"
    if build_age and build_age != "":
        sql_age = f"COALESCE({build_age}, {default_build_age})"
    else:
        sql_age = f"{default_build_age}"
    if build_wwr and build_wwr != "":
        sql_wwr = f"COALESCE({build_wwr}, {default_build_wwr})"
    else:
        sql_wwr = f"{default_build_wwr}"
    if build_shutter and build_shutter != "":
        sql_shutter = f"COALESCE({build_shutter}, {default_build_shutter})"
    else:
        sql_shutter = f"{default_build_shutter}"
    if build_nat_ventil and build_nat_ventil != "":
        sql_nat_ventil = f"COALESCE({build_nat_ventil}, {default_build_nat_ventil})"
    else:
        sql_nat_ventil = f"{default_build_nat_ventil}"
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS TEMPO_BUILDING_2;
        CREATE TABLE TEMPO_BUILDING_2({ID_FIELD_BUILD} SERIAL,
                                      {GEOM_FIELD} GEOMETRY,
                                      {HEIGHT_FIELD} DOUBLE,
                                      {BUILDING_AGE} INTEGER,
                                      {BUILDING_WWR} DOUBLE,
                                      {BUILDING_SHUTTER} DOUBLE,
                                      {BUILDING_NATURAL_VENT_RATE} DOUBLE)
            AS SELECT   NULL,
                        ST_MAKEVALID(ST_NORMALIZE({GEOM_FIELD})) AS {GEOM_FIELD},
                        {sql_height} AS {HEIGHT_FIELD},
                        {sql_age} AS {BUILDING_AGE},
                        {sql_wwr} AS {BUILDING_WWR},
                        {sql_shutter} AS {BUILDING_SHUTTER},
                        {sql_nat_ventil} AS {BUILDING_NATURAL_VENT_RATE}
            FROM TEMPO_BUILDING_1
        """)
    
    # Set a building height class to each building
    casewhen_sql = " ".join([f"""WHEN {HEIGHT_FIELD} >= {BUILDING_SIZE_CLASSES.loc[i, "low_limit"]}
                                      AND {HEIGHT_FIELD} < {BUILDING_SIZE_CLASSES.loc[i+1, "low_limit"]}
                                 THEN {i} """
                             for i in BUILDING_SIZE_CLASSES.index[0:-1]])
    casewhen_sql += f"""WHEN {HEIGHT_FIELD} >= {BUILDING_SIZE_CLASSES.loc[BUILDING_SIZE_CLASSES.index[-1], "low_limit"]}
                        THEN {BUILDING_SIZE_CLASSES.index[-1]}"""
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS TEMPO_BUILDING_3;
        CREATE TABLE TEMPO_BUILDING_3 
            AS SELECT   {ID_FIELD_BUILD},
                        {GEOM_FIELD},
                        {HEIGHT_FIELD},
                        {BUILDING_WWR},
                        {BUILDING_SHUTTER},
                        {BUILDING_NATURAL_VENT_RATE},
                        {BUILDING_AGE},
                        CASE {casewhen_sql} END AS {BUILD_SIZE_CLASS}
            FROM TEMPO_BUILDING_2
        """)
    
    
    # Create and fill building age class and all building characteristics
    sql_properties = {}
    properties = list(BUILDING_PROPERTIES[list(BUILDING_PROPERTIES.keys())[0]].columns)
    properties.remove("Name")
    properties.remove("period_start")
    properties.remove("period_end")
        
    for prop in properties:
        sql_properties[prop] = f"""CAST(CASE  """
        for buildt in BUILDING_SIZE_CLASSES.index:
            sql_properties[prop] += f"""WHEN {BUILD_SIZE_CLASS} = {buildt}
                                        THEN CASE""" 
            for period in BUILDING_PROPERTIES[buildt].index:
                sql_properties[prop] += f""" WHEN {BUILDING_AGE} >= {BUILDING_PROPERTIES[buildt].loc[period, "period_start"]} AND {BUILDING_AGE} < {BUILDING_PROPERTIES[buildt].loc[period, "period_end"]}
                                             THEN {BUILDING_PROPERTIES[buildt].loc[period, prop]}"""
            sql_properties[prop] +=" END "
        sql_properties[prop] += f""" END AS DOUBLE) AS {prop}"""
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS {BUILDINGS_TAB};
        CREATE TABLE {BUILDINGS_TAB}
            AS SELECT   {ID_FIELD_BUILD},
                        {GEOM_FIELD},
                        {HEIGHT_FIELD},
                        {BUILDING_WWR},
                        {BUILDING_SHUTTER},
                        {BUILDING_NATURAL_VENT_RATE},
                        {BUILD_SIZE_CLASS},
                        {", ".join(sql_properties.values())}
            FROM TEMPO_BUILDING_3
        """)    
    
    # Delete temporary tables if not debug mode              
    if not DEBUG:
        cursor.execute(
            """
            DROP TABLE IF EXISTS TEMPO_PARK_CANOPY_1, TEMPO_PARK_GROUND_1,
            TEMPO_BUILDING_1, TEMPO_BUILDING_2, TEMPO_BUILDING_3;
            """)
            
    return distance_max
    
def testInputData(cursor):
    """ Test that the loaded input data are OK (after filling with missing values).

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

			cursor: conn.cursor
				A cursor object, used to perform queries
        
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            None"""   
    # Test that there is only a single park to be treated in the park boundaries
    cursor.execute(
        """
        SELECT COUNT(*) FROM {0}
        """.format(PARK_BOUNDARIES_TAB))
    nparks = cursor.fetchall()[0][0]
    # A CONVERTIR EN ERREUR
    if nparks!=1:
        print("""Verify your input data, there is {0} parks in your park_boundaries
              input data whereas exactly one is needed !
              """.format(nparks))
    
    # Test that there is only limited surface superimposition of two ground types or canopy types
    cursor.execute(
        """
        SELECT 1-ST_AREA(ST_ACCUM({0}))/ST_AREA(ST_UNION(ST_ACCUM({0}))) AS F
        FROM {1};
        """.format(GEOM_FIELD                   , PARK_CANOPY))
    canopy_duplic = cursor.fetchall()[0][0]
    cursor.execute(
        """
        SELECT 1-ST_AREA(ST_ACCUM({0}))/ST_AREA(ST_UNION(ST_ACCUM({0}))) AS F
        FROM {1};
        """.format(GEOM_FIELD                   , PARK_GROUND))
    ground_duplic = cursor.fetchall()[0][0]
    
    # A CONVERTIR EN ERREUR
    if canopy_duplic > SUPERIMP_THRESH or ground_duplic > SUPERIMP_THRESH:
        print("""Verify your input data, there is about {0} % superimposition in
              the canopy layer and {1} % in the ground layer
              """.format(str(int(canopy_duplic*100)), str(int(ground_duplic*100))))
    
    # Test that the park ground covers almost entirely the park
    cursor.execute(
        """
        SELECT ST_AREA(ST_UNION(ST_ACCUM(a.{0})))/ST_AREA(b.{0})
        FROM {1} AS a, {2} AS b
        GROUP BY b.{0};
        """.format( GEOM_FIELD           , PARK_GROUND,
                    PARK_BOUNDARIES_TAB))
    ground_to_park_ratio = cursor.fetchall()[0][0]
    # A CONVERTIR EN ERREUR
    if ground_to_park_ratio < GROUND_TO_PARK_RATIO:
        print("""Verify your input data, there is only {0} % of your ground data
              that covers your park within its boundaries (> {1} % needed
              """.format(str(int(ground_to_park_ratio*100)), str(int(GROUND_TO_PARK_RATIO*100))))       
    
            

def calc_park_fractions(cursor, rect_park, ground_cover, canopy_cover, wind_dir):            
    """ Calculates for each park corridor in a given direction the park
    fraction of each combination of ground / canopy covers

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

			cursor: conn.cursor
				A cursor object, used to perform queries        
            rect_park: String
                Table name where park boundaries are saved
            ground_cover: String
                Table name where park ground cover types are saved
            canopy_cover: String
                Table name where park canopy cover types are saved
            wind_dir: float
                wind direction (clock-wise, ° from North)
        
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            rect_park_frac: String
                Name of the table where are saved park corridors with corresponding
                cover fractions"""             
    
    # Temporary tables (and prefix for temporary tables)
    cover_combin = DataUtil.postfix("COVER_COMBINATION")
    cover_combin_poly = DataUtil.postfix("COVER_COMBINATION_POLY")
    cover_combin_plus_ground = DataUtil.postfix("COVER_COMBINATION_PLUS_GROUND")
    cover_combin_plus_ground_repl = DataUtil.postfix("COVER_COMBINATION_PLUS_GROUND_REPL")
    rect_park_frac_buf = DataUtil.postfix("RECT_PARK_FRAC_BUF")
    rect_park_frac_buf2 = DataUtil.postfix("RECT_PARK_FRAC_BUF2")
    
    # Output table names
    rect_park_frac = DataUtil.postfix("RECT_PARK_FRAC", str(wind_dir).replace(".", "_"))
    
    
    # Combine ground and canopy layers
    cursor.execute(
        """
        {0};{1};
        DROP TABLE IF EXISTS {2};
        CREATE TABLE {2}
            AS SELECT   a.ID,
                        ST_INTERSECTION(a.{3}, b.{3}) AS {3},
                        a.{4} + b.{4} AS {4}
            FROM {5} AS a, {6} AS b
            WHERE a.{3} && b.{3} AND ST_INTERSECTS(a.{3}, b.{3})
            UNION ALL
            SELECT      a.ID,
                        ST_DIFFERENCE(a.{3}, ST_UNION(ST_ACCUM(b.{3}))) AS {3},
                        a.{4}
            FROM {5} AS a, {6} AS b
            WHERE a.{3} && b.{3} AND ST_INTERSECTS(a.{3}, b.{3})
            GROUP BY a.{3}
        """.format( DataUtil.createIndex(tableName=ground_cover, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    DataUtil.createIndex(tableName=canopy_cover, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    cover_combin,
                    GEOM_FIELD,
                    TYPE,
                    ground_cover,
                    canopy_cover))
      
    # Explode geometry collections and keep only polygons
    cursor.execute(
        """
        DROP TABLE IF EXISTS {0};
        CREATE TABLE {0}
            AS SELECT   {1}, {2}, ID
            FROM ST_EXPLODE('(SELECT ST_COLLECTIONEXTRACT({1}, 3) AS {1},
                                     {2},
                                     ID
                             FROM {3})')
            WHERE NOT ST_ISEMPTY({1});
        """.format( cover_combin_poly,
                    GEOM_FIELD,
                    TYPE,
                    cover_combin))        
    
    # Union the ground/canopy combinations and the ground without any canopy cover
    cursor.execute(
        """
        {0};{1};
        DROP TABLE IF EXISTS {2};
        CREATE TABLE {2}
            AS SELECT   {3},
                        {4}
            FROM {5}
            UNION ALL
            SELECT      b.{3},
                        b.{4}
            FROM {5} AS a RIGHT JOIN {6} AS b 
            ON a.ID = b.ID
            WHERE a.ID IS NULL;
        """.format( DataUtil.createIndex(tableName=cover_combin_poly, 
                                         fieldName="ID",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=ground_cover, 
                                         fieldName="ID",
                                         isSpatial=False),
                    cover_combin_plus_ground,
                    GEOM_FIELD,
                    TYPE,
                    cover_combin_poly,
                    ground_cover))

    # Non existing combinations are replaced
    combi_replace_sql = [""" WHEN {0} = {1} THEN {2}
                         """.format( TYPE,
                                     i,
                                     REPLACE_COMBI[i])
                         for i in REPLACE_COMBI.index]
    cursor.execute(
        """
        {0};
        DROP TABLE IF EXISTS {1};
        CREATE TABLE {1}
            AS SELECT   {2},
                        CASE {3} ELSE {4} END AS {4}
            FROM {5}
        """.format( DataUtil.createIndex(tableName=cover_combin_plus_ground, 
                                         fieldName=TYPE,
                                         isSpatial=False),
                    cover_combin_plus_ground_repl,
                    GEOM_FIELD,
                    " ".join(combi_replace_sql),
                    TYPE,
                    cover_combin_plus_ground))
    
    
    # Calculate fraction of each combination for each corridor
    cursor.execute(
        """
        {0};{1};{8};{9};{10};
        DROP TABLE IF EXISTS {2};
        CREATE TABLE {2}
            AS SELECT   a.ID,
                        a.{7},
                        a.{3},
                        SUM(ST_AREA(ST_INTERSECTION(a.{3}, b.{3}))) / ST_AREA(a.{3}) AS FRACTION,
                        b.{4}
            FROM {5} AS a, {6} AS b
            WHERE a.{3} && b.{3} AND ST_INTERSECTS(a.{3}, b.{3})
            GROUP BY a.ID, a.{7}, b.{4}
        """.format( DataUtil.createIndex(tableName=rect_park, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    DataUtil.createIndex(tableName=cover_combin_plus_ground_repl, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    rect_park_frac_buf,
                    GEOM_FIELD,
                    TYPE,
                    rect_park,
                    cover_combin_plus_ground_repl,
                    ID_UPSTREAM,
                    DataUtil.createIndex(tableName=rect_park, 
                                         fieldName="ID",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=rect_park, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=cover_combin_plus_ground_repl, 
                                         fieldName=TYPE,
                                         isSpatial=False)))
        
    # Convert the fraction column into as many columns as there are
    # combinations of ground and canopy covers
    casewhen_sql = [""" 
                    COALESCE(CASE WHEN {0} = {1} THEN SUM({2}) END, 0) AS {3}
                    """.format( TYPE,
                                i,
                                "FRACTION",
                                COMBI_FIELD_BASE.format(i))
                    for i in S_GROUND_CANOPY.index.difference(REPLACE_COMBI.index)]
    cursor.execute(
        """
        {0};{1};{2};
        DROP TABLE IF EXISTS {3};
        CREATE TABLE {3}
            AS SELECT   {4},
                        {5},
                        {9},
                        {7}
            FROM {8}
            GROUP BY {4}, {5}, {6};
        
        """.format( DataUtil.createIndex(tableName=rect_park_frac_buf, 
                                         fieldName="ID",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=rect_park_frac_buf, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=rect_park_frac_buf, 
                                         fieldName=TYPE,
                                         isSpatial=False),
                    rect_park_frac_buf2,
                    "ID",
                    ID_UPSTREAM,
                    TYPE,
                    ", ".join(casewhen_sql),
                    rect_park_frac_buf,
                    GEOM_FIELD))

    # Keep only a single row per corridor and fill empty part of corridors with default value...
    combi_columns = DataUtil.getColumns(cursor = cursor, tableName = rect_park_frac_buf2)
    combi_columns.remove(GEOM_FIELD)
    combi_columns.remove("ID")
    combi_columns.remove(ID_UPSTREAM)
    combi_columns_sql = ["MAX({0}) AS {0}".format(i) for i in combi_columns]
    if combi_columns.count(COMBI_FIELD_BASE.format(DEFAULT_COMBI)) == 1:
        combi_columns_sql.remove("MAX({0}) AS {0}".format(COMBI_FIELD_BASE.format(DEFAULT_COMBI)))
        combi_columns.remove(COMBI_FIELD_BASE.format(DEFAULT_COMBI))
    combi_columns_sql += ["1-({0}) AS {1}".format(  "+".join(["MAX({0})".format(i) for i in combi_columns]),
                                                COMBI_FIELD_BASE.format(DEFAULT_COMBI))] 
    cursor.execute(
        """
        {0};{1};
        DROP TABLE IF EXISTS {2};
        CREATE TABLE {2}
            AS SELECT   {3},
                        {4},
                        {7},
                        {5}
            FROM {6}
            GROUP BY {3}, {4};
        """.format( DataUtil.createIndex(tableName=rect_park_frac_buf2, 
                                         fieldName="ID",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=rect_park_frac_buf2, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    rect_park_frac,
                    "ID",
                    ID_UPSTREAM,
                    ", ".join(combi_columns_sql),
                    rect_park_frac_buf2,
                    GEOM_FIELD))

    # Delete temporary tables if not debug mode              
    if not DEBUG:
        cursor.execute(
            """
            DROP TABLE IF EXISTS {0}, {1}, {2}, {3}, {4}, {5};
            """.format( cover_combin                , cover_combin_poly,
                        cover_combin_plus_ground    , cover_combin_plus_ground_repl,
                        rect_park_frac_buf          , rect_park_frac_buf2))              
                    
    return rect_park_frac


def createsBlocks(cursor, inputBuildings, snappingTolerance = GEOMETRY_MERGE_TOLERANCE):
    """ Creates blocks and stacked blocks from buildings touching each other.

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

            cursor: conn.cursor
                A cursor object, used to perform spatial SQL queries
            inputBuildings: String
                Name of the table containing building geometries and height
            snappingTolerance: float, default GEOMETRY_MERGE_TOLERANCE
                Distance in meter below which two buildings are 
                considered as touching each other (m)
            
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            blockTable: String
                Name of the table containing the block geometries
                (only block of touching buildings independantly of their height)
            buildingTable: String
                Name of the table containing the building geometry and attributes
                as well as the block ID """
    print("Creates blocks and stacked blocks")
    # Creates final tables
    blockTable = DataUtil.prefix("block_table", prefix = "")
    buildingTable = DataUtil.prefix("building_table", prefix = "")

    # Creates the block (a method based on network - such as H2network
    # would be much more efficient)
    cursor.execute("""
       DROP TABLE IF EXISTS {0}; 
       CREATE TABLE {0} 
            AS SELECT EXPLOD_ID AS {1}, ST_MAKEVALID(ST_SIMPLIFY(ST_NORMALIZE({2}), {5})) AS {2} 
            FROM ST_EXPLODE ('(SELECT ST_UNION(ST_ACCUM(ST_BUFFER({2},{3},''join=mitre'')))
                             AS {2} FROM {4})');
            """.format(blockTable           , ID_FIELD_BLOCK,
                        GEOM_FIELD          , snappingTolerance,
                        inputBuildings      , GEOMETRY_SIMPLIFICATION_DISTANCE))

    # Identify building/block relations and convert building height to integer
    build_cols = DataUtil.getColumns(cursor = cursor,
                                     tableName = inputBuildings)
    build_cols.remove(HEIGHT_FIELD)
    build_cols.remove(GEOM_FIELD)
    cursor.execute("""
       {7};
       {8};
       DROP TABLE IF EXISTS {0};
        CREATE TABLE {0} 
                AS SELECT   a.{1}, ST_MAKEVALID(a.{2}) AS {2},
                            CAST(a.{3} AS INT) AS {3}, b.{4}
                FROM    {5} AS a, {6} AS b
                WHERE   a.{2} && b.{2} AND ST_INTERSECTS(a.{2}, b.{2});
        """.format( buildingTable               , ", a.".join(build_cols), 
                    GEOM_FIELD                  , HEIGHT_FIELD, 
                    ID_FIELD_BLOCK              , inputBuildings, 
                    blockTable                  , DataUtil.createIndex( tableName=inputBuildings, 
                                                                        fieldName=GEOM_FIELD,
                                                                        isSpatial=True),
                    DataUtil.createIndex(tableName=blockTable, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True)))
                    
    return buildingTable, blockTable


def calc_rect_block_indic(cursor, blocks, rect_city, wind_dir):
    """ Calculates fraction of block per corridor and density of block number.

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

            cursor: conn.cursor
                A cursor object, used to perform spatial SQL queries
            blocks: String
                Name of the block table
            rect_city: String
                Name of the table where urban corridors around the park are saved
            wind_dir: float
                wind direction (clock-wise, ° from North)
        
            
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            rectIndicBlock: String
                Name of the table containing the corridors geometries
                and the block indicator results"""
    # Temporary tables (and prefix for temporary tables)
    correl_rect_blocks = DataUtil.postfix("CORREL_RECT_BLOCKS")
    
    # Output table names
    rectIndicBlock = DataUtil.postfix("CITY_INDIC_BLOCKS", str(wind_dir).replace(".", "_"))

    # Calculates the intersections between blocks and city "rectangles"
    cursor.execute(
        """ 
        {0};{1};
        DROP TABLE IF EXISTS {2};
        CREATE TABLE {2}
            AS SELECT   a.{3},
                        a.{8},
                        b.{4},
                        a.{5},
                        ST_AREA(ST_INTERSECTION(a.{5}, b.{5})) AS AREA_BLOCK_INTER,
                        ST_AREA(b.{5}) AS AREA_BLOCK_TOT
            FROM {6} AS a, {7} AS b
            WHERE a.{5} && b.{5} AND ST_INTERSECTS(a.{5}, b.{5})
        """.format( DataUtil.createIndex(tableName=blocks, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    DataUtil.createIndex(tableName=rect_city, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    correl_rect_blocks          , "ID",
                    ID_FIELD_BLOCK              , GEOM_FIELD,
                    rect_city                   , blocks,
                    ID_UPSTREAM))

    # Calculates the indicators
    cursor.execute(
        """ 
        {0};{7};{10};{11};
        DROP TABLE IF EXISTS {1};
        CREATE TABLE {1}
            AS SELECT   b.{2}, 
                        b.{8},
                        b.{3},
                        COALESCE(SUM(a.AREA_BLOCK_INTER/a.AREA_BLOCK_TOT)/ST_AREA(a.{3}), 0) AS {4},
                        COALESCE(SUM(a.AREA_BLOCK_INTER)/ST_AREA(a.{3}), 0) AS {5}
            FROM {6} AS a RIGHT JOIN {9} AS b
            ON a.{2} = b.{2} AND a.{8} = b.{8}
            GROUP BY b.{2}, b.{8}
        """.format( DataUtil.createIndex(tableName=correl_rect_blocks, 
                                         fieldName="ID",
                                         isSpatial=False),
                    rectIndicBlock          , "ID",
                    GEOM_FIELD              , BLOCK_NB_DENSITY,
                    BLOCK_SURF_FRACTION     , correl_rect_blocks,
                    DataUtil.createIndex(tableName=correl_rect_blocks, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    ID_UPSTREAM             , rect_city,
                    DataUtil.createIndex(tableName=rect_city, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=rect_city, 
                                         fieldName="ID",
                                         isSpatial=False)))
    
    # Delete temporary tables if not debug mode              
    if not DEBUG:
        cursor.execute(
            """
            DROP TABLE IF EXISTS {0};
            """.format( correl_rect_blocks)) 
            
    return rectIndicBlock

def calc_rect_build_height(cursor, buildings, rect_city, wind_dir):
    """ Calculates mean building height indicators per corridor.

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

            cursor: conn.cursor
                A cursor object, used to perform spatial SQL queries
            buildings: String
                Name of the table where buildings are saved
            rect_city: String
                Name of the table where urban corridors around the park are saved
            wind_dir: float
                wind direction (clock-wise, ° from North)
        
            
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            rectIndicBuild: String
                Name of the table containing the rectangle geometries
                and the building height indicator results"""
    # Temporary tables (and prefix for temporary tables)
    correl_rect_builds = DataUtil.postfix("CORREL_RECT_BUILDS")
    
    # Output table names
    rectIndicBuild = DataUtil.postfix("CITY_INDIC_BUILDS", str(wind_dir).replace(".", "_"))

    # Calculates the intersections between buildings and city "rectangles"
    cursor.execute(
        """ 
        {0};{1};
        DROP TABLE IF EXISTS {2};
        CREATE TABLE {2}
            AS SELECT   a.{3},
                        a.{8},
                        b.{4},
                        a.{5},
                        ST_AREA(ST_INTERSECTION(a.{5}, b.{5})) AS AREA_BUILD
            FROM {6} AS a, {7} AS b
            WHERE a.{5} && b.{5} AND ST_INTERSECTS(a.{5}, b.{5})
        """.format( DataUtil.createIndex(tableName=buildings, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    DataUtil.createIndex(tableName=rect_city, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    correl_rect_builds          , "ID",
                    HEIGHT_FIELD                , GEOM_FIELD,
                    rect_city                   , buildings,
                    ID_UPSTREAM))

    # Calculates the indicators
    cursor.execute(
        """ 
        {0};{7};{10};{11};
        DROP TABLE IF EXISTS {1};
        CREATE TABLE {1}
            AS SELECT   b.{2}, 
                        b.{8},
                        b.{3},
                        COALESCE(EXP(1.0/COUNT(a.*)*SUM(LOG(a.{4}))),0) AS {5},
                        COALESCE(SUM(a.AREA_BUILD*a.{4})/SUM(a.AREA_BUILD), 0) AS {9}
            FROM {6} AS a RIGHT JOIN {12} AS b
            ON a.{2} = b.{2} AND a.{8} = b.{8}
            GROUP BY b.{2}, b.{8}
        """.format( DataUtil.createIndex(tableName=correl_rect_builds, 
                                         fieldName="ID",
                                         isSpatial=False),
                    rectIndicBuild          , "ID",
                    GEOM_FIELD              , HEIGHT_FIELD,
                    GEOM_MEAN_BUILD_HEIGHT  , correl_rect_builds,
                    DataUtil.createIndex(tableName=correl_rect_builds, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    ID_UPSTREAM             , MEAN_BUILD_HEIGHT,
                    DataUtil.createIndex(tableName=rect_city, 
                                         fieldName="ID",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=rect_city, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    rect_city))
    
    # Delete temporary tables if not debug mode              
    if not DEBUG:
        cursor.execute(
            """
            DROP TABLE IF EXISTS {0};
            """.format( correl_rect_builds)) 
            
    return rectIndicBuild


def calc_street_indic(cursor, blocks, rect_city, crosswind_lines, wind_dir):
    """ Calculates street indicators (size, number) per corridors.

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

            cursor: conn.cursor
                A cursor object, used to perform spatial SQL queries
            blocks: String
                Name of the table where blocks are saved
            rect_city: String
                Name of the table where urban corridors around the park are saved
            crosswind_lines: String
                Name of the table where cross wind lines are saved
            wind_dir: float
                wind direction (clock-wise, ° from North)
        
            
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            rectIndicStreet: String
                Name of the table containing the rectangle geometries
                and the street indicator results"""
    # Temporary tables (and prefix for temporary tables)
    rect_line_corr = DataUtil.postfix("RECT_LINE_CORR")
    streets_tab = DataUtil.postfix("STREET_TAB")
    splitted_streets_only = DataUtil.postfix("SPLITTED_STREETS_ONLY")
    streets_extremities = DataUtil.postfix("STREET_EXTREMITIES")
    real_streets = DataUtil.postfix("REAL_STREETS")
    first_street_indic = DataUtil.postfix("FIRST_STREET_INDIC")
    second_street_indic_buf = DataUtil.postfix("SECOND_STREET_INDIC_BUF")
    rect_indic_street_tempo = DataUtil.postfix("RECT_INDIC_STREET_TEMPO")
    
    # Output table names
    rectIndicStreet = DataUtil.postfix("CITY_INDIC_STREET", str(wind_dir).replace(".", "_"))

    # Calculates the intersection of each line with each corridor
    cursor.execute(
        """ 
        {0};{1};
        DROP TABLE IF EXISTS {2};
        CREATE TABLE {2}
            AS SELECT   a.{3} AS {4},
                        a.{5},
                        a.{6},
                        b.{7},
                        ST_LENGTH(ST_INTERSECTION(a.{6}, b.{6})) AS L_rec
            FROM {8} AS a, {9} AS b
            WHERE   a.{6} && b.{6} AND ST_INTERSECTS(a.{6}, b.{6})
        """.format( DataUtil.createIndex(tableName=crosswind_lines, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    DataUtil.createIndex(tableName=rect_city, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    rect_line_corr              , "ID",
                    "ID_RECT"                   , ID_UPSTREAM,
                    GEOM_FIELD                  , "ID", 
                    rect_city                   , crosswind_lines))
                    
    # Calculates the diff between crosswind lines and blocks (to get kind of "streets width")
    cursor.execute(
        """ 
        {0};{1};
        DROP TABLE IF EXISTS {2};
        CREATE TABLE {2}
            AS SELECT   {3},
                        EXPLOD_ID AS {4},
                        {5},
                        ST_LENGTH({5}) AS {6}
            FROM ST_EXPLODE('(  SELECT  a.{3}, 
                                        ST_DIFFERENCE(a.{5}, ST_UNION(ST_ACCUM(b.{5}))) AS {5}
                                FROM {7} AS a, {8} AS b
                                WHERE a.{5} && b.{5} AND ST_INTERSECTS(a.{5}, b.{5})
                                GROUP BY a.{5}, a.{3})')
            WHERE NOT ST_ISEMPTY({5})
        """.format( DataUtil.createIndex(tableName=crosswind_lines, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    DataUtil.createIndex(tableName=blocks, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    streets_tab                 , "ID",
                    ID_STREET                   , GEOM_FIELD,
                    STREET_WIDTH                , crosswind_lines,
                    blocks))

    # Calculates the block id of each street extremities to check that streets are real streets...
    cursor.execute(
        """ 
        {0};{1};
        DROP TABLE IF EXISTS {2};
        CREATE TABLE {2}
            AS SELECT   a.{3},
                        a.{4},
                        a.{5},
                        a.{6},
                        b.{7}
            FROM {8} AS a, {9} AS b
            WHERE a.{5} && b.{5} AND ST_INTERSECTS(a.{5}, b.{5})
        """.format( DataUtil.createIndex(tableName=streets_tab, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    DataUtil.createIndex(tableName=blocks, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    streets_extremities         , "ID",
                    ID_STREET                   , GEOM_FIELD,
                    STREET_WIDTH                , ID_FIELD_BLOCK, 
                    streets_tab                 , blocks))
                    
    # Calculates the intersection of each street with each corridor
    cursor.execute(
        """ 
        {0};{1};{2};{12};
        DROP TABLE IF EXISTS {3};
        CREATE TABLE {3}
            AS SELECT   a.{4}, 
                        a.{5},
                        b.{4} AS {6},
                        b.{13},
                        b.{7},
                        ST_LENGTH(ST_INTERSECTION(a.{7}, b.{7})) AS L_INTER,
                        MAX(a.{8}) AS {8},
                        MAX(a.{11}) AS ID_BLOCK1,
                        MIN(a.{11}) AS ID_BLOCK2
            FROM {9} AS a, {10} AS b
            WHERE   a.{7} && b.{7} AND ST_INTERSECTS(a.{7}, b.{7})
            GROUP BY a.{4}, a.{5}, b.{4}, b.{13}
        """.format( DataUtil.createIndex(tableName=streets_extremities, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    DataUtil.createIndex(tableName=rect_city, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    DataUtil.createIndex(tableName=streets_extremities, 
                                         fieldName="ID",
                                         isSpatial=False),
                    real_streets                , "ID",
                    ID_STREET                   , "ID_RECT",
                    GEOM_FIELD                  , STREET_WIDTH, 
                    streets_extremities         , rect_city,
                    ID_FIELD_BLOCK,
                    DataUtil.createIndex(tableName=streets_extremities, 
                                         fieldName=ID_STREET,
                                         isSpatial=False),
                    ID_UPSTREAM))
                    
    # Keep only streets in a given corridor if at least one of the building 
    # is in the corridor and if the street is shared 
    # between two blocks and not a single one (only if real street)
    cursor.execute(
        """ 
        {0};{1};{2};{3};{4};{5};{6};{7};
        DROP TABLE IF EXISTS {8};
        CREATE TABLE {8}
            AS SELECT   a.{9}, 
                        a.{10},
                        a.{11},
                        a.{12},
                        a.{13},
                        a.{14},
                        b.L_REC
            FROM {15} AS a LEFT JOIN {16} AS b
            ON a.{9} = b.{9} AND a.{10} = b.{10} AND a.{11} = b.{11}
            WHERE a.L_INTER < b.L_REC AND a.ID_BLOCK1 <> a.ID_BLOCK2
            GROUP BY a.{9}, a.{10}, a.{11}, a.{12}
        """.format( DataUtil.createIndex(tableName=real_streets, 
                                         fieldName="ID_RECT",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=real_streets, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=real_streets, 
                                         fieldName="ID",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=real_streets, 
                                         fieldName="ID_BLOCK1",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=real_streets, 
                                         fieldName="ID_BLOCK2",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=rect_line_corr, 
                                         fieldName="ID_RECT",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=rect_line_corr, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=rect_line_corr, 
                                         fieldName="ID",
                                         isSpatial=False),
                    splitted_streets_only       , "ID_RECT",
                    ID_UPSTREAM                 , "ID",
                    ID_STREET                   , GEOM_FIELD,
                    STREET_WIDTH                , real_streets,
                    rect_line_corr))
                    
                    
    # Calculates the median street width only if the street is shared 
    # between two blocks and not a single one (only if real street)
    cursor.execute(
        """ 
        {0};{1};
        DROP TABLE IF EXISTS {2};
        CREATE TABLE {2}
            AS SELECT   {3},
                        {4},
                        {7},
                        CAST(MEDIAN({5}) AS DOUBLE) AS {5}
            FROM {6}
            GROUP BY {3}, {4}, {7}
        """.format( DataUtil.createIndex(tableName=splitted_streets_only, 
                                         fieldName="ID_RECT",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=splitted_streets_only, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    first_street_indic          , "ID_RECT",
                    GEOM_FIELD                  , STREET_WIDTH,
                    splitted_streets_only       , ID_UPSTREAM))
                    
    # Calculates the density of street number per line only if the street is shared 
    # between two blocks and not a single one (only if real street)
    cursor.execute(
        """ 
        {0};{1};{2};
        DROP TABLE IF EXISTS {4};
        CREATE TABLE {4}
            AS SELECT   {5},
                        {6},
                        {7},
                        {9},
                        CAST(COUNT(*) AS DOUBLE) / (CAST(COUNT(*) AS DOUBLE) + MAX({3})) AS STREET_NUMBER_DENSITY
            FROM {8}
            GROUP BY {5}, {6}, {7}, {9}
        """.format( DataUtil.createIndex(tableName=splitted_streets_only, 
                                         fieldName="ID_RECT",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=splitted_streets_only, 
                                         fieldName="ID",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=splitted_streets_only, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    "L_rec"                     , second_street_indic_buf,
                    "ID_RECT"                   , "ID",
                    GEOM_FIELD                  , splitted_streets_only,
                    ID_UPSTREAM))
                        
    # Calculates the mean density of street number and gather with previous indicator
    # Calculates also the fraction of opening of the park on the streets
    cursor.execute(
        """ 
        {0};{1};{10};{11};
        DROP TABLE IF EXISTS {2};
        CREATE TABLE {2}
            AS SELECT   a.{3} AS ID,
                        a.{9},
                        a.{4},
                        a.{5},
                        AVG(b.STREET_NUMBER_DENSITY) AS {6},
                        AVG(b.STREET_NUMBER_DENSITY) * a.{5} AS {12}
            FROM {7} AS a LEFT JOIN {8} AS b
            ON a.{3} = b.{3} AND a.{9} = b.{9}
            GROUP BY b.{3}, a.{4}, a.{9}
        """.format( DataUtil.createIndex(tableName=first_street_indic, 
                                         fieldName="ID_RECT",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=second_street_indic_buf, 
                                         fieldName="ID_RECT",
                                         isSpatial=False),
                    rect_indic_street_tempo     , "ID_RECT",
                    GEOM_FIELD                  , STREET_WIDTH,
                    NB_STREET_DENSITY           , first_street_indic,
                    second_street_indic_buf     , ID_UPSTREAM,
                    DataUtil.createIndex(tableName=first_street_indic, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=second_street_indic_buf, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    OPENING_FRACTION))
    
    # Fill in some of the null value indicators
    cursor.execute(
        f""" 
        {DataUtil.createIndex(tableName=rect_indic_street_tempo, 
                              fieldName=ID_UPSTREAM,
                              isSpatial=False)};
        {DataUtil.createIndex(tableName=rect_city, 
                              fieldName=ID_UPSTREAM,
                              isSpatial=False)}; 
        {DataUtil.createIndex(tableName=rect_indic_street_tempo, 
                              fieldName="ID",
                              isSpatial=False)};
        {DataUtil.createIndex(tableName=rect_city, 
                              fieldName="ID",
                              isSpatial=False)};
        DROP TABLE IF EXISTS {rectIndicStreet};
        CREATE TABLE {rectIndicStreet}
            AS SELECT   a.ID,
                        a.{ID_UPSTREAM},
                        a.{GEOM_FIELD},
                        b.{STREET_WIDTH},
                        COALESCE(b.{NB_STREET_DENSITY}, 0) AS {NB_STREET_DENSITY},
                        COALESCE(b.{OPENING_FRACTION}, 1) AS {OPENING_FRACTION}
            FROM {rect_city} AS a LEFT JOIN {rect_indic_street_tempo} AS b
            ON a.{ID_UPSTREAM} = b.{ID_UPSTREAM} AND a.ID = b.ID
            GROUP BY a.ID, a.{ID_UPSTREAM}
        """)
                    
    # Delete temporary tables if not debug mode              
    if not DEBUG:
        cursor.execute(
            """
            DROP TABLE IF EXISTS {0}, {1}, {2}, {3}, {4}, {5}, {6};
            """.format( streets_tab                 , streets_extremities,
                        real_streets                , first_street_indic,
                        second_street_indic_buf     , rect_line_corr,
                        splitted_streets_only       , rect_indic_street_tempo)) 
            
    return rectIndicStreet

def generic_facade_indicators(cursor, buildings, rsu, indic, wind_dir):
    """ Calculates facade density per corridor.

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

            cursor: conn.cursor
                A cursor object, used to perform spatial SQL queries
            buildings: String
                Name of the table where buildings are saved
            rsu: String
                Name of the table where urban corridors around the park are saved
            indic: String
                Name of the facade indicator to calculate. Possible values are:
                    -> FREE_FACADE_FRACTION
                    -> ASPECT_RATIO
            wind_dir: float
                wind direction (clock-wise, ° from North)
        
            
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            rsuFacadeIndic: String
                Name of the table containing the rsu geometries
                and the facade indicator results"""
                
    # Temporary table names
    correl_rsu_builds = DataUtil.postfix("CORREL_RSU_BUILDS")
    buildLine = DataUtil.postfix("build_Line")
    buildLineRsu = DataUtil.postfix("build_Line_rsu")
    sharedLineRsu = DataUtil.postfix("share_Line_rsu")
    onlyBuildRsu = DataUtil.postfix("only_Build_rsu")

    # Output table
    rsuFacadeIndic = DataUtil.postfix(indic + "_INDIC", str(wind_dir).replace(".", "_"))

    # Calculates the intersections between buildings and city "rectangles"
    cursor.execute(
        """ 
        {0};{1};
        DROP TABLE IF EXISTS {2};
        CREATE TABLE {2}
            AS SELECT   a.{3},
                        a.{4},
                        b.{5},
                        b.{6},
                        b.{9}
            FROM {7} AS a, {8} AS b
            WHERE a.{5} && b.{5} AND ST_INTERSECTS(a.{5}, b.{5})
        """.format( DataUtil.createIndex(tableName=buildings, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    DataUtil.createIndex(tableName=rsu, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True),
                    correl_rsu_builds         , "ID",
                    ID_UPSTREAM                , GEOM_FIELD,
                    HEIGHT_FIELD               , rsu,
                    buildings                  , ID_FIELD_BUILD))


    # Convert the building polygons into lines and create the intersection with corridors polygons
    cursor.execute(
        """ 
        {0};{1};{2};{3};    
        """.format( DataUtil.createIndex(tableName=correl_rsu_builds, 
                                        fieldName="ID",
                                        isSpatial=False),
                    DataUtil.createIndex(tableName=rsu, 
                                         fieldName="ID",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=correl_rsu_builds, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=rsu, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False)))
    cursor.execute(f"""
        DROP TABLE IF EXISTS {buildLine};
        CREATE TABLE {buildLine}
            AS SELECT   a.{ID_FIELD_BUILD}, a.ID, a.{ID_UPSTREAM},
                        ST_AREA(a.{GEOM_FIELD}) AS BUILD_AREA,
                        ST_AREA(b.{GEOM_FIELD}) AS RSU_AREA,
                        ST_CollectionExtract(ST_INTERSECTION(ST_TOMULTILINE(a.{GEOM_FIELD}), b.{GEOM_FIELD}), 2) AS {GEOM_FIELD},
                        a.{HEIGHT_FIELD}
            FROM {correl_rsu_builds} AS a LEFT JOIN {rsu} AS b
            ON a.ID = b.ID AND a.{ID_UPSTREAM} = b.{ID_UPSTREAM}
        """)

    # Keep only intersected facades within a given distance and calculate their area per RSU
    cursor.execute(
        """ 
        {0};{1};{2};{3};    
        """.format( DataUtil.createIndex(tableName=buildLine, 
                                        fieldName=GEOM_FIELD,
                                        isSpatial=True),
                    DataUtil.createIndex(tableName=buildLine, 
                                         fieldName="ID",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=buildLine, 
                                         fieldName=ID_FIELD_BUILD,
                                         isSpatial=False),
                     DataUtil.createIndex(tableName=buildLine, 
                                          fieldName=ID_UPSTREAM,
                                          isSpatial=False)))
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS {sharedLineRsu};
        CREATE TABLE {sharedLineRsu} 
            AS SELECT   SUM(ST_LENGTH(  ST_INTERSECTION(a.{GEOM_FIELD}, 
                                                        ST_SNAP(b.{GEOM_FIELD}, 
                                                                a.{GEOM_FIELD}, 
                                                                {GEOMETRY_SNAP_TOLERANCE})
                                                        )
                                        )
                            *LEAST(a.{HEIGHT_FIELD}, b.{HEIGHT_FIELD})) AS FACADE_AREA,
                        a.ID,
                        a.{ID_UPSTREAM}
            FROM    {buildLine} AS a LEFT JOIN {buildLine} AS b
                    ON a.ID = b.ID
            WHERE       a.{GEOM_FIELD} && b.{GEOM_FIELD} AND ST_INTERSECTS(a.{GEOM_FIELD}, 
                        ST_SNAP(b.{GEOM_FIELD}, a.{GEOM_FIELD}, {GEOMETRY_SNAP_TOLERANCE})) AND
                        a.{ID_FIELD_BUILD} <> b.{ID_FIELD_BUILD}
            GROUP BY a.ID, a.{ID_UPSTREAM};""")

    # Calculates the building facade area within each RSU
    cursor.execute(
        """ 
        {0};{1};   
        """.format( DataUtil.createIndex(tableName=buildLine, 
                                        fieldName="ID",
                                        isSpatial=False),
                    DataUtil.createIndex(tableName=buildLine, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False)))
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS {buildLineRsu};
        CREATE TABLE {buildLineRsu}
            AS SELECT   ID, 
                        MIN(RSU_AREA) AS RSU_AREA, 
                        SUM(BUILD_AREA) AS BUILD_AREA,
                        {ID_UPSTREAM},
                        SUM(ST_LENGTH({GEOM_FIELD}) * {HEIGHT_FIELD}) AS FACADE_AREA
            FROM {buildLine}
            GROUP BY ID, {ID_UPSTREAM};""")

    # Calculates the facade indicator needed by RSU¨
    if indic == FREE_FACADE_FRACTION:
        sql_indic = """COALESCE((a.FACADE_AREA-b.FACADE_AREA)/(a.FACADE_AREA-b.FACADE_AREA+a.RSU_AREA),
                                a.FACADE_AREA/(a.FACADE_AREA+a.RSU_AREA)) AS {FREE_FACADE_FRACTION}"""
    elif indic == ASPECT_RATIO:
        sql_indic = """COALESCE(0.5*(a.FACADE_AREA-b.FACADE_AREA)/(a.RSU_AREA-a.BUILD_AREA),
                                0.5*a.FACADE_AREA/(a.RSU_AREA-a.BUILD_AREA)) AS {ASPECT_RATIO}"""
    cursor.execute(
        """ 
        {0};{1};{2};{3};    
        """.format( DataUtil.createIndex(tableName=buildLineRsu, 
                                        fieldName="ID",
                                        isSpatial=False),
                    DataUtil.createIndex(tableName=sharedLineRsu, 
                                         fieldName="ID",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=buildLineRsu, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=sharedLineRsu, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False)))
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS {onlyBuildRsu};
        CREATE TABLE {onlyBuildRsu}
            AS SELECT   a.ID,
                        a.{ID_UPSTREAM},
                        {sql_indic}
            FROM {buildLineRsu} AS a LEFT JOIN {sharedLineRsu} AS b
            ON a.ID = b.ID AND a.{ID_UPSTREAM} = b.{ID_UPSTREAM}""")

    # Join RSU having no buildings and set their value to 0
    cursor.execute(
        """ 
        {0};{1};{2};{3};
        """.format( DataUtil.createIndex(tableName=rsu, 
                                         fieldName="ID",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=onlyBuildRsu, 
                                         fieldName="ID",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=rsu, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=onlyBuildRsu, 
                                         fieldName=ID_UPSTREAM,
                                         isSpatial=False)))
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS {rsuFacadeIndic};
        CREATE TABLE {rsuFacadeIndic}
            AS SELECT   a.ID,
                        a.{ID_UPSTREAM},
                        a.{GEOM_FIELD},
                        COALESCE(b.{indic}, 0) AS {indic}
            FROM {rsu} AS a LEFT JOIN {onlyBuildRsu} AS b
            ON a.ID = b.ID AND a.{ID_UPSTREAM} = b.{ID_UPSTREAM}""")

    # Delete temporary tables if not debug mode              
    if not DEBUG:
        # The temporary tables are deleted
        cursor.execute(
            f"""
            DROP TABLE IF EXISTS {buildLine}, {buildLineRsu}, {sharedLineRsu},
                                 {onlyBuildRsu}, {correl_rsu_builds}
            """)
        
    return rsuFacadeIndic

def calc_build_indic(cursor, buildings, blocks, prefix):
    """ Calculates buiding indicators

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

            cursor: conn.cursor
                A cursor object, used to perform spatial SQL queries
            buildings: String
                Name of the table where buildings are saved
            blocks: String
                Name of the table where blocks are saved
            prefix: String
                Prefix to add at the beginning of the output table
        
            
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            build_indic: String
                Name of the table containing the building geometries
                and the indicators results"""
    
    # Temporary table names
    shared_wall = DataUtil.postfix("SHARED_WALL")
    shared_wall_frac = DataUtil.postfix("SHARED_WALL_FRAC")
    geometry_types = DataUtil.postfix("GEOMETRY_TYPES")
    rsu = DataUtil.postfix("RSU")
    aspect_and_height = DataUtil.postfix("ASPECT_AND_HEIGHT")

    # Output table
    build_indic = DataUtil.postfix("BUILD_INDIC", "")

    
    # Identify shared walls
    cursor.execute(
        """ 
        {0};{1};   
        """.format( DataUtil.createIndex(tableName=buildings, 
                                         fieldName=ID_FIELD_BUILD,
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=buildings, 
                                         fieldName=GEOM_FIELD,
                                         isSpatial=True)))
    cursor.execute(
    f"""
    DROP TABLE IF EXISTS {shared_wall};
    CREATE TABLE {shared_wall}
        AS SELECT 
            ST_INTERSECTION(a.{GEOM_FIELD},
                            b.{GEOM_FIELD}) AS {GEOM_FIELD},
            a.{ID_FIELD_BUILD}, 
            ST_PERIMETER(a.{GEOM_FIELD}) + 
            ST_PERIMETER(ST_HOLES(a.{GEOM_FIELD})) AS PERIMETER
        FROM {buildings} a, {buildings} b 
        WHERE a.{GEOM_FIELD} && b.{GEOM_FIELD} 
            AND ST_INTERSECTS(a.{GEOM_FIELD}, b.{GEOM_FIELD}) 
            AND a.{ID_FIELD_BUILD} <> b.{ID_FIELD_BUILD}
    """)
    
    # Calculate the ratio of linear of wall shared with other buildings
    cursor.execute(
        """ {0};   
        """.format( DataUtil.createIndex(tableName=shared_wall, 
                                         fieldName=ID_FIELD_BUILD,
                                         isSpatial=False)))
    cursor.execute(
    f"""
    DROP TABLE IF EXISTS {shared_wall_frac};
    CREATE TABLE {shared_wall_frac}
        AS SELECT   SUM(st_length({GEOM_FIELD})/perimeter) AS SHARED_WALL_FRAC,
                    {ID_FIELD_BUILD} FROM {shared_wall}
        GROUP BY {ID_FIELD_BUILD};
    """)
        
    # Identify the geometry type
    cursor.execute(
        """ 
        {0};{1};   
        """.format( DataUtil.createIndex(tableName=buildings, 
                                         fieldName=ID_FIELD_BUILD,
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=shared_wall_frac, 
                                         fieldName=ID_FIELD_BUILD,
                                         isSpatial=False)))
    casewhen_sql = [f"""WHEN a.SHARED_WALL_FRAC >= {BUILDING_GEOMETRY_CLASSES.loc[i, "lower_limit_shared_wall"]}
                             AND a.SHARED_WALL_FRAC < {BUILDING_GEOMETRY_CLASSES.loc[i, "upper_limit_shared_wall"]}
                         THEN {i}""" for i in BUILDING_GEOMETRY_CLASSES.index]
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS {geometry_types};
        CREATE TABLE {geometry_types}
            AS SELECT   COALESCE(CASE {" ".join(casewhen_sql)} END, 4) AS {BUILD_GEOM_TYPE},
                        b.{ID_FIELD_BUILD},
                        b.{GEOM_FIELD}
            FROM {shared_wall_frac} AS a RIGHT JOIN {buildings} AS b
            ON a.{ID_FIELD_BUILD} = b.{ID_FIELD_BUILD}
        """)
        
    # Calculate the orientation of each geometry
    geometry_orientation = building_orientation(cursor = cursor,
                                                buildings = geometry_types, 
                                                shared_wall = shared_wall)
        
    # Calculate the aspect ratio in a 'BLOCK_BUFFER_INDIC' m buffer around each block
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS {rsu};
        CREATE TABLE {rsu}
            AS SELECT   {ID_FIELD_BLOCK} AS ID, 
                        {ID_FIELD_BLOCK} AS {ID_UPSTREAM}, 
                        ST_BUFFER({GEOM_FIELD}, {BLOCK_BUFFER_INDIC}, 1) AS {GEOM_FIELD}
            FROM {blocks}
        """)
    block_aspect_ratio = generic_facade_indicators(cursor = cursor,
                                                   buildings = buildings, 
                                                   rsu = rsu, 
                                                   indic = ASPECT_RATIO,
                                                   wind_dir = "")
    
    # Gather aspect ratio with building id
    cursor.execute(
        """ 
        {0};{1};   
        """.format( DataUtil.createIndex(tableName=buildings, 
                                         fieldName=ID_FIELD_BLOCK,
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=block_aspect_ratio, 
                                         fieldName="ID",
                                         isSpatial=False)))   
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS {aspect_and_height};
        CREATE TABLE {aspect_and_height}
            AS SELECT a.*,
                      b.{ASPECT_RATIO}
            FROM {buildings} AS a LEFT JOIN {block_aspect_ratio} AS b
            ON a.{ID_FIELD_BLOCK} = b.ID
        """)
    

    tablesAndId = {aspect_and_height : [ID_FIELD_BUILD],
                   geometry_orientation : [ID_FIELD_BUILD]}
    build_indic = joinTables(cursor = cursor, 
                             tablesAndId = tablesAndId,
                             outputTableName = prefix + OUTPUT_BUILD_INDIC)

    # Delete temporary tables if not debug mode              
    if not DEBUG:
        # The temporary tables are deleted
        cursor.execute(
            f"""
            DROP TABLE IF EXISTS {shared_wall}, {shared_wall_frac}, 
            {geometry_types}, {rsu}, {geometry_orientation},
            {block_aspect_ratio}, {aspect_and_height}
            """)

    return build_indic

def building_orientation(cursor, buildings, shared_wall):
    """ Calculates buiding orientation (South, West, North, East)

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

            cursor: conn.cursor
                A cursor object, used to perform spatial SQL queries
            buildings: String
                Name of the table where buildings containing geometry type are saved
            shared_wall: String
                Name of the table where shared walls between buildings are saved
        
            
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            geometry_orientation: String
                Name of the table containing the building geometries
                and the orientation"""

    # Temporary table names
    all_facade_linear = DataUtil.postfix("ALL_FACADE_LINEAR")
    sum_facade_linear = DataUtil.postfix("SUM_FACADE_LINEAR")
    all_orientations_for_all = DataUtil.postfix("ALL_ORIENTATIONS_FOR_ALL")
    orientation_ranking = DataUtil.postfix("ORIENTATION_RANKING")
    
    # Output table
    geometry_orientation = DataUtil.postfix("GEOMETRY_ORIENTATION", "")

    # Calculates the linear of facade being shared and not being shared and
    # the corresponding facade orientation (4 different possibles)
    casewhen_sql = [f"""WHEN ST_AZIMUTH(ST_STARTPOINT({GEOM_FIELD}), ST_ENDPOINT({GEOM_FIELD})) >= {ORIENTATIONS.loc[i, "lower_limit"]}
                             {ORIENTATIONS.loc[i, "operation"]}
                             ST_AZIMUTH(ST_STARTPOINT({GEOM_FIELD}), ST_ENDPOINT({GEOM_FIELD})) < {ORIENTATIONS.loc[i, "upper_limit"]}
                         THEN {i}""" for i in ORIENTATIONS.index]
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS {all_facade_linear};
        CREATE TABLE {all_facade_linear}
            AS SELECT   {ID_FIELD_BUILD},
                        CASE {" ".join(casewhen_sql)} END AS ORIENTATION,
                        ST_LENGTH({GEOM_FIELD}) AS LINEAR,
                        {BUILD_GEOM_TYPE}
            FROM ST_EXPLODE('(SELECT    {ID_FIELD_BUILD},
                                        {BUILD_GEOM_TYPE},
                                        ST_TOMULTISEGMENTS({GEOM_FIELD}) AS {GEOM_FIELD}
                            FROM {buildings})')
            UNION ALL
            SELECT   {ID_FIELD_BUILD},
                        CASE {" ".join(casewhen_sql)} END AS ORIENTATION,
                        -ST_LENGTH({GEOM_FIELD}) AS LINEAR,
                        null AS {BUILD_GEOM_TYPE}
            FROM ST_EXPLODE('(SELECT    {ID_FIELD_BUILD},
                                        ST_TOMULTISEGMENTS({GEOM_FIELD}) AS {GEOM_FIELD}
                            FROM {shared_wall})')
        """)

        
    # By default, set facade length to 0 m to each orientation
    cursor.execute(f"SELECT {ID_FIELD_BUILD}, {BUILD_GEOM_TYPE} FROM {buildings}")
    build_info = cursor.fetchall()
    sql_values = [f"({i[0]}, {i[1]}, {j}, 0)" 
                  for i in build_info for j in ORIENTATIONS.index]
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS {all_orientations_for_all};
        CREATE TABLE {all_orientations_for_all}({ID_FIELD_BUILD} INTEGER,
                                                {BUILD_GEOM_TYPE} INTEGER,
                                                ORIENTATION INTEGER,
                                                LINEAR DOUBLE)
            AS VALUES {", ".join(sql_values)};
        """)    
    
    # Calculates the total length by building by orientation
    cursor.execute(
        """ 
        {0};{1};   
        """.format( DataUtil.createIndex(tableName=all_facade_linear, 
                                         fieldName=ID_FIELD_BUILD,
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=all_facade_linear, 
                                         fieldName="ORIENTATION",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=all_orientations_for_all, 
                                         fieldName=ID_FIELD_BUILD,
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=all_orientations_for_all, 
                                         fieldName="ORIENTATION",
                                         isSpatial=False)))
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS {sum_facade_linear};
        CREATE TABLE {sum_facade_linear}
            AS SELECT   b.{ID_FIELD_BUILD},
                        SUM(a.LINEAR) AS LINEAR,
                        b.ORIENTATION,
                        MAX(b.{BUILD_GEOM_TYPE}) AS {BUILD_GEOM_TYPE}
            FROM {all_facade_linear} AS a RIGHT JOIN {all_orientations_for_all} AS b
            ON a.{ID_FIELD_BUILD} = b.{ID_FIELD_BUILD} AND a.ORIENTATION = b.ORIENTATION
            GROUP BY b.{ID_FIELD_BUILD}, b.ORIENTATION
        """)

        
    # Identify the 3 main orientations of the building
    cursor.execute(
        """ 
        {0}
        """.format( DataUtil.createIndex(tableName=sum_facade_linear, 
                                         fieldName=ID_FIELD_BUILD,
                                         isSpatial=False)))
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS {orientation_ranking};
        CREATE TABLE {orientation_ranking}
            AS  SELECT  {ID_FIELD_BUILD}, 
                        CAST(ARRAY_AGG(ORIENTATION ORDER BY LINEAR DESC)[1] AS INTEGER) AS ORIENTATION1, 
                        CAST(ARRAY_AGG(ORIENTATION ORDER BY LINEAR DESC)[2] AS INTEGER) AS ORIENTATION2,
                        CAST(ARRAY_AGG(ORIENTATION ORDER BY LINEAR DESC)[3] AS INTEGER) AS ORIENTATION3,
                        MAX({BUILD_GEOM_TYPE}) AS {BUILD_GEOM_TYPE}
            FROM {sum_facade_linear}
            GROUP BY {ID_FIELD_BUILD}
        """)
    
    # Identify the orientation of the "original North on Cerema figure"
    # for each geometry type (1 -> North is North, 2 -> North is East, etc.)
    cursor.execute(
        """ 
        {0}{1}{2}
        """.format( DataUtil.createIndex(tableName=orientation_ranking, 
                                         fieldName="ORIENTATION1",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=orientation_ranking, 
                                         fieldName="ORIENTATION2",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=orientation_ranking, 
                                         fieldName="ORIENTATION3",
                                         isSpatial=False),
                    DataUtil.createIndex(tableName=orientation_ranking, 
                                         fieldName=BUILD_GEOM_TYPE,
                                         isSpatial=False)))
    cursor.execute(
        f"""
        DROP TABLE IF EXISTS {geometry_orientation};
        CREATE TABLE {geometry_orientation}
            AS  SELECT  {ID_FIELD_BUILD}, 
                        CASE    WHEN    ORIENTATION1 + ORIENTATION2 = 4
                                        OR ORIENTATION1 + ORIENTATION2 = 6
                                THEN 1
                                ELSE 2
                        END AS {BUILD_GEOM_TYPE},
                        CASE    WHEN    ORIENTATION1 + ORIENTATION2 = 4
                                THEN    2
                                WHEN    ORIENTATION1 + ORIENTATION2 = 6
                                THEN    1
                                WHEN    ORIENTATION1 + ORIENTATION2 = 3
                                THEN    3
                                WHEN    ORIENTATION1 + ORIENTATION2 = 5
                                THEN    CASE    WHEN (ORIENTATION1 = 2 OR ORIENTATION2 = 2) 
                                                THEN    4
                                                WHEN (ORIENTATION1 = 1 OR ORIENTATION2 = 1) 
                                                THEN    2
                                        END
                                WHEN    ORIENTATION1 + ORIENTATION2 = 7
                                THEN    1
                        END AS {BUILD_NORTH_ORIENTATION}
            FROM {orientation_ranking}
            WHERE {BUILD_GEOM_TYPE} = 1 OR {BUILD_GEOM_TYPE} = 2
            UNION ALL
            SELECT  {ID_FIELD_BUILD}, 
                    {BUILD_GEOM_TYPE},
                    CASE    WHEN    ORIENTATION1 + ORIENTATION2 + ORIENTATION3 = 6
                            THEN    4
                            WHEN    ORIENTATION1 + ORIENTATION2 + ORIENTATION3 = 7
                            THEN    3
                            WHEN    ORIENTATION1 + ORIENTATION2 + ORIENTATION3 = 8
                            THEN    2
                            WHEN    ORIENTATION1 + ORIENTATION2 + ORIENTATION3 = 9
                            THEN    1
                    END AS {BUILD_NORTH_ORIENTATION}
            FROM {orientation_ranking}
            WHERE {BUILD_GEOM_TYPE} = 3
            UNION ALL
            SELECT  {ID_FIELD_BUILD}, 
                    {BUILD_GEOM_TYPE},
                    1 AS {BUILD_NORTH_ORIENTATION}
            FROM {orientation_ranking}
            WHERE {BUILD_GEOM_TYPE} = 4          
        """)
    
    return geometry_orientation
    
    # Delete temporary tables if not debug mode              
    if not DEBUG:
        # The temporary tables are deleted
        cursor.execute(
            f"""
            DROP TABLE IF EXISTS {all_facade_linear}, {sum_facade_linear},
                    {all_orientations_for_all}, {orientation_ranking}
            """)
            
def joinTables(cursor, tablesAndId, outputTableName):
    """ Join many tables in one based on one or several ids

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

            cursor: conn.cursor
                A cursor object, used to perform spatial SQL queries
            tablesAndId: dictionary
                Table name as key and list of indexes used for the join as value
            postfix
        
            
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            joinedTable: String
                Name of the table containing all joined tables"""
    
    # Create the select and join SQL query needed for the table join
    tables = list(tablesAndId.keys())
    letters = list(string.ascii_lowercase)
    letters.extend([i+b for i in letters for b in letters])
    list_col = {}
    sql_select = "a.*"
    sql_leftjoin = f"{tables[0]} AS a"
    for i, t in enumerate(tables):
        cursor.execute(
            """{0}
            """.format(" ".join([DataUtil.createIndex(  tableName=t, 
                                                        fieldName=ind,
                                                        isSpatial=False)
                                    for ind in tablesAndId[t]])))
        list_col[t] = DataUtil.getColumns(cursor = cursor, tableName = t)
        if list_col[t].count(GEOM_FIELD) > 0:
            list_col[t].remove(GEOM_FIELD)
        for ind in tablesAndId[t]:
            list_col[t].remove(ind)
        if i > 0:
            sql_select += ","
            sql_select += ",".join([f"{letters[i]}.{ind}" for ind in list_col[t]])
            sql_leftjoin += f" LEFT JOIN {t} AS {letters[i]} ON " 
            sql_leftjoin += " AND ".join([f"a.{tablesAndId[tables[0]][j]} = {letters[i]}.{ind}" 
                                          for j, ind in enumerate(tablesAndId[t])])
    
    # Execute the table join
    cursor.execute(
        f""" 
        DROP TABLE IF EXISTS {outputTableName};
        CREATE TABLE {outputTableName}
            AS SELECT   {sql_select}
            FROM {sql_leftjoin}
        """)
    # cursor.execute(
    #     f""" 
    #     DROP TABLE IF EXISTS {city_all_indic};
    #     CREATE TABLE {city_all_indic}
    #         AS SELECT   a.*,
    #                     {", b.".join(list_col[rect_city_indic2])},
    #                     {", c.".join(list_col[rect_city_indic3])},
    #                     {", d.".join(list_col[rect_city_indic4])}
    #         FROM {rect_city_indic1} AS a
    #              LEFT JOIN {rect_city_indic2} AS b ON a.ID = b.ID AND a.{ID_UPSTREAM} = b.{ID_UPSTREAM}
    #              LEFT JOIN {rect_city_indic3} AS c ON a.ID = c.ID AND a.{ID_UPSTREAM} = c.{ID_UPSTREAM}
    #              LEFT JOIN {rect_city_indic4} AS d ON a.ID = d.ID AND a.{ID_UPSTREAM} = d.{ID_UPSTREAM}
    #     """)
                
    return outputTableName