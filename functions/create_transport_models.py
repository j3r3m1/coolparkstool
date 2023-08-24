#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 21 16:29:14 2023

@author: Jérémy Bernard, Chercheur associé au Lab-STICC
"""
import pandas as pd
from regression_functions import reg_mod, plot_regression, non_lin_reg_mod, round_to
from itertools import combinations
from globalVariables import *
import matplotlib.pylab as plt
from pathlib import Path

curdir = os.path.abspath(os.path.curdir)
dedicated_folder = os.path.join(Path(curdir).parent, 'Resources', 'cooling_transport_results')
training_data_paths = {12: os.path.join(dedicated_folder, "training_data_12h.csv"),
                       23: os.path.join(dedicated_folder, "training_data_23h.csv")}

yx = {"dTmorpho": [[MEAN_BUILD_HEIGHT, OPENING_FRACTION, NB_STREET_DENSITY, FREE_FACADE_FRACTION],
                   [MEAN_BUILD_HEIGHT, OPENING_FRACTION, BLOCK_NB_DENSITY, FREE_FACADE_FRACTION]],
      "Dmorpho": [[MEAN_BUILD_HEIGHT, OPENING_FRACTION, NB_STREET_DENSITY],
                  [MEAN_BUILD_HEIGHT, OPENING_FRACTION, BLOCK_NB_DENSITY]]}



# for each time step (12h and 23h)
for tp, path in training_data_paths.items():
    df = pd.read_csv(path,
                     header = 0,
                     index_col = None)
    
    # for each variable to model (dTmorpho and Dmorpho)
    for yn in yx.keys():
        ###############################################################################
        ############################ CREATE THE MODEL #################################
        ###############################################################################
        results = pd.DataFrame(columns = ["tp", "y", "nvars", "formula", "x_combi", "residuals", "rsquared", "pval", "pval_max"])
        # For each combination of variables to test as dependent variables
        for xvars in yx[yn]:
            # Create the list of all list of variables to test
            list_var2test = list()
            for i in xvars:
                list_var2test.append([i])
            for n in np.arange(2, len(xvars) + 1):
                list_var2test += list(combinations(xvars, n))
            
            # Test the regression for each list of variables
            for wind_factor in [True, False]:
                for combi in list_var2test:
                    combi = list(combi)
                    if wind_factor:
                        x_all = df[[WSPEED]].join(df[combi].multiply(df[WSPEED], axis = 0))
                    else:
                        x_all = df[[WSPEED]].join(df[combi])
                    combi = [WSPEED] + combi
                    model = reg_mod(y = df[yn], 
                                    y_name = yn, 
                                    params = x_all, 
                                    robust = False)
                    term2list = [str(round_to(model.params[i+1], 3)) + " . " + combi[i]\
                                     for i in np.arange(1, len(combi))]
                    term_ws = str(round_to(model.params[WSPEED], 3)) + f" . {WSPEED}" 
                    if wind_factor:
                        formula = f"{round_to(model.params['Intercept'], 3)} + {term_ws} + {WSPEED} * ({' + '.join(term2list)})"
                    else:
                        formula = f"{round_to(model.params['Intercept'], 3)} + {term_ws} + {' + '.join(term2list)}"
                    result_i = {"tp": tp,
                                "y": yn, 
                                "nvars": len(combi), 
                                "formula" : formula,
                                "x_combi": combi,
                                "residuals": model.resid,
                                "rsquared": model.rsquared,
                                "pval": model.pvalues,
                                "pval_max": model.pvalues.max()}
                    
                    results = results.append(result_i, ignore_index = True)
            
        ###############################################################################
        ############################ ANALYSE THE RESULTS #################################
        ###############################################################################
        # For each number of variables
        x_plot = []
        y_plot = []
        xtick_labels = []
        for nvar in results.nvars.unique():
            # We keep all models having nvars AND having no pval > 0.01
            valid_results = results[(results["nvars"] ==  nvar) *\
                                    (results["pval_max"] < 0.01)]
            if valid_results.empty:
                id_best_invalid = results[(results["nvars"] ==  nvar)]["pval_max"].idxmin()
                pval_max = results.loc[id_best_invalid, "pval_max"]
                x_plot.append(nvar)
                y_plot.append(results.loc[id_best_invalid, "rsquared"])
                xtick_labels.append(f"(pval_max = {pval_max})\n{results.loc[id_best_invalid, 'formula']}")
            else:
                id_min = valid_results["rsquared"].idxmax()
                x_plot.append(results.loc[id_min, "nvars"])
                y_plot.append(results.loc[id_min, "rsquared"])
                xtick_labels.append(results.loc[id_min, "formula"])
            
        fig, ax = plt.subplots(figsize = (20, 10))
        fig.suptitle(f"{yn} - {tp} h")
        ax.plot(x_plot, y_plot, marker='o', color='blue')
        # Customize x-axis tick labels
        ax.set_xticks(x_plot)
        ax.set_xticklabels(xtick_labels, 
                           fontdict = {"fontsize" : 7}, 
                           rotation = 5,
                           ha='right')
            
        fig.savefig(dedicated_folder + os.sep + f"{yn} - {tp}h")
plt.close("all")
        