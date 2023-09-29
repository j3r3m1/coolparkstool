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

DEFAULT_SCENARIO = "Reference_scenario"
DEFAULT_WEATHER = "Reference_weather"

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
ADD_SUFFIX_NAME = False

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

# WARNING: IDEALLY, TRY TO HAVE THE TWO FOLLOWING VARIABLES AS MULTIPLES OF 3
# Number of cross wind cells in a space including the park and also the city in its surrounding
N_CROSS_WIND_PARK = 30 # equivalent to 10 cells to the left of the park, 10 within and 10 on the right
# Number of along wind cells in a space including the park and also the city
N_ALONG_WIND_PARK = 30  # equivalent to 10 cells before the park, 10 within and 10 after

# min cell size (m)
MIN_CELL_SIZE = 20

# Number of cells in the output raster
NB_OUTPUT_CELL = 16 * (N_CROSS_WIND_PARK) * N_ALONG_WIND_PARK

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
FLOOR_AREA = "FLOOR_AREA"
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
BUILDING_UROOF = "UROOF"
BUILDING_UWALL = "UWALL"
BUILDING_UWIN = "UWIN"
BUILDING_USLAB = "USLAB"
BUILDING_INFILTRATION_RATE = "INFILTRATION_RATE"
BUILDING_NATURAL_VENT_RATE = "NATURAL_VENT_RATE"
BUILDING_MECHANICAL_VENT_RATE = "MECHANICAL_VENT_RATE"
BUILDING_SHUTTER = "SHUTTER"

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
S_GROUND_CANOPY = pd.concat([S_GROUND, pd.Series({i+j: S_GROUND[i] + " / " + S_CANOPY[j]
                             for i in S_GROUND.index for j in S_CANOPY.index})])

# Combination of ground / canopy that cannot exist or need to be replace
REPLACE_COMBI = pd.Series({2: 3, 12: 13, 22: 23, 32: 33})

# Default combination in case there is not 100% values in a corridor
DEFAULT_COMBI = 1 


###############################################################################
#################### BUILDING RELATED INFORMATIONS ############################
###############################################################################
# Building size classes
BUILDING_SIZE_CLASSES = pd.DataFrame({"name" : ["MI", 
                                                "PLC", 
                                                "GLC"],
                                      "low_limit" : [0, 6, 9]},
                                     index = [1,2,3])

# Building geometry classes
BUILDING_GEOMETRY_CLASSES = pd.DataFrame({"name" : ["G1",
                                                    "G2",
                                                    "G3",
                                                    "G4"],
                                          "lower_limit_shared_wall" : [0.3, 0.3, 0.05, 0.],
                                          "upper_limit_shared_wall" : [1., 1., 0.3, 0.05]},
                                         index = [1,2,3,4])

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
BUILDING_DEFAULT_HEIGHT = 9
BUILDING_DEFAULT_WINDOWS_WALL_RATIO = 0.2
BUILDING_DEFAULT_SHUTTER = 1
BUILDING_DEFAULT_NAT_VENTIL = 0.6
BUILDING_DEFAULT_FLOOR_HEIGHT = 3

