# CoolParksTool

**A version for the Processing Toolbox in QGIS**

This is the official repository for the CoolParksTool.
It summarizes the results of the research project called CoolParks. 
The user provides park boundaries, type of ground within the park, 
type of canopy within the park and meteorological conditions. 
As output the cooling effect of the park on its surrounding built-up area 
is calculated as well as its impact on building energy consumption and building
 indoor thermal comfort

## Installation

### Pré-requis
Comme [GeoClimate](https://github.com/orbisgis/geoclimate) ou le module [URock de UMEP](https://umep-docs.readthedocs.io/en/latest/processor/Wind%20model%20URock.html), CoolParksTool utilise pour une grande partie de ses calculs le système de gestion de bases de données spatiales [H2GIS](https://github.com/orbisgis/h2gis).

Ce système reposant sur Java, il est nécessaire que votre ordinateur dispose d'une installation du logiciel Java relativement récente (>=8):
- pour windows: https://java.com/en/download/windows_manual.jsp
- pour linux: https://java.com/en/download/
- pour macOS: https://www.java.com/en/download/apple.jsp

### Créer un environnement propice à l’installation de CoolParksTool

Il est tout d'abord nécessaire de créer un environnement propice à l'installation de CoolParksTool. Pour cela, 2 solutions sont possibles :
- si vous avez un environnement Windows, il est préférable de préalablement installer le programme qui s’appelle osgeo4W (https://trac.osgeo.org/osgeo4w/).
- Si vous ne souhaitez pas utiliser cet outil ou que vous avez un environnement Linux ou MacOS, il est recommandé de préalablement utiliser le programme qui s’appelle Anaconda (https://anaconda.org/).

#### Installation via osgeo4W
Ce programme permet de gérer l’installation de librairies python dans un environnement dédié dans lequel un certain nombre de librairies utilisées par QGIS sont préinstallées. 

Pour l’utiliser :
- télécharger l’installateur: https://download.osgeo.org/osgeo4w/v2/osgeo4w-setup.exe
- lancer le une première fois en sélectionnant “install express”. Cocher QGIS, QGIS LTR, GDAL et GRASS
- à la fin de l’installation, il est nécessaire d’installer d’autres librairies. Pour cela, relancer l’installateur (osgeo4W-setup) mais cette fois ci sélectionner “advanced installation”. Cliquer XX fois sur suivant. Trois librairies doivent ensuite être installées : shapely, geopandas et statsmodels. Pour cela :
    - rechercher les dans la barre de recherche  : entrer le nom mais inutile de taper entrer ensuite, il s’agit simplement de cliquer sur le + qui permet d’afficher les résultats de la recherche
    - l’installer si nécessaire : si aucune version de la librairie recherchée n’est installée, il faut cliquer une seule fois sur la ligne correspondant à la librairie à installer. Si une version est affichée, cela signifie que la librairie est déjà installer, aucune action n’est nécessaire. Réitérer ces deux derniers points pour chaque librairie à installer.
- Enfin, X autres librairies sont à installer en-dehors de l’installateur d’osgeo4W. Elles doivent cependant être installées dans le même environnement. Pour cela, il faut cette fois ci lancer le “shell osgeo4W”. Une fois lancé, il faut installer les librairies via pip :
    - pip install unidecode
    - pip install ?

#### Installation via anaconda
Anaconda permet de gérer l’installation de librairies Python via la création d’environnements dédiés à un besoin donné. Il permet également de s’assurer de l’intercompatibilité des librairies entre elles dans un environnement donné. 

Pour l’utiliser :
    -télécharger la version d’anaconda propre à votre système d’exploitation : https://www.anaconda.com/download#downloads
    - lancer l’installation
    - il s’agit maintenant de créer un nouvel environnement dédié à l’utilisation de CoolParksTool et d’installer les librairies nécessaires à son fonctionnement dans cet environnement. Pour cela, deux solutions existent :
        - si vous avez installé anaconda en mode “ligne de commande” :
            - ouvrer un terminal
            - créer un nouvel environnement : conda create --name coolparks
            - activer cet environnement : conda activate coolparks
            - ajouter une nouvelle source de librairies d’où anaconda pourra télécharger des librairies : conda config --add channels conda-forge
            - installer les librairies (cela peut prendre un temps considérable de gérer les dépendances) : conda install gdal qgis shapely geopandas unidecode statsmodels
            - lancer QGIS via le terminal en tapant : qgis
        - si vous avez installé anaconda en mode “graphique” :

### Installer CoolParksTool
Quelle que soit la solution choisie, vous devez maintenant avoir QGIS ouvert dans un environnement propice au bon fonctionnement de CoolParksTool. Pour installer ce dernier, il suffit maintenant :
    - de télécharger le zip de CoolParksTool depuis le dépôt GitHub : https://github.com/j3r3m1/coolparkstool/archive/refs/heads/main.zip
    - d’ouvrir le menu de gestion des librairies via “Extensions → gérer les XXX” puis sélectionner “install from zip” dans le ruban de gauche
    - de sélectionner le zip de CoolParksTool préalablement téléchargé et cliquer sur “Installer”
 
## Acknowledgements
This work has been performed within the research project CoolParks co-funded by the French Agency ADEME (grant number 1917C0002).
