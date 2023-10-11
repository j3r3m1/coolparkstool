# -*- coding: utf-8 -*-
from .globalVariables import *
import numpy as np
import pandas as pd
from osgeo import gdal, gdalconst
import itertools

from . import DataUtil
from . import loadData

import string

def dpv_calc(df):
    T_radian = df[T_AIR] * np.pi / 180.0 # convert to radian for trigonometric function 
    p_sat = 610.7 * (1 + 2 ** 0.5 * np.sin(T_radian / 3)) ** 8.827 # formula from Alt, cf. Guyot p.106
    DPV = (p_sat - df[RH] * p_sat / 100) / 100 # deficit de pression de vapeur en hectopascal
    
    return DPV

def air_cooling_and_diffusion(grid_sum_tair, grid_sum_deltatair, grid_ind_city_before, grid_ind_park, 
                              grid_ind_city_after, tair, ws_norm, dpv_norm, max_dist,
                              day_hour):
    """ For a given wind direction, calculates the park effect on the air 
    temperature within and outside the park boundaries. The corresponding
    grid is added to the temperature grid that has been summed previously for
    this given direction. 

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

			grid_sum_tair: pd.Series
				Sum of air temperature grid for a given wind direction  
			grid_sum_deltatair: pd.Series
				Sum of delta air temperature grid (with - without park) for a given wind direction  
            grid_ind_city_before: pd.DataFrame
                Grid containing indicators for a given wind direction for grid points before the park
            grid_ind_park: pd.DataFrame
                Grid containing indicators for a given wind direction for grid points within the park
            grid_ind_city_after: pd.DataFrame
                Grid containing indicators for a given wind direction for grid points after the park
            tair: float
                Air temperature at the given date and time
            ws_norm: float
                Wind speed at a given date and time normalized by the cooling factor
            dpv_norm: float
                Saturating pressure deficitat the given date and time normalized by the cooling factor 
            max_distance: float
                Maximum distance for which the cooling is considered
            day_hour: int
                Time of the day
        
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            grid_sum_tair: pd.Series
                Sum of the air temperature grid for this given wind direction
            grid_sum_deltatair: pd.Series
                Sum of the air temperature decrease generated by the park"""
    
    # Grid of air temperature and deltaT for this specific day (and time)
    grid_val_d = pd.Series(index = grid_sum_tair.index, dtype = float)
    grid_dval_d = pd.Series(index = grid_sum_tair.index, dtype = float)
    
    ####### EFFECT OF THE MORPHO ON THE TEMPERATURE BEFORE THE PARK ###########
    # Effect of the city morphology before the park on the air temperature
    grid_val_d.loc[grid_ind_city_before.index] = \
        tair + calc_morpho_t_effect(df_indic = grid_ind_city_before,
                                    ws_norm = ws_norm,
                                    day_hour = day_hour)
    grid_dval_d.loc[grid_ind_city_before.index] = 0
    
    ######## EFFECT OF THE MORPHO ON THE TEMPERATURE AFTER THE PARK #######
    # Calculate the air temperature of the city after the park without the cool air transport effect
    grid_val_d.loc[grid_ind_city_after.index] = \
        tair + calc_morpho_t_effect(df_indic = grid_ind_city_after,
                                    ws_norm = ws_norm,
                                    day_hour = day_hour)
    
    # Need to iterate to fill cells either since a corridor may have separated 
    # (by streets) patches of park
    for i in grid_ind_park["ID_UPSTREAM"].unique():
        ######## EFFECT OF THE PARK COMPOSITION ON THE TEMPERATURE IN THE PARK #######
        # Get the cells for the i st "row" of park
        grid_ind_park_upstream = grid_ind_park[grid_ind_park["ID_UPSTREAM"] == i]
        
        # Get the temperature of the last patch of city
        if i == 1:
            input_park_tair, input_park_dtair =\
                identify_previous_temp(grid_ind_current_upstream = grid_ind_park_upstream,
                                       grid_ind_previous = grid_ind_city_before,
                                       grid_tair = grid_val_d,
                                       grid_dtair = grid_dval_d)
        else:
            input_park_tair, input_park_dtair =\
                identify_previous_temp(grid_ind_current_upstream = grid_ind_park_upstream,
                                       grid_ind_previous = grid_ind_city_after,
                                       grid_tair = grid_val_d,
                                       grid_dtair = grid_dval_d)
    
        # Consider the park ground and canopy cover to update park air temperature
        grid_val_d.loc[grid_ind_park_upstream.index] = calc_park_effect(df_indic = grid_ind_park_upstream, 
                                                                        tair = input_park_tair,
                                                                        ws_norm = ws_norm, 
                                                                        dpv_norm = dpv_norm,
                                                                        day_hour = day_hour)
        # Calculate deltaT temperature
        grid_dval_d.loc[grid_ind_park_upstream.index] = input_park_dtair\
            .add(grid_val_d.loc[grid_ind_park_upstream.index]).subtract(input_park_tair)
        
        ######## EFFECT OF THE MORPHO ON THE TEMPERATURE AFTER THE PARK #######
        # Get the cells for the i+1 st "row" of city
        grid_ind_city_upstream = grid_ind_city_after[grid_ind_city_after["ID_UPSTREAM"] == i + 1]
        # Identify the air temperature at the output of the park
        input_city_tair, input_city_dtair = \
            identify_previous_temp(grid_ind_current_upstream = grid_ind_city_upstream,
                                   grid_ind_previous = grid_ind_park,
                                   grid_tair = grid_val_d,
                                   grid_dtair = grid_dval_d)

        ######## EFFECT OF THE MORPHO ON THE COOL AIR TRANSPORT AFTER THE PARK #######
        # Calculate the max distance of the cooling effect for each corridor
        d_morpho = calc_morpho_d_effect(df_indic = grid_ind_city_upstream,
                                        ws_norm = ws_norm,
                                        day_hour = day_hour)
        
        # Update the air temperature of the city after the park to consider the cool air transport effect
        coef_t_morpho = grid_ind_city_upstream.D_PARK.div(d_morpho)
        coef_t_park = (d_morpho.subtract(grid_ind_city_upstream.D_PARK)).div(d_morpho)
        coef_t_morpho[coef_t_morpho>1] = 1
        coef_t_park[coef_t_park<0] = 0
        grid_val_d.loc[grid_ind_city_upstream.index] = \
                   grid_val_d.loc[grid_ind_city_upstream.index] * coef_t_morpho\
                       + input_city_tair * coef_t_park
        # Calculate deltaT temperature
        grid_dval_d.loc[grid_ind_city_upstream.index] = input_city_dtair\
            .multiply(coef_t_park)
    
    # Add air temperature values to the existing ones
    grid_sum_tair += grid_val_d
    grid_sum_deltatair += grid_dval_d
    
    return grid_sum_tair, grid_sum_deltatair
    
