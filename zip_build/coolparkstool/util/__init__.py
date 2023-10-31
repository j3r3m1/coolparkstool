# -*- coding: utf-8 -*-
# __author__ = 'xlinfr'

from qgis.PyQt.QtWidgets import QMessageBox
from .coolparkstool_installer import setup_coolparkstool_python
from qgis.core import Qgis, QgsMessageLog
# we can specify a version if needed
try: 
    import jaydebeapi
except:
    if QMessageBox.question(None, "CoolParksTool Python dependencies not installed",
              "Do you automatically want install missing python modules? \r\n"
              "QGIS will be non-responsive for a couple of minutes.",
               QMessageBox.Ok | QMessageBox.Cancel) == QMessageBox.Ok:
        try:
            setup_coolparkstool_python(ver=None)
            QMessageBox.information(None, "Packages successfully installed",
                                    "To make all parts of the plugin work it is recommended to restart your QGIS-session.")
        except Exception as e:
            QMessageBox.information(None, "An error occurred",
                                    "Packages not installed. report any errors to https://github.com/J3r3m1/CoolParksTool/issues")
    else:
        QMessageBox.information(None,
                                "Information", "Packages not installed. CoolParksTool will not be fully operational.")
