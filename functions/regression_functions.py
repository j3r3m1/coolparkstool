# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import statsmodels.formula.api as smf
import matplotlib.pylab as plt
import math
from statsmodels.sandbox.regression.predstd import wls_prediction_std
from scipy.optimize import curve_fit
from globalVariables import WSPEED

def reg_mod(y, y_name, params, robust = False, reg_type = "poly", offset_null = False, n_order = 1):
	"""Create a polynomial regression model of a variable from one or several other variables.
	
		Parameters
	_ _ _ _ _ _ _ _ _ _ 
	
			y : pd.Series
				Values taken by the y variable to be modeled
			y_name : str
				Name of the variable to be modeled
			params : pd.DataFrame or pd.Series
				Values taken by the variable(s) which will be used for modelling our y variable
			robust : boolean, default False
				If robust is True, robust regression (statsmodels.formula.api.rlm) is used instead of the traditional ordinary least square (statsmodels.formula.api.ols).
				It is less sensitive to outliers so coefficients found by the regression may differ a lot from traditional regression.
			reg_type : {"x_n", "poly", "log"}, default "poly"
				Dictionary of non linear regression types linearized if necessary
					--> "x_n" : shape of p1 * x**n + p2 with n = n_order and p2 = 0 if offset_null = True
					--> "poly" : shape of polynomial function
					--> "log" : shape of log(p1 * x + p2)
			offset_null : boolean, default False
				Define if the regression equation is contrained by f(x = 0) = 0 or not
			n_order : int, default 1
				Maximum order of the polynomial regression model
				
		Returns
	_ _ _ _ _ _ _ _ _ _ 
	
			Model instance"""
	
	params = pd.DataFrame(params)
	df_buff = params.join(pd.Series(y, name = y_name))
	if reg_type is "log":
		offset_null = False						#Needed to calculate p2 in y = log(p1 * x + p2)
		df_buff[y_name] = np.exp(df_buff[y_name])
	df = pd.DataFrame(index = range(0, len(df_buff)), columns = df_buff.columns)
	
	for c in df_buff.columns:
		if reg_type is "x_n":
			df[c] = (df_buff[c].values.astype(float)) ** n_order		#Necessary to homogeneise data type as float. Otherwise, several ols models could sometimes be created
		df[c] = df_buff[c].values.astype(float)		#Necessary to homogeneise data type as float. Otherwise, several ols models could sometimes be created
	
	formula = y_name + " ~ "
	if offset_null is False:
		formula += " 1"
	elif offset_null is True:
		formula += " - 1"
	for p in params.columns:
		formula += " + " + p
		if reg_type is "poly":
			for n in range(2, n_order + 1):
				formula += " + I(" + p + " ** " + str(n) + ")"
	
	if robust is False:
		result = smf.wls(formula = formula, data = df).fit()
	else:
		result = smf.wls(formula = formula, data = df).fit()
	
	return result