def identify_point_position(grid_indic):
    """ For each wind direction, identify the index corresponding to the city before the park,
       to the index corresponding to the park and to the city after the park

		Parameters
		_ _ _ _ _ _ _ _ _ _ 
  
            grid_indic: dictionary of pd.DataFrame
                Dictionary containing for each wind direction the grid containing 
                park and city indicators
        
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            Dictionnary with for each wind direction, grid indic for city before the park
            Dictionnary with for each wind direction, grid indic for  the park
            Dictionnary with for each wind direction, grid indic for city after the park"""
    
    return  {d: grid_indic[d][grid_indic[d][[D_PARK_INPUT, D_PARK_OUTPUT, D_PARK]].isna().all(axis = 1)]
             for d in grid_indic.keys()},\
            {d: grid_indic[d].dropna(axis = 0, 
                                     how = "all",
                                     subset = [D_PARK_INPUT, D_PARK_OUTPUT])
             for d in grid_indic.keys()},\
            {d: grid_indic[d].dropna(axis = 0, 
                                     how = "all",
                                     subset = [D_PARK])
             for d in grid_indic.keys()}
            
    
def remove_null_upstream(grid_indic, start):
    """ Some of the upstream city zones did not intersect grid points, thus
    there are missing index (for example ID_UPSTREAM = 1 and then 3 for a column
    but no 2). Thus this function work reindexes the ID_UPSTREAM in a continuous way.
    
		Parameters
		_ _ _ _ _ _ _ _ _ _ 
  
            grid_indic: dictionary of pd.DataFrame
                Dictionary containing for each wind direction the grid containing 
                park and city indicators
            start: int
                Minimum possible ID_UPSTREAM value of the grid
        
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            Dictionnary with for each wind direction, the grid with a continuous ID_UPSTREAM index"""
   
    for d in grid_indic:
        # First set to 1 cells having ID_UPSTREAM = 0
        grid_indic[d].loc[grid_indic[d][grid_indic[d]["ID_UPSTREAM"] == 0].index,\
                          "ID_UPSTREAM"] = 1
        for col in grid_indic[d]["ID_COL"].unique():
            grid_ind_col = grid_indic[d][grid_indic[d]["ID_COL"] == col]
            id_valid = start - 1
            for id_up in np.arange(1, grid_ind_col["ID_UPSTREAM"].max() + 1):
                if not grid_ind_col[grid_ind_col["ID_UPSTREAM"] == id_up].empty:
                    if id_up > id_valid + 1:
                        grid_indic[d].loc[grid_ind_col[grid_ind_col["ID_UPSTREAM"] == id_up].index,\
                                          "ID_UPSTREAM"] = id_valid + 1
                    id_valid += 1
            
    return grid_indic
    
