# -*- coding: utf-8 -*-
from .globalVariables import *
import numpy as np

from . import DataUtil
from . import loadData

import string

def dpv_calc(df):
    T_radian = df[T_AIR] * np.pi / 180.0 # convert to radian for trigonometric function 
    p_sat = 610.7 * (1 + 2 ** 0.5 * np.sin(T_radian / 3)) ** 8.827 # formula from Alt, cf. Guyot p.106
    DPV = (p_sat - df[RH] * p_sat / 100) / 100 # deficit de pression de vapeur en hectopascal
    
    return DPV

def air_cooling_and_diffusion(grid_values, grid_indic, tair, ws, dpv):
    """ For a given wind direction, calculates the park effect on the air 
    temperature within and outside the park boundaries. The corresponding
    grid is added to the temperature grid that has been summed previously for
    this given direction. 

		Parameters
		_ _ _ _ _ _ _ _ _ _ 

			grid_values: pd.Series
				Air temperature grid for a given wind direction      
            grid_indic: pd.DataFrame
                Grid containing park and city indicators for a given wind direction
            tair: float
                Air temperature at the given date and time
            ws: float
                Wind speed at the given date and time
            dpv: float
                Saturating pressure deficit at the given date and time
        
		Returns
		_ _ _ _ _ _ _ _ _ _ 

            Sum of the air temperature grid for this given wind direction"""
    
    # Effect of the city morphology before the park on the air temperature
    