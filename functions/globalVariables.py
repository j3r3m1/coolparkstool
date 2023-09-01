#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 13 13:18:02 2023

@author: Jérémy Bernard, chercheur associé au Lab-STICC
"""
import pandas as pd
import numpy as np
import tempfile
import os
from pathlib import Path

DEFAULT_PREFIX = "default"

OUTPUT_RASTER_EXTENSION = ".Gtiff"
DELETE_OUTPUT_IF_EXISTS = True

# Output folder names
OUTPUT_PREPROCESSOR_FOLDER = "preprocessor_outputs"
OUTPUT_PROCESSOR_FOLDER = "processor_outputs"

# File base names
OUTPUT_T = "OUTPUT_T"
OUTPUT_DT = "OUTPUT_deltaT"
WIND_DIR_RATE = "WIND_DIR"
BUILD_INDEP_VAR = "BUILD_INDEP_VAR"

# Informations to set the DB used for geographical calculations
INSTANCE_NAME = "coolparks"
INSTANCE_ID ="sa"
INSTANCE_PASS = "sa"
NEW_DB = True
ADD_SUFFIX_NAME = True

# Where to save the current JAVA path
JAVA_PATH_FILENAME = "JavaPath.csv"

# Define temporary directory
TEMPO_DIRECTORY = tempfile.gettempdir()


# Superimposition threshold accepted in park canopy and park ground data
SUPERIMP_THRESH = 0.

# Merge building geometries as block when closer than 'GEOMETRY_MERGE_TOLERANCE'
GEOMETRY_MERGE_TOLERANCE = 0.05
GEOMETRY_SIMPLIFICATION_DISTANCE = 0.25

# Consider facades as touching each other within a snap tolerance
GEOMETRY_SNAP_TOLERANCE = 0.05

# Ground park data should almost filled the park within its boundaries
GROUND_TO_PARK_RATIO = 0.95

# Number of cross wind cells within the park
N_CROSS_WIND_PARK = 6

# Number of cells outside the park (left + right)
N_CROSS_WIND_OUTSIDE = 12

# Number of along wind cells in a space including the park and also the city
N_ALONG_WIND_PARK = 15  # equivalent to 10 cells before the park, 10 within and 10 after

# min cell size (m)
MIN_CELL_SIZE = 20

# Cross wind lines distance
CROSSWIND_LINE_DIST = 8

# Number of wind directions
N_DIRECTIONS = 8

# Default values for distance to park entrance and outputs
DEFAULT_D_PARK_INPUT = -999
DEFAULT_D_PARK_OUTPUT = -999
DEFAULT_D_PARK = -999
DEFAULT_CORRIDOR_AREA = -999

# Table names
BUILDINGS_TAB = "BUILDINGS"
PARK_BOUNDARIES_TAB = "PARK_BOUNDARIES"
PARK_CANOPY = "PARK_CANOPY"
PARK_GROUND = "PARK_GROUND"
BLOCK_TAB = "BLOCKS"
OUTPUT_CITY_INDIC = "CITY_INDIC"
OUTPUT_PARK_INDIC = "PARK_INDIC"
OUTPUT_BUILD_INDIC = "BUILD_INDIC"
OUTPUT_GRID = "OUTPUT_GRID"

# Field names
GEOM_FIELD = "THE_GEOM"
HEIGHT_FIELD = "HEIGHT_ROOF"
TYPE = "TYPE"
ID_FIELD_BUILD = "ID_BUILD"
ID_FIELD_BLOCK = "ID_BLOCK"
ID_UPSTREAM = "ID_UPSTREAM"
ID_STREET = "ID_STREET"
COMBI_FIELD_BASE = "FRAC_{0}_COMBI"
BLOCK_NB_DENSITY = "BLOCK_NB_DENSITY"
BLOCK_SURF_FRACTION = "BLOCK_SURF_FRACTION"
MEAN_BUILD_HEIGHT = "MEAN_BUILD_HEIGHT"
GEOM_MEAN_BUILD_HEIGHT = "GEOM_MEAN_BUILD_HEIGHT"
STREET_WIDTH = "STREET_WIDTH"
NB_STREET_DENSITY = "NB_STREET_DENSITY"
OPENING_FRACTION = "OPENING_FRACTION"
FREE_FACADE_FRACTION = "FREE_FACADE_FRACTION"
ASPECT_RATIO = "ASPECT_RATIO"
BUILD_GEOM_TYPE = "BUILD_GEOM_TYPE"
CORRIDOR_PARK_FRAC = "CORRIDOR_PARK_FRAC"
D_PARK_INPUT = "D_INPUT"
D_PARK_OUTPUT = "D_OUTPUT"
D_PARK = "D_PARK"
BUILD_NORTH_ORIENTATION = "NORTH_ORIENTATION"
BUILD_SIZE_CLASS = "BUILD_SIZE_CLASS"
BUILDING_AGE = "BUILDING_AGE"
BUILDING_RENOVATION = "BUILDING_RENOVATION"
BUILDING_CLASS = "BUILDING_CLASS"
BUILDING_WWR = "BUILDING_WWR"
BUILDING_AMPLIF_FACTOR = "AMPLIF_FACTOR"
BUILDING_RROOF = "RROOF"
BUILDING_RWALL = "RWALL"
BUILDING_UWIN = "UWIN"
BUILDING_RSLAB = "RSLAB"
BUILDING_INFILTRATION_RATE = "INFILTRATION_RATE"
BUILDING_NATURAL_VENT_RATE = "NATURAL_VENT_RATE"
BUILDING_MECHANICAL_VENT_RATE = "MECHANICAL_VENT_RATE"

DELTA_T = "DELTA_T"
ENERGY_IMPACT_ABS = "ENERGY_IMPACT_ABS"
ENERGY_IMPACT_REL = "ENERGY_IMPACT_REL"
THERM_COMFORT_IMPACT_ABS = "THERM_COMFORT_IMPACT_ABS"
THERM_COMFORT_IMPACT_REL = "THERM_COMFORT_IMPACT_REL"

# DB name
DB_NAME = "coolparks"

DEBUG = True

# Series of canopy and ground park types and combinations of each
S_GROUND = pd.Series({1: "sol nu",
                      2: "eau", 
                      3: "herbace", 
                      4: "impermeable"})
S_CANOPY = pd.Series({10: "arbre isole",
                      20: "boise", 
                      30: "boise dense"})
S_GROUND_CANOPY = S_GROUND.append(pd.Series({i+j: S_GROUND[i] + " / " + S_CANOPY[j]
                             for i in S_GROUND.index for j in S_CANOPY.index}))

# Combination of ground / canopy that cannot exist or need to be replace
REPLACE_COMBI = pd.Series({2: 3, 12: 13, 22: 23, 32: 33})

# Default combination in case there is not 100% values in a corridor
DEFAULT_COMBI = 1 


###############################################################################
#################### BUILDING RELATED INFORMATIONS ############################
###############################################################################
# Building size classes
BUILDING_SIZE_CLASSES = pd.DataFrame({"name" : ["Maison Individuelle", 
                                                "Petit Logement Collectif", 
                                                "Grand Logement Collectif"],
                                      "low_limit" : [3, 6, 9]},
                                     index = [1,2,3])

# Building geometry classes
BUILDING_GEOMETRY_CLASSES = pd.DataFrame({"name" : ["G12",
                                                    "G3",
                                                    "G4"],
                                          "lower_limit_shared_wall" : [0.3, 0.05, 0.],
                                          "upper_limit_shared_wall" : [1., 0.3, 0.05]},
                                         index = [12,3,4])

ORIENTATIONS = pd.DataFrame({"name" : ["North",
                                       "East",
                                       "South",
                                       "West"],
                             "lower_limit" : [5*np.pi/4, 7*np.pi/4, np.pi/4, 3*np.pi/4],
                             "upper_limit" : [7*np.pi/4, np.pi/4, 3*np.pi/4, 5*np.pi/4],
                             "operation" : ["AND", "OR", "AND", "AND"]},
                                         index = [1,2,3,4])

# Buffer size used to calculate aspect ratio around each block
BLOCK_BUFFER_INDIC = 50

# Default values for building characteristics
BUILDING_DEFAULT_AGE = 1970
BUILDING_DEFAULT_RENOVATION = False
BUILDING_DEFAULT_HEIGHT = 3
BUILDING_DEFAULT_WINDOWS_WALL_RATIO = 0.25

# Building properties per building age
BUILDING_PROPERTIES = pd.DataFrame({"Name": ["Construit avant 1974 et non rénové thermiquement",
                                             "Construit après 1974 ou rénové thermiquement"],
                                    "period_start" : [0, 1974],
                                    "period_end" : [1974, 2300],
                                    "Rroof" : [1.04, 1.48],
                                    "Rwall": [0.58, 1.20],
                                    "Uwin" : [3.1, 1.7],
                                    "Rslab" : [0.24, 0.37],
                                    "Infiltration_rate" : [0.75, 0.53],
                                    "Natural_vent_rate" : [1.3, 1.3],
                                    "Mechanical_vent_rate" : [0.3, 0.3]},
                                    index = [1, 2])

# Regression coefficient and variables correspondance
coef_var_correspondance = \
    pd.Series([ASPECT_RATIO,
               BUILDING_WWR,
               BUILDING_AMPLIF_FACTOR,
               HEIGHT_FIELD,
               BUILDING_RROOF, 
               BUILDING_RWALL, 
               BUILDING_UWIN, 
               BUILDING_RSLAB, 
               BUILDING_INFILTRATION_RATE, 
               BUILDING_NATURAL_VENT_RATE,
               BUILDING_MECHANICAL_VENT_RATE], 
              index = np.arange(1, 12))
    
# Basic value used as reference for the calculation of the amplification factor
# used as input in the building energy model to consider the cooling effect of the park
BASIC_COOLING = -0.11

# Dates used for calculation
START_DATE = "01/06"
END_DATE = "01/09"

# Generic names for meteorological variables
WDIR = "wdir"
WSPEED = "wspeed"
T_AIR = "Ta" 
RH = "RH"
P_ATMO = "Patmo"
DPV = "DPV"

# length of the edge of the pattern ("motif") used for creating the empirical models
PATTERN_SIZE = 10

# Time considered for the day and for the night
DAY_TIME = 12
NIGHT_TIME = 23

# Max distance for which the cooling is considered
MAX_DIST = {DAY_TIME: 50, NIGHT_TIME: 300}

# Extreme values of the factors used for the cooling estimation
COOLING_FACTORS = {12 : pd.DataFrame({"dpv" : [11.8559505666779, 28.670673995194],
                                      "ws" : [1.6, 4.6]},
                                     index = ["min", "max"]),
                   23 : pd.DataFrame({"dpv" : [2.18714242784999, 10.5792601906677],
                                      "ws" : [1.6, 4.6]},
                                     index = ["min", "max"])}

# Empirical model coefficients for park cooling
COOLING_CREATION_PATH = os.path.join(Path(os.path.dirname(os.path.abspath(__file__))).parents[0], "Resources", "empirical_coefficients", "cooling_creation")
COEF_COOLING_RATE = {DAY_TIME: pd.read_csv(COOLING_CREATION_PATH + os.sep + f"cooling_rate_{DAY_TIME}.csv",
                                           header = 0,
                                           index_col = 0),
                     NIGHT_TIME : pd.read_csv(COOLING_CREATION_PATH + os.sep + f"cooling_rate_{NIGHT_TIME}.csv",
                                              header = 0,
                                              index_col = 0)}
COEF_SURF_TEMP = {DAY_TIME: pd.read_csv(COOLING_CREATION_PATH + os.sep + f"surface_temp_{DAY_TIME}.csv",
                                        header = 0,
                                        index_col = 0),
                  NIGHT_TIME : pd.read_csv(COOLING_CREATION_PATH + os.sep + f"surface_temp_{NIGHT_TIME}.csv",
                                           header = 0,
                                           index_col = 0)}

# Empirical model coefficients for park cool air diffusion
WIND_FACTOR_NAME = "wind_factor"
CONSTANT_NAME = "constant"
COOLING_TRANSPORT_PATH = os.path.join(Path(os.path.dirname(os.path.abspath(__file__))).parents[0], "Resources", "empirical_coefficients", "cooled_air_transport")
COEF_DT_MORPHO = {DAY_TIME: pd.read_csv(COOLING_TRANSPORT_PATH + os.sep + f"dt_morpho_{DAY_TIME}.csv",
                                        header = 0,
                                        index_col = 0),
                  NIGHT_TIME : pd.read_csv(COOLING_TRANSPORT_PATH + os.sep + f"dt_morpho_{NIGHT_TIME}.csv",
                                           header = 0,
                                           index_col = 0)}
COEF_D_MORPHO = {DAY_TIME: pd.read_csv(COOLING_TRANSPORT_PATH + os.sep + f"d_morpho_{DAY_TIME}.csv",
                                       header = 0,
                                       index_col = 0),
                 NIGHT_TIME : pd.read_csv(COOLING_TRANSPORT_PATH + os.sep + f"d_morpho_{NIGHT_TIME}.csv",
                                          header = 0,
                                          index_col = 0)}

# Maximum and minimum values achievable for the spatial indicators (due to training data calibration)
TRAINING_TRANSPORT_PATH = os.path.join(Path(os.path.dirname(os.path.abspath(__file__))).parents[0], "Resources", "cooling_transport_results")
TRANSPORT_MAX_VAL = pd.read_csv(TRAINING_TRANSPORT_PATH + os.sep + f"training_data_{DAY_TIME}h.csv",
                                header = 0,
                                index_col = 0).max()
TRANSPORT_MIN_VAL = pd.read_csv(TRAINING_TRANSPORT_PATH + os.sep + f"training_data_{DAY_TIME}h.csv",
                                header = 0,
                                index_col = 0).min()

# Empirical model coefficients for building energy and building thermal comfort
BUILD_ENERGY_PATH = os.path.join(Path(os.path.dirname(os.path.abspath(__file__))).parents[0], "Resources", "empirical_coefficients", "building_energy")
BUILD_COMFORT_PATH = os.path.join(Path(os.path.dirname(os.path.abspath(__file__))).parents[0], "Resources", "empirical_coefficients", "building_comfort")


#############################################################################
#################### POSTPROCESSING INFORMATIONS ############################
#############################################################################
LIST_OF_CHANGES = pd.Series(['park', 'city', 'weather'])