def calc_morpho_t_effect(df_indic, ws_norm, day_hour):
    """ Calculates the effect of the morphology on the air temperature observed in 
    a neighborhood.

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

			df_indic: pd.DataFrame
				Morphology indicator used for the regression
            ws_norm: float
                Wind speed at a given date and time normalized by the cooling factor
            day_hour: int
                Time of the day
        
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            dT: pd.Series
                Air temperature increase due to the urban morphology of each city corridor"""
    ws = denormalize_factor(value = ws_norm, 
                            value_min = COOLING_FACTORS[day_hour].loc["min","ws"], 
                            value_max = COOLING_FACTORS[day_hour].loc["max","ws"])
    
    # Limit the values of the geospatial indicators to the range used for this indicator during the training phase
    df_indic_lim = limit_geoindic(df_indic, TRANSPORT_EXTREMUM_VAL)
    
    # Test whether the formula type has a wind speed multiplicator
    if COEF_DT_MORPHO[day_hour].loc[WIND_FACTOR_NAME, "value"] == 0:
        geospatial_term = sum([df_indic_lim[i] * COEF_DT_MORPHO[day_hour].loc[i, "value"] \
                               for i in COEF_DT_MORPHO[day_hour].index[3:]])
    else:
        geospatial_term = ws * sum([df_indic_lim[i] * COEF_DT_MORPHO[day_hour].loc[i, "value"] \
                                    for i in COEF_DT_MORPHO[day_hour].index[3:]])
    dT = COEF_DT_MORPHO[day_hour].loc[CONSTANT_NAME, "value"] \
        + ws * COEF_DT_MORPHO[day_hour].loc[WSPEED, "value"] \
            + geospatial_term
    
    return dT

def calc_morpho_d_effect(df_indic, ws_norm, day_hour):
    """ Calculates the effect of the morphology on the distance where the cooling
    due to the park can be observed.

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

			df_indic: pd.DataFrame
				Morphology indicator used for the regression
            ws_norm: float
                Wind speed at a given date and time normalized by the cooling factor
            day_hour: int
                Time of the day
        
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            d: pd.Series
                For each city corridor, the distance up to which the cooling effect
                of the park is measurable"""
    ws = denormalize_factor(value = ws_norm, 
                            value_min = COOLING_FACTORS[day_hour].loc["min","ws"], 
                            value_max = COOLING_FACTORS[day_hour].loc["max","ws"])
    
    # Limit the values of the geospatial indicators to the range used for this indicator during the training phase
    df_indic_lim = limit_geoindic(df_indic, TRANSPORT_EXTREMUM_VAL)
    
    # Test whether the formula type has a wind speed multiplicator
    if COEF_D_MORPHO[day_hour].loc[WIND_FACTOR_NAME, "value"] == 0:
        geospatial_term = sum([df_indic_lim[i] * COEF_D_MORPHO[day_hour].loc[i, "value"] \
                               for i in COEF_D_MORPHO[day_hour].index[3:]])
    else:
        geospatial_term = ws * sum([df_indic_lim[i] * COEF_D_MORPHO[day_hour].loc[i, "value"] \
                                    for i in COEF_D_MORPHO[day_hour].index[3:]])
    d = COEF_D_MORPHO[day_hour].loc[CONSTANT_NAME, "value"] \
        + ws * COEF_D_MORPHO[day_hour].loc[WSPEED, "value"] \
            + geospatial_term
    
    return d