# Building properties per building age and building size class (cf. index of BUILDING_SIZE_CLASS)
BUILDING_PROPERTIES = {1: pd.DataFrame({"Name": ["Construit avant 1915",
                                                 "Construit entre 1915 et 1948",
                                                 "Construit entre 1948 et 1968",
                                                 "Construit entre 1968 et 1975",
                                                 "Construit entre 1975 et 1982",
                                                 "Construit entre 1982 et 1990",
                                                 "Construit entre 1990 et 2001",
                                                 "Construit entre 2001 et 2006",
                                                 "Construit entre 2006 et 2012",
                                                 "Construit après 2012"],
                                        "period_start" : [0, 1915, 1948, 1968, 1974,
                                                          1982, 1990, 2001, 2006, 2012],
                                        "period_end" : [1915, 1948, 1968, 1974, 1982, 
                                                        1990, 2001, 2006, 2012, 2300],
                                        BUILDING_UROOF : [.775,1.31,1.26,1.6,.43,.725,
                                                          .165,.19,.28,.135],
                                        BUILDING_UWALL: [.97,1.145,1.395,1.295,1.295,.33,
                                                         .275,.26,.25,.185],
                                        BUILDING_UWIN : [2.64,4.81,1.8,1.8,1.9,
                                                         1.8,1.4,1.3,1.3,1.1],
                                        BUILDING_USLAB : [1.89,.965,1.515,1.365,
                                                          1.305,.745,.3,.38,.185,.165],
                                        BUILDING_INFILTRATION_RATE : [3,3,3,3,2,2,1.5,1.5,1.3,.6],
                                        BUILDING_MECHANICAL_VENT_RATE : [0,0,.6,.6,.6,.6,.6,.6,.6,.6]},
                                        index = np.arange(1,11)),
                       2: pd.DataFrame({"Name": ["Construit avant 1915",
                                                 "Construit entre 1915 et 1948",
                                                 "Construit entre 1948 et 1968",
                                                 "Construit entre 1968 et 1975",
                                                 "Construit entre 1975 et 1982",
                                                 "Construit entre 1982 et 1990",
                                                 "Construit entre 1990 et 2001",
                                                 "Construit entre 2001 et 2006",
                                                 "Construit entre 2006 et 2012",
                                                 "Construit après 2012"],
                                        "period_start" : [0, 1915, 1948, 1968, 1974,
                                                          1982, 1990, 2001, 2006, 2012],
                                        "period_end" : [1915, 1948, 1968, 1974, 1982, 
                                                        1990, 2001, 2006, 2012, 2300],
                                        BUILDING_UROOF : [.775,1.26,1.26,.495,.295,
                                                          .425,.305,.255,.21,.19],
                                        BUILDING_UWALL: [.97,1.27,1.595,.485,.4,
                                                         .275,.26,.26,.245,.15],
                                        BUILDING_UWIN : [1.8,1.9,2.9,3.3,1.9,1.9,
                                                         1.8,1.3,1.3,1.1],
                                        BUILDING_USLAB : [1.89,1.515,1.565,1.365,.74,
                                                          .375,.36,.285,.24,.165],
                                        BUILDING_INFILTRATION_RATE : [3,3,3,3,2,2,1.7,1.7,1.7,1],
                                        BUILDING_MECHANICAL_VENT_RATE : [0,0,.6,.6,.6,.6,.6,.6,.6,.6]},
                                        index = np.arange(1,11)),
                       3: pd.DataFrame({"Name": ["Construit avant 1915",
                                                 "Construit entre 1915 et 1948",
                                                 "Construit entre 1948 et 1968",
                                                 "Construit entre 1968 et 1975",
                                                 "Construit entre 1975 et 1982",
                                                 "Construit entre 1982 et 1990",
                                                 "Construit entre 1990 et 2001",
                                                 "Construit entre 2001 et 2006",
                                                 "Construit entre 2006 et 2012",
                                                 "Construit après 2012"],
                                        "period_start" : [0, 1915, 1948, 1968, 1974,
                                                          1982, 1990, 2001, 2006, 2012],
                                        "period_end" : [1915, 1948, 1968, 1974, 1982, 
                                                        1990, 2001, 2006, 2012, 2300],
                                        BUILDING_UROOF : [1.25,1.715,1.715,1.715,
                                                          .495,.425,.33,.21,.255,.11],
                                        BUILDING_UWALL: [1.015,.945,1.635,.485,.49,
                                                         .485,1.595,.33,.225,.22],
                                        BUILDING_UWIN : [2.9,1.9,1.8,1.8,1.9,
                                                         1.8,2.15,1.3,1.3,1.1],
                                        BUILDING_USLAB : [1.565,1.515,1.365,1.365,
                                                          .335,.315,.315,.275,.2,.22],
                                        BUILDING_INFILTRATION_RATE : [3,3,3,3,2,2,1.7,1.7,1.7,1],
                                        BUILDING_MECHANICAL_VENT_RATE : [0,0,.6,.6,.6,.6,.6,.6,.6,.6]},
                                        index = np.arange(1,11))}

