# -*- coding: utf-8 -*-

"""
/***************************************************************************
 Prepare CoolParksTool
                                 A QGIS plugin
 This plugin prepare data for the CoolParksTool
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2023-07-06
        copyright            : (C) 2023 by Jérémy Bernard / University of Gothenburg
        email                : jeremy.bernard@zaclys.net
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Jérémy Bernard'
__date__ = '2023-07-06'
__copyright__ = '(C) 2023 by Jérémy Bernard'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import os
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterField,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterMatrix,
                       QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterString,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterBoolean,
                       QgsRasterLayer,
                       QgsVectorLayer,
                       QgsProject,
                       QgsProcessingContext,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFile,
                       QgsProcessingException)
from qgis.PyQt.QtWidgets import QMessageBox
# qgis.utils import iface
from pathlib import Path
from qgis.PyQt.QtGui import QIcon
import inspect
import unidecode

from .functions import mainCalculations
from .functions.globalVariables import *
from .functions import WriteMetadata


class CoolParksProcessorAlgorithm(QgsProcessingAlgorithm):
    """
    
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    # Input variables
    SCENARIO_DIRECTORY = "SCENARIO_DIRECTORY"
    WEATHER_FILE = "WEATHER_FILE"
    WEATHER_SCENARIO = "WEATHER_SCENARIO"
    OUTPUT_DIRECTORY = "OUTPUT_DIRECTORY"
    
    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """
        
        # We add the input parameters
        # First the layers used as input and output
        self.addParameter(
            QgsProcessingParameterFile(
                self.SCENARIO_DIRECTORY,
                self.tr('Directory of the scenario of interest'),
                behavior=QgsProcessingParameterFile.Folder))
        self.addParameter(
            QgsProcessingParameterFile(
                self.WEATHER_FILE,
                self.tr('Input meteorological file (.txt or .csv)')))
        self.addParameter(
            QgsProcessingParameterString(
                self.WEATHER_SCENARIO,
                self.tr('Name of the meteorological scenario'),
                defaultValue = DEFAULT_PREFIX,
                optional = False)) 

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        
        # try:
        #     import jaydebeapi
        # except:
        #     raise QgsProcessingException("'jaydebeapi' Python package is missing.")
        
        scenarioDirectory = self.parameterAsString(parameters, self.SCENARIO_DIRECTORY, context)
        weatherFile = self.parameterAsString(parameters, self.WEATHER_FILE, context)
        weatherScenario = self.parameterAsString(parameters, self.WEATHER_SCENARIO, context)
        prefix = unidecode.unidecode(weatherScenario).replace(" ", "_")
        
        # Creates the output folder if it does not exist
        if os.path.exists(scenarioDirectory + os.sep + OUTPUT_PROCESSOR_FOLDER):
            if os.path.exists(scenarioDirectory + os.sep + OUTPUT_PROCESSOR_FOLDER + os.sep + prefix):
                raise QgsProcessingException(f'"{prefix}" folder already exists in "{scenarioDirectory + os.sep + OUTPUT_PROCESSOR_FOLDER}"')
            else:
                os.mkdir(scenarioDirectory + os.sep + OUTPUT_PROCESSOR_FOLDER + os.sep + prefix)   
        else:
            raise QgsProcessingException(f'"{scenarioDirectory}" should contain a folder called "{OUTPUT_PROCESSOR_FOLDER}". It is not the directory of a preprocessed scenario.')
        

        # if feedback:
        #     feedback.setProgressText("Writing settings for this model run to specified output folder (Filename: RunInfoURock_YYYY_DOY_HHMM.txt)")
        # WriteMetadataURock.writeRunInfo(outputDirectory, build_file, heightBuild,
        #                                 veg_file, attenuationVeg, baseHeightVeg, topHeightVeg,
        #                                 z_ref, v_ref, windDirection, profileType,
        #                                 profileFile,
        #                                 meshSize, dz)
        
        if feedback:
            feedback.setProgressText("Calculate park effect on air temperature")
            if feedback.isCanceled():
                feedback.setProgressText("Calculation cancelled by user")
                return {}
        # Calculates the effect of the park on its surrounding
        mainCalculations.calcParkInfluence(weatherFilePath = weatherFile, 
                                           preprocessOutputPath = scenarioDirectory,
                                           prefix = prefix,
                                           feedback = feedback)
        
        if feedback:
            feedback.setProgressText("Calculate park effect on building energy and thermal comfort")
            if feedback.isCanceled():
                feedback.setProgressText("Calculation cancelled by user")
                return {}
        # Calculates the impact of the cooling on the buildings
        mainCalculations.calcBuildingImpact(preprocessOutputPath = scenarioDirectory,
                                            prefix = prefix)
        
        # Return the output file names
        return {self.OUTPUT_DIRECTORY: scenarioDirectory + os.sep + OUTPUT_PROCESSOR_FOLDER + os.sep + prefix}


    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'coolparkstool_process'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('2. Calculate park effects')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return ''

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
    
    def shortHelpString(self):
        return self.tr('The CoolParksTool prepare plugin can be used to prepare '+\
                       'the spatial data that are used in the CoolParksTool'+
                       ' models'+
        '\n'
        '\n'
        'This tools requires Java. If Java is not installed on your system,'+ 
        'visit www.java.com and install the latest version. Make sure to install correct version '+
        'based on your system architecture (32- or 64-bit).'
        '\n'
        '\n'
        '---------------\n'
        'Full manual available via the <b>Help</b>-button.')

    def helpUrl(self):
        url = "https://github.com/j3r3m1/coolparkstool"
        return url
    
    def icon(self):
        cmd_folder = Path(os.path.split(inspect.getfile(inspect.currentframe()))[0]).parent
        icon = QIcon(str(cmd_folder) + "/icons/urock.png")
        return icon

    def createInstance(self):
        return CoolParksProcessorAlgorithm()