def calc_park_effect(df_indic, tair, ws_norm, dpv_norm, day_hour):
    """ Calculates the effect of the park on the air temperature observed within 
    a given corridor.

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

			df_indic: pd.DataFrame
				Park soil and vegetation fractions used for the calculation of the cooling rate
            tair: float
                Air temperature at the given date and time
            ws_norm: float
                Wind speed normalized by the cooling factor at a given date and time
            dpv_norm: float
                Saturating pressure deficit normalized by the cooling factor at the given date and time
            day_hour: int
                Time of the day
        
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            T_park: pd.Series
                Air temperature within each cell of a park due to its park ground
                and canopy type"""
    # First calculates the (surface temperature - Tin) and cooling rate for each combination
    # of ground and canopy type met in the park for the given weather condition
    combi_col_names = df_indic.columns
    combi_col_names = combi_col_names.drop(["ID", "ID_ROW", "ID_COL", D_PARK_INPUT, D_PARK_OUTPUT, 
                                            ID_UPSTREAM, CORRIDOR_PARK_FRAC, D_PARK, BLOCK_NB_DENSITY,
                                            BLOCK_SURF_FRACTION, GEOM_MEAN_BUILD_HEIGHT,
                                            STREET_WIDTH, NB_STREET_DENSITY, FREE_FACADE_FRACTION,
                                            MEAN_BUILD_HEIGHT, OPENING_FRACTION])
    df_dts = COEF_SURF_TEMP[day_hour].loc[combi_col_names, "a0"] + COEF_SURF_TEMP[day_hour].loc[combi_col_names, "a1"] * ws_norm +\
        COEF_SURF_TEMP[day_hour].loc[combi_col_names, "a2"] * dpv_norm + COEF_SURF_TEMP[day_hour].loc[combi_col_names, "a12"] * ws_norm * dpv_norm
    df_cr = COEF_COOLING_RATE[day_hour].loc[combi_col_names, "a0"] + COEF_COOLING_RATE[day_hour].loc[combi_col_names, "a1"] * ws_norm +\
        COEF_COOLING_RATE[day_hour].loc[combi_col_names, "a2"] * dpv_norm + COEF_COOLING_RATE[day_hour].loc[combi_col_names, "a12"] * ws_norm * dpv_norm    
    
    # Calculates the number of 10 m width squares met along each corridor
    n = (df_indic[D_PARK_INPUT].abs()) / PATTERN_SIZE
    
    # Set the max footprint size that can have an effect on the air temperature at a given point
    n[n > MAX_DIST[day_hour] / PATTERN_SIZE] = MAX_DIST[day_hour] / PATTERN_SIZE
    
    # Calculates the air temperature going out of the park taking into account:
    #   - the length of the corridor (formula with the n exponent)
    #   - the composition of the corridor (apply the previous formula for all type and then weight by area fraction)
    #   - weight the Tout - Tin difference by the fraction of the corridor covered by the park
    one_minus_cr_n = pd.DataFrame({i: (1 - df_cr[i])**(n) for i in df_cr.index}, index = n.index)
    T_park = df_indic[combi_col_names].mul(tair, axis = 0).sum(axis = 1)\
            + df_indic[combi_col_names].mul((1 - one_minus_cr_n).mul(df_dts), axis = 0)\
                .sum(axis = 1)
    T_park = tair + (T_park - tair) * (df_indic[CORRIDOR_PARK_FRAC])
    
    return T_park

def limit_geoindic(df_indic, limits):
    for ind in df_indic.columns[df_indic.columns.isin(limits.index)]:
        df_indic.loc[df_indic[df_indic[ind] > limits.loc[ind, "MAX"]].index, ind] = limits.loc[ind, "MAX"]
        df_indic.loc[df_indic[df_indic[ind] < limits.loc[ind, "MIN"]].index, ind] = limits.loc[ind, "MIN"]
    
    return df_indic

def normalize_factor(value, value_min, value_max):
    result = (value - (value_min + value_max) / 2) / ((value_max - value_min) / 2)
    result[result>1] = 1
    result[result<-1] = -1
    return result

def denormalize_factor(value, value_min, value_max):
    return value * ((value_max - value_min) / 2) + (value_min + value_max) / 2

