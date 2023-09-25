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
import struct
from qgis.PyQt.QtGui import QIcon
import inspect
import unidecode

from .functions import mainCalculations
from .functions.globalVariables import *
from .functions import WriteMetadata

from .functions.H2gisConnection import getJavaDir, setJavaDir, saveJavaDir



class CoolParksPreparerAlgorithm(QgsProcessingAlgorithm):
    """
    
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    # Input variables
    # JAVA_PATH = "JAVA_PATH"
    BUILDING_TABLE_NAME = 'BUILDINGS'
    PARK_BOUNDARIES_TABLE_NAME = "PARK_BOUNDARIES"
    PARK_GROUND_TABLE_NAME = "PARK_GROUND"
    PARK_CANOPY_TABLE_NAME = "PARK_CANOPY"
    
    BUILD_HEIGHT_FIELD = "BUILD_HEIGHT_FIELD"
    DEFAULT_BUILD_HEIGHT = "DEFAULT_BUILD_HEIGHT"
    BUILD_AGE_FIELD = "BUILD_AGE"
    DEFAULT_BUILD_AGE = "DEFAULT_BUILD_AGE"
    BUILD_WWR_FIELD = "BUILD_WWR"
    DEFAULT_BUILD_WWR = "DEFAULT_BUILD_WWR"
    BUILD_SHUTTER_FIELD = "BUILD_SHUTTER"
    DEFAULT_BUILD_SHUTTER = "DEFAULT_BUILD_SHUTTER"
    
    PARK_GROUND_TYPE_FIELD = "PARK_GROUND_TYPE"
    PARK_CANOPY_TYPE_FIELD = "PARK_CANOPY_TYPE"
    
    # Output variables    
    OUTPUT_DIRECTORY = "UROCK_OUTPUT"
    SCENARIO_NAME = "SCENARIO_NAME"
    
    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """
        
        
        self.addParameter(
            QgsProcessingParameterString(
                self.SCENARIO_NAME,
                self.tr('Scenario name for the current urban morphology and park'),
                defaultValue = DEFAULT_SCENARIO,
                optional = False)) 
        
        # We add the input parameters
        # First the layers used as input and output
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.BUILDING_TABLE_NAME,
                self.tr('Building polygons'),
                [QgsProcessing.TypeVectorPolygon],
                optional = False))
        # BUILDIND HEIGHT
        self.addParameter(
            QgsProcessingParameterField(
                self.BUILD_HEIGHT_FIELD,
                self.tr('Building height field'),
                None,
                self.BUILDING_TABLE_NAME,
                QgsProcessingParameterField.Numeric,
                optional = True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEFAULT_BUILD_HEIGHT,
                self.tr('Default building height (m)'),
                QgsProcessingParameterNumber.Double,
                BUILDING_DEFAULT_HEIGHT,
                True))
        # BUILDIND AGE
        self.addParameter(
            QgsProcessingParameterField(
                self.BUILD_AGE_FIELD,
                self.tr('Building construction year'),
                None,
                self.BUILDING_TABLE_NAME,
                QgsProcessingParameterField.Numeric,
                optional = True))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEFAULT_BUILD_AGE,
                self.tr('Default building construction year'),
                QgsProcessingParameterNumber.Integer,
                BUILDING_DEFAULT_AGE,
                True))
        # BUILDIND WWR
        self.addParameter(
            QgsProcessingParameterField(
                self.BUILD_WWR_FIELD,
                self.tr('Building windows-to-wall ratio field'),
                None,
                self.BUILDING_TABLE_NAME,
                QgsProcessingParameterField.Numeric,
                optional = True))  
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEFAULT_BUILD_WWR,
                self.tr('Default building windows-to-wall ratio'), 
                QgsProcessingParameterNumber.Double,
                QVariant(BUILDING_DEFAULT_WINDOWS_WALL_RATIO), 
                False,
                minValue=0.05, 
                maxValue=0.95))
        # BUILDING Shutter
        self.addParameter(
            QgsProcessingParameterField(
                self.BUILD_SHUTTER_FIELD,
                self.tr('Building windows-to-wall ratio field'),
                None,
                self.BUILDING_TABLE_NAME,
                QgsProcessingParameterField.Numeric,
                optional = True))  
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEFAULT_BUILD_SHUTTER,
                self.tr('Default building shutter opening'), 
                QgsProcessingParameterNumber.Double,
                QVariant(BUILDING_DEFAULT_SHUTTER), 
                False,
                minValue=0, 
                maxValue=1))        
        
        # PARK BOUNDARIES
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.PARK_BOUNDARIES_TABLE_NAME,
                self.tr('Park boundaries polygon'),
                [QgsProcessing.TypeVectorPolygon],
                optional=False))
        
        # PARK GROUND COVER
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.PARK_GROUND_TABLE_NAME,
                self.tr('Park ground cover polygons'),
                [QgsProcessing.TypeVectorPolygon],
                optional=False))
        self.addParameter(
            QgsProcessingParameterField(
                self.PARK_GROUND_TYPE_FIELD,
                self.tr('Park ground cover type'),
                None,
                self.PARK_GROUND_TABLE_NAME,
                QgsProcessingParameterField.String,
                optional = False))
        
        # PARK CANOPY COVER
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.PARK_CANOPY_TABLE_NAME,
                self.tr('Park canopy cover polygons'),
                [QgsProcessing.TypeVectorPolygon],
                optional=False))
        self.addParameter(
            QgsProcessingParameterField(
                self.PARK_CANOPY_TYPE_FIELD,
                self.tr('Park canopy cover type'),
                None,
                self.PARK_CANOPY_TABLE_NAME,
                QgsProcessingParameterField.String,
                optional = False))
    
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT_DIRECTORY,
                self.tr('Directory to save the outputs')))

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        
        try:
            import jaydebeapi
        except:
            raise QgsProcessingException("'jaydebeapi' Python package is missing.")

        # Get the plugin directory to save some useful files
        plugin_directory = self.plugin_dir = os.path.dirname(__file__)
        
        # Get the default value of the Java environment path if already exists
        javaDirDefault = getJavaDir(plugin_directory)        
        
        if not javaDirDefault:  # Raise an error if could not find a Java installation
            raise QgsProcessingException("No Java installation found")            
        elif ("Program Files (x86)" in javaDirDefault) and (struct.calcsize("P") * 8 != 32):
            # Raise an error if Java is 32 bits but Python 64 bits
            raise QgsProcessingException('Only a 32 bits version of Java has been'+
                                         'found while your Python installation is 64 bits.'+
                                         'Consider installing a 64 bits Java version.')
        else:   # Set a Java dir if not exist and save it into a file in the plugin repository
            setJavaDir(javaDirDefault)
            saveJavaDir(javaPath = javaDirDefault,
                        pluginDirectory = plugin_directory)
        
        javaEnvVar = javaDirDefault
        
        # # Get the resource folder where styles are located
        # resourceDir = os.path.join(Path(plugin_directory).parent, 'functions', 'URock')
        
        # Defines default buiding values
        def_build_height = self.parameterAsInt(parameters, self.DEFAULT_BUILD_HEIGHT, context)
        def_build_age = self.parameterAsInt(parameters, self.DEFAULT_BUILD_AGE, context)
        def_build_wwr = self.parameterAsDouble(parameters, self.DEFAULT_BUILD_WWR, context)
        def_build_shutter = self.parameterAsDouble(parameters, self.DEFAULT_BUILD_SHUTTER, context)
                
        # Get building layer and then file directory
        inputBuildinglayer = self.parameterAsVectorLayer(parameters, self.BUILDING_TABLE_NAME, context)
        buildHeight = self.parameterAsString(parameters, self.BUILD_HEIGHT_FIELD, context)
        buildAge = self.parameterAsString(parameters, self.BUILD_AGE_FIELD, context)
        buildWWR = self.parameterAsString(parameters, self.BUILD_WWR_FIELD, context)
        buildShutter = self.parameterAsString(parameters, self.BUILD_SHUTTER_FIELD, context)
                
        if inputBuildinglayer:
            build_file = str(inputBuildinglayer.dataProvider().dataSourceUri())
            if build_file.count("|layername") == 1:
                build_file = build_file.split("|layername")[0]
            srid_build = inputBuildinglayer.crs().postgisSrid()

        # Get park boundary layer, check that it has the same SRID as building layer
        # and then get the file directory of the layer
        inputParkBoundLayer = self.parameterAsVectorLayer(parameters, self.PARK_BOUNDARIES_TABLE_NAME, context)
        if inputParkBoundLayer:
            park_bound_file = str(inputParkBoundLayer.dataProvider().dataSourceUri())
            if park_bound_file.count("|layername") == 1:
                park_bound_file = park_bound_file.split("|layername")[0]
            srid_park_bound = inputParkBoundLayer.crs().postgisSrid()
            if srid_build != srid_park_bound:
                feedback.pushWarning('Coordinate system of input building layer and park boundaries differs!')

        # Get park ground layer, check that it has the same SRID as building layer
        # and then get the file directory of the layer
        inputParkGroundLayer = self.parameterAsVectorLayer(parameters, self.PARK_GROUND_TABLE_NAME, context)
        parkGroundType = self.parameterAsString(parameters, self.PARK_GROUND_TYPE_FIELD, context)
        if inputParkGroundLayer:
            park_ground_file = str(inputParkGroundLayer.dataProvider().dataSourceUri())
            if park_ground_file.count("|layername") == 1:
                park_ground_file = park_ground_file.split("|layername")[0]
            srid_park_ground = inputParkGroundLayer.crs().postgisSrid()
            if srid_build != srid_park_ground:
                feedback.pushWarning('Coordinate system of input building layer and park ground differs!')

        # Get park canopy layer, check that it has the same SRID as building layer
        # and then get the file directory of the layer
        inputParkCanopyLayer = self.parameterAsVectorLayer(parameters, self.PARK_CANOPY_TABLE_NAME, context)
        parkCanopyType = self.parameterAsString(parameters, self.PARK_CANOPY_TYPE_FIELD, context)
        if inputParkCanopyLayer:
            park_canopy_file = str(inputParkCanopyLayer.dataProvider().dataSourceUri())
            if park_canopy_file.count("|layername") == 1:
                park_canopy_file = park_canopy_file.split("|layername")[0]
            srid_park_canopy = inputParkCanopyLayer.crs().postgisSrid()
            if srid_build != srid_park_canopy:
                feedback.pushWarning('Coordinate system of input building layer and park canopy differs!')

        
        # Defines outputs
        outputDirectory = self.parameterAsString(parameters, self.OUTPUT_DIRECTORY, context)
        scenarioName = self.parameterAsString(parameters, self.SCENARIO_NAME, context)
        prefix = unidecode.unidecode(scenarioName).replace(" ", "_")
        
        # Creates the output folder if it does not exist
        if not os.path.exists(outputDirectory):
            if os.path.exists(Path(outputDirectory).parent.absolute()):
                os.mkdir(outputDirectory)
            else:
                raise QgsProcessingException('The output directory does not exist, neither its parent directory')
        # Create the folder for the scenario to be run
        if os.path.exists(outputDirectory + os.path.sep + prefix):
            raise QgsProcessingException(f'The folder "{prefix}" already exists in "{outputDirectory}" directory. Please change "Scenario name" or remove the corresponding directory')
        else:
            os.mkdir(outputDirectory + os.path.sep + prefix)
        
        # Create the output folder for the preprocessors and processors
        os.mkdir(outputDirectory + os.path.sep + prefix + os.sep + OUTPUT_PREPROCESSOR_FOLDER)
        os.mkdir(outputDirectory + os.path.sep + prefix + os.sep + OUTPUT_PROCESSOR_FOLDER)
        
        # if feedback:
        #     feedback.setProgressText("Writing settings for this model run to specified output folder (Filename: RunInfoURock_YYYY_DOY_HHMM.txt)")
        # WriteMetadataURock.writeRunInfo(outputDirectory, build_file, heightBuild,
        #                                 veg_file, attenuationVeg, baseHeightVeg, topHeightVeg,
        #                                 z_ref, v_ref, windDirection, profileType,
        #                                 profileFile,
        #                                 meshSize, dz)
        
        # Make the calculations
        cursor, cityAllIndic = \
            mainCalculations.prepareData(plugin_directory = plugin_directory, 
                                        buildingFilePath = build_file,
                                        parkBoundaryFilePath = park_bound_file,
                                        parkCanopyFilePath = park_canopy_file,
                                        parkGroundFilePath = park_ground_file,
                                        srid = srid_build,
                                        build_height = buildHeight,
                                        build_age = buildAge,
                                        build_wwr = buildWWR,
                                        build_shutter = buildShutter,
                                        default_build_height = def_build_height,
                                        default_build_age = def_build_age,
                                        default_build_wwr = def_build_wwr,                                        
                                        default_build_shutter = def_build_shutter,                                        
                                        nAlongWind = N_ALONG_WIND_PARK,
                                        nCrossWind = N_CROSS_WIND_PARK,
                                        feedback = feedback,
                                        output_directory = outputDirectory,
                                        prefix = prefix)
        

        # Return the output file names
        return {self.OUTPUT_DIRECTORY: outputDirectory,
                self.SCENARIO_NAME: scenarioName}

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'coolparkstool_prepare'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('1. Prepare data')

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
        return self.tr('The CoolParksTool "1. Prepare data" module is used '+
                       'to characterize a given scenario:\n'+
                       '    - the park composition along several wind directions,\n'+
                       '    - the urban morphology along several wind directions,\n'+
                       '    - the building types'
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
        return CoolParksPreparerAlgorithm()