# Regression coefficient and variables correspondance
coef_var_correspondance = \
    pd.Series([BUILDING_WWR,
               ASPECT_RATIO,
               BUILDING_AMPLIF_FACTOR,
               BUILDING_SHUTTER,
               BUILDING_UROOF, 
               BUILDING_UWALL, 
               BUILDING_USLAB,
               BUILDING_UWIN,
               BUILDING_INFILTRATION_RATE, 
               BUILDING_NATURAL_VENT_RATE,
               BUILDING_MECHANICAL_VENT_RATE], 
              index = np.arange(1, 12))
    
# Basic value used as reference for the calculation of the amplification factor
# used as input in the building energy model to consider the cooling effect of the park
BASIC_COOLING = -0.11

# Dates used for calculation
START_DATE = "01/06"
END_DATE = "30/09"

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
TRANSPORT_EXTREMUM_VAL = pd.concat([pd.read_csv(TRAINING_TRANSPORT_PATH + os.sep + f"training_data_{DAY_TIME}h.csv",
                                                header = 0,
                                                index_col = 0).max().rename("MAX"),
                                    pd.read_csv(TRAINING_TRANSPORT_PATH + os.sep + f"training_data_{DAY_TIME}h.csv",
                                                header = 0,
                                                index_col = 0).min().rename("MIN")],
                                   axis = 1)

# Empirical model coefficients for building energy and building thermal comfort
BUILD_ENERGY_PATH = os.path.join(Path(os.path.dirname(os.path.abspath(__file__))).parents[0], "Resources", "empirical_coefficients", "building_energy")
BUILD_COMFORT_PATH = os.path.join(Path(os.path.dirname(os.path.abspath(__file__))).parents[0], "Resources", "empirical_coefficients", "building_comfort")
# Min and max achievable for building indicators value
BUILD_EXTREMUM_VAL = pd.DataFrame({BUILDING_WWR: [20, 80],
                                   ASPECT_RATIO: [0, 4],
                                   BUILDING_AMPLIF_FACTOR: [0, 40],
                                   BUILDING_SHUTTER: [0,1],
                                   BUILDING_UROOF: [0.1, 3],
                                   BUILDING_UWALL: [0.12, 2.6],
                                   BUILDING_USLAB: [0.12, 3.55],
                                   BUILDING_UWIN: [0.8, 4.8],
                                   BUILDING_INFILTRATION_RATE: [0.067, 1],
                                   BUILDING_NATURAL_VENT_RATE: [0.6, 2],
                                   BUILDING_MECHANICAL_VENT_RATE: [0, 0.6]},
                                  index = ["MIN", "MAX"]).transpose()

#############################################################################
#################### POSTPROCESSING INFORMATIONS ############################
#############################################################################
BUILDING_LEGEND = pd.Series({ENERGY_IMPACT_ABS: "Absolute energy impact (Alt - Ref) (kWh/m²/an)",
                             ENERGY_IMPACT_REL: "Relative energy impact ((Alt - Ref) / Ref without park) (%)",
                             THERM_COMFORT_IMPACT_ABS: "Absolute thermal discomfort impact (Alt - Ref) (°C.h discomfort)",
                             THERM_COMFORT_IMPACT_REL: "Relative thermal discomfort impact ((Alt - Ref) / Ref without park) (%)"})
LIST_OF_CHANGES = pd.Series(['park composition', 'urban morphology', 'weather', 'buildings characteristics'])
DEFAULT_OPACITY = 0.75
NB_ISOVALUES = 9
NB_SIGN_DIGITS = 2
REF_SCEN = "REFERENCE_SCENARIO"
ALT_SCEN = "ALTERNATIVE_REFERENCE_SCENARIO"
DIFF_SCEN = "DIFF_SCEN"