def identify_previous_temp(grid_ind_current_upstream, grid_ind_previous, grid_tair, grid_dtair):
    """ Identify the last IDs of the previous land type (either city if we are
    interested in the park, either park if we are interested in the city) and get
    its air temperature in order to use it as input for the new land type.

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

			grid_ind_current_upstream: pd.DataFrame
				Grid containing the cell of the current type of land for a given upstream number
            grid_ind_previous: pd.DataFrame
                Grid containing the cell of the previous type of land
            grid_tair: pd.DataFrame
                Grid of air temperature
            grid_dtair: pd.DataFrame
                Grid of delta T air temperature
        
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            grid_current_tair: pd.Series
                Air temperature within each cell of the current land type
            grid_current_dtair: pd.Series
                Delta air temperature within each cell of the current land type"""
    
    # Get the first cell of the i_st patch of park
    rows_n_cols_concerned = grid_ind_current_upstream.groupby("ID_COL")["ID_ROW"].min()
    
    # Get the first cell of the i_st patch of park
    rows_n_cols_concerned = grid_ind_current_upstream.groupby("ID_COL")["ID_ROW"].min()
    
    # Get the ID of the cells located right before (upstream) 
    # the first cell of the park    
    id_concerned =  \
        [grid_ind_previous[(grid_ind_previous["ID_COL"] == i)\
                            * (grid_ind_previous["ID_ROW"] == rows_n_cols_concerned[i] - 1)].index[0]\
          for i in rows_n_cols_concerned.index]

    # Get the air temperature of these cells right before park patch
    grid_tair_previous = grid_tair.loc[id_concerned]
    grid_tair_previous.index = rows_n_cols_concerned.index # Reindex to be able to add the input air temperature to the park cooling effect
    grid_dtair_previous = grid_dtair.loc[id_concerned]
    grid_dtair_previous.index = rows_n_cols_concerned.index #idem preced for deltaT
        
    
    # Set as default temperature for all current land cells the one calculated as output of the previous land
    grid_current_tair = pd.concat([pd.Series({i: grid_tair_previous[col] \
                                              for i in grid_ind_current_upstream[grid_ind_current_upstream["ID_COL"] == col].index}) \
                                   for col in grid_tair_previous.index])
    grid_current_dtair = pd.concat([pd.Series({i: grid_dtair_previous[col] \
                                              for i in grid_ind_current_upstream[grid_ind_current_upstream["ID_COL"] == col].index}) \
                                   for col in grid_dtair_previous.index])
    
    return grid_current_tair, grid_current_dtair

def save_raster(array, path, x_count, y_count, geotransform, projection):
    """ Save a raster file using gdal

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

			array: 2D-array like
				Values to write
            path: string
                Path where to save the raster
            x_count: in
                Number of columns of the raster
            y_count: int
                Number of rows of the raster
            geotransform: raster GetGeoTransform()
                Informations about the location of the raster
            projection: raster GetProjection()
                Information about the projection to use for the raster
        
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            None """
    driver = gdal.GetDriverByName("GTiff")
    output_dt = driver.Create(path, 
                              x_count, 
                              y_count, 
                              1, 
                              gdalconst.GDT_Float32)
    output_dt.SetGeoTransform(geotransform)
    output_dt.SetProjection(projection)
    
    # Write the result array to the output raster band
    output_band_t = output_dt.GetRasterBand(1)
    output_band_t.WriteArray(array)
    
    # Close the output raster
    output_ds = None
    
def calc_build_impact(df_indic, deltaT_cols):
    """ Calculates the effect of the park on building energy and thermal
    comfort indicators.

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

			df_indic: pd.DataFrame
				Building indicators used for the regression

		Returns
		_ _ _ _ _ _ _ _ _ _ 

            df_impacts: pd.DataFrame
                For each building, the absolute and relative energy and
                thermal comfort impact of the park"""
    df_impacts = pd.DataFrame(index = df_indic.index)
    
    # Calculate the energy consumption and thermal comfort without park effect
    df_indic_nopark = df_indic.copy(deep = True)
    df_indic_nopark.loc[:, BUILDING_AMPLIF_FACTOR] = 0
    df_NRJ_without = build_impact_formula(df_indic = df_indic_nopark, variable = "NRJ")
    df_comf_without = build_impact_formula(df_indic = df_indic_nopark, variable = "comfort")
    
    # Calculate the energy consumption and thermal comfort with park effect
    df_NRJ_with = build_impact_formula(df_indic = df_indic, variable = "NRJ")
    df_comf_with = build_impact_formula(df_indic = df_indic, variable = "comfort")
    
    # Calculates the absolute impact of the park
    df_impacts[ENERGY_IMPACT_ABS] = df_NRJ_with.subtract(df_NRJ_without)
    df_impacts[THERM_COMFORT_IMPACT_ABS] = df_comf_with.subtract(df_comf_without)
    
    # Calculates the relative impact of the park
    df_impacts[ENERGY_IMPACT_REL] = df_impacts[ENERGY_IMPACT_ABS].divide(df_NRJ_without) * 100
    df_impacts[THERM_COMFORT_IMPACT_REL] = df_impacts[THERM_COMFORT_IMPACT_ABS].divide(df_comf_without) * 100
       
    return df_impacts

def build_impact_formula(df_indic, variable):
    """ Calculates the effect of the park on building energy cooling

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

			df_indic: pd.DataFrame
				Building indicators used for the regression
            variable: String
                The type of variable that is needed to calculate
                    -> "NRJ": for building cooling calculation
                    -> "comfort": for thermal comfort inside building

		Returns
		_ _ _ _ _ _ _ _ _ _ 

            df_build_effect: pd.Serie
                For each building, the effect on the building (either energy or thermal comfort)"""
    df_effect = pd.Series(index = df_indic.index)
    
    # The number of models is equal to the combination of all values included within variables
    list_of_possible = [df_indic[BUILD_GEOM_TYPE].unique(),
                        df_indic[BUILD_NORTH_ORIENTATION].unique(),
                        df_indic[BUILD_SIZE_CLASS].unique()]
    all_combi = list(itertools.product(*list_of_possible))
    
    if variable == "NRJ":
        path_to_file = BUILD_ENERGY_PATH
    elif variable == "comfort":
        path_to_file = BUILD_COMFORT_PATH
    
    # Limit the values of the geospatial indicators to the range used for 
    # the indicators during the training phase
    df_indic = limit_geoindic(df_indic, BUILD_EXTREMUM_VAL)
    
    # For each combination of building type
    for gt_c, ot_c, bc_c in all_combi:
        # Get the name corresponding to each type
        gt = BUILDING_GEOMETRY_CLASSES.loc[gt_c, "name"]
        ot = ORIENTATIONS.loc[ot_c, "name"]
        bc = BUILDING_SIZE_CLASSES.loc[bc_c, "name"]
        
        # Load regression coefficients
        df_coef = pd.read_csv(path_to_file + os.sep + f"{bc}_{gt}_{ot}.csv",
                              header = 0,
                              index_col = 0)
        # Shutter is in lower case in the coefficients while in upper case otherwise...
        df_coef.loc[:, "var1"] = df_coef.loc[:, "var1"].str.upper()
        df_coef.loc[:, "var2"] = df_coef.loc[:, "var2"].str.upper()
        
        # Keep only buildings having the current combination of types
        condition = (df_indic[BUILD_GEOM_TYPE] == gt_c)\
            * (df_indic[BUILD_NORTH_ORIENTATION] == ot_c)\
                * (df_indic[BUILD_SIZE_CLASS] == bc_c)
        idx_build = df_indic[condition].index
        
        # Calculates the energy needed by the building
        #constant = df_coef[df_coef["var1"].isna()].value[0]
        
        condition_lin_term = (df_coef["var1"].notna())*(df_coef["var2"].isna())
        linear_terms = sum([row["value"] * df_indic.loc[idx_build, row["var1"]] \
                        for index, row in df_coef[condition_lin_term][["value", "var1"]].iterrows()])
    
        condition_cross_term = (df_coef["var1"].notna())*(df_coef["var2"].notna())
        cross_terms = sum([row["value"] * df_indic.loc[idx_build, row["var1"]]\
                            * df_indic.loc[idx_build, row["var2"]] \
                        for index, row in df_coef[condition_cross_term][["value", "var1", "var2"]].iterrows()])
    
        #df_effect.loc[idx_build] = constant + linear_terms + cross_terms
        df_effect.loc[idx_build] = linear_terms + cross_terms
    
    return df_effect