def plot_regression(modeled, x, color, equation_vposition, robust = False, offset_null = False, equation_disp = "EQUA_N_CARAC", confidence_interval = np.nan, equation_hposition = "left", \
equation_fontsize = 20, linestyle = "-", linewidth = 2, reg_type = "poly", n_order = 1, fig = None, ax = None, label = None):
	"""Plot a polynomial regression model curve (if the modeled variable y is explained only by a unique variable x) on a graphic (potentially on an existing figure).
	
		Parameters
	_ _ _ _ _ _ _ _ _ _ 
	
			modeled : Model instance
				The model instance to be plotted
			x : np.array
				Values taken by the explaining variable on the graphic
			color : matplotib color
				Color of the modeled variable curve
			equation_vposition : np.float
				Position (in y coordinate) of the regression equation on the graphic on the vertical axis (adviced y.quantile(q = 0.95).
			robust : boolean, default False
				If robust is True, robust regression (statsmodels.formula.api.rlm) is used instead of the traditional ordinary least square (statsmodels.formula.api.ols).
				It is less sensitive to outliers so coefficients found by the regression may differ a lot from traditional regression.
			offset_null : boolean, default False
				Define if the regression equation is contrained by f(x = 0) = 0 or not
			equation_disp : {"EQUA_N_CARAC", "EQUA", "CARAC", None}, default = "EQUA_N_CARAC
				Information on the model to be displayed on the graphic
						--> "EQUA_N_CARAC" : The equation AND the R2 and f_pvalue will be displayed
						--> "EQUA" : ONLY the equation will be displayed
						--> "CARAC" : ONLY the R2 and f_pvalue will be displayed
						--> None : None of the equation and the R2 and f_pvalue will be displayed
			confidence_interval : np.float (included in the interval [0, 1], default np.nan
				Confidence interval for two-sided hypothesis
			equation_hposition : {"left", "right"}, default "left"
				Position of the regression equation on the graphic
					--> "left" : on the left side
					--> "right" : on the right side
			equation_fontsize : int, default 20
				Fontsize of the equation displayed on the chart
			linestyle : matplotlib linestyle, default "-"
				Style of the line curve
			linewidth : float, default 2
				Thickness of the regression curve line
			reg_type : {"x_n", "poly", "log"}, default "poly"
				Dictionary of non linear regression types linearized if necessary
					--> "x_n" : shape of p1 * x**n + p2 with n = n_order and p2 = 0 if offset_null = True
					--> "poly" : shape of polynomial function
					--> "log" : shape of log(p1 * x + p2)
			n_order : int, default 1
				Maximum order of the polynomial regression model
			fig : plt.Figure object
				Figure on which the modeled variable curve should be plotted
			ax : plt.Axes object
				Axes on which the modeled variable curve should be plotted
			label : string, default None
				Label to display in the legend. If label is different from None and equation_disp is different from None, then the equation caracteristics
				will be displayed with the label you entered.
				
		Returns
	_ _ _ _ _ _ _ _ _ _ 
	
			Figure and Axe object where the new regression curve has been plotted
			
			WARNING ! The determination coefficient for the robust regression is not displayed (neither calculated) because it would take into account 
			outliers that which makes no sense..."""
	
	if fig == None:
		fig = plt.figure(plt.get_fignums()[-1])
	if ax == None:
		ax = fig.get_axes()[0]
	
	if reg_type is "log":
		offset_null = False						#Needed to calculate p2 in y = log(p1 * x + p2)
	
	no_equation = False
	if offset_null is True:
		offset = 0
	elif offset_null is False:
		offset = modeled.params["Intercept"]
	slope = {}
	slope[1] = modeled.params[x.name]
	if math.isnan(slope[1]):
		no_equation = True
	else:
		if reg_type is "poly":
			formula = lambda x : slope[1] * x + offset
			equation = "y = " + str(np.round(slope[1], 3)) + " . x + " + str(np.round(offset, 3))
		elif reg_type is "log":
			formula = lambda x : np.log(slope[1] * x + offset)
			equation = "y = log(" + str(np.round(slope[1], 3)) + " . x + " + str(np.round(offset, 3)) + ")"
		elif reg_type is "x_n":
			formula = lambda x : slope[1] * x ** n_order + offset
			equation = "y = " + str(np.round(slope[1], 3)) + " . x**" + str(n_order) + " + " + str(np.round(offset, 3))
			
	if reg_type is "poly":
		for n in range(2, n_order + 1):
			slope[n] = modeled.params["I(" + x.name + " ** " + str(n) + ")"]
			if math.isnan(slope[n]):
				no_equation = True
			else:
				equation += " + " + str(np.round(slope[n], 3)) + "x**" + str(n) 
	
	if no_equation is False:
		if reg_type is "poly":
			if n_order == 2:
				formula = lambda x : slope[1] * x + offset + slope[2] * x ** 2
				
			elif n_order == 3:
				formula = lambda x : slope[1] * x + offset + slope[2] * x ** 2 + slope[3] * x ** 3
				
			elif n_order == 4:
				formula = lambda x : slope[1] * x + offset + slope[2] * x ** 2 + slope[3] * x ** 3 + slope[4] * x ** 4

			elif n_order == 5:
				formula = lambda x : slope[1] * x + offset + slope[2] * x**2 + slope[3] * x**3 + slope[4] * x**4 + slope[5] * x**5
		
		x_vec = np.arange(min(x.dropna()), max(x.dropna()), (max(x.dropna()) - min(x.dropna())) / 50)
		
		if robust is True:
			rsquared_adj = "No_R2 "
			p_val = "No_pval"
		else:
			rsquared_adj = "R2 = " + str(np.round(modeled.rsquared_adj, 3))
			
			p_val = str(np.round(modeled.f_pvalue, 3))
		carac = rsquared_adj + " - " + "pval = " +  p_val
		if equation_disp is "EQUA_N_CARAC":
			to_display =  "   " + equation + "\n   " + carac
		elif equation_disp is "EQUA":
			to_display =  "   " + equation
		elif equation_disp is "CARAC":
			to_display =  "   " + carac
		elif equation_disp is None:
			to_display =  ""		
		if label is not None and equation_disp is not None:
			label += to_display
		
		ax.plot(x_vec, formula(x_vec), linewidth = linewidth, linestyle = linestyle, color = color, label = label)
		if np.isnan(confidence_interval) is False:
			prstd, iv_l, iv_u = wls_prediction_std(modeled, alpha = confidence_interval)
			df = pd.DataFrame({"iv_l" : iv_l.values, "iv_u" : iv_u.values}, index = x).sort()		
			ax.plot(df.index.values, df["iv_l"].values, "--k", markersize = 0)
			ax.plot(df.index, df["iv_u"], "--k", markersize = 0)
		

		if equation_hposition is "left":
			x_legend = x.min()
		elif equation_hposition is "right":
			x_legend = x.max()
		y_legend = equation_vposition

		ax.annotate(to_display, (x_legend, y_legend), color = color, fontsize = equation_fontsize)
	
	return fig, ax

def non_lin_reg_mod(y, x, weights = None):
    initial_guess = [1.0] + [0.0] + [0.0] * (x.shape[0] - 1) 
    popt, pcov = curve_fit(model_formula, x, y, p0 = initial_guess,
                           sigma = weights) 
    residuals = y - model_formula(np.insert(x, 0, 1), *popt) 
    
    coef_values = pd.Series(popt, index = ["p" + str(i) for i in range(1, len(popt) + 1)], name = "values") 
    coef_cov = pd.DataFrame(pcov, columns = ["p" + str(i) for i in range(1, len(popt) + 1)], index = ["p" + str(i) for i in range(1, len(popt) + 1)]) 
    
    return coef_values, coef_cov, residuals


def model_formula(x, *coeffs):
    term = np.sum([coeff * x[i+1] for i, coeff in enumerate(coeffs[2:])])
    return coeffs[0] + coeffs[1] * x[0] + x[0] * term

def round_to(number, ndecim):
    return round(number, ndecim - int(np.floor(np.log10(abs(number))) + 1))