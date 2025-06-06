# CoolParksTool

**A version for the Processing Toolbox in QGIS**

This is the official repository for the CoolParksTool.
It summarizes the results of the research project called CoolParks. 
The user provides park boundaries, type of ground within the park, 
type of canopy within the park and meteorological conditions. 
As output the cooling effect of the park on its surrounding built-up area 
is calculated as well as its impact on building energy consumption and building
 indoor thermal comfort

## Description

Vous trouverez une [vidéo](https://github.com/j3r3m1/coolparkstool/blob/main/Presentations/video_presentation.mp4) et un [support de présentation](https://github.com/j3r3m1/coolparkstool/blob/main/Presentations/10h15-10h30_Presentation_CoolParksTool.pdf) de l'outil CoolParksTool.

## Installation

### Pré-requis
Comme [GeoClimate](https://github.com/orbisgis/geoclimate) ou le module [URock de UMEP](https://umep-docs.readthedocs.io/en/latest/processor/Wind%20model%20URock.html), CoolParksTool utilise pour une grande partie de ses calculs le système de gestion de bases de données spatiales [H2GIS](https://github.com/orbisgis/h2gis).

Ce système reposant sur Java, il est nécessaire que votre ordinateur dispose d'une installation du logiciel Java relativement récente (>=8):
- pour windows: https://java.com/en/download/windows_manual.jsp
- pour linux: https://java.com/en/download/
- pour macOS: https://www.java.com/en/download/apple.jsp

### Créer un environnement propice à l’installation de CoolParksTool

Il est tout d'abord nécessaire de créer un environnement propice à l'installation de CoolParksTool. Pour cela, 2 solutions sont possibles :
- **Vous avez un environnement Windows**, il est préférable de préalablement installer le programme qui s’appelle osgeo4W (https://trac.osgeo.org/osgeo4w/).
- **Vous avez un environnement Linux ou MacOS** ou vous avez Windows mais ne souhaitez pas utiliser osgeo4w, il est recommandé de préalablement utiliser le programme qui s’appelle Anaconda (https://anaconda.org/).

#### Vous avez un environnement Windows
Il est recommandé d'installer osgeo4W. Ce programme permet de gérer l’installation de librairies python dans un environnement dédié dans lequel un certain nombre de librairies utilisées par QGIS sont préinstallées. 

Pour l’utiliser :
- télécharger l’installateur: https://download.osgeo.org/osgeo4w/v2/osgeo4w-setup.exe
- lancer le une première fois en sélectionnant “install express”. Cocher QGIS, QGIS LTR, GDAL et GRASS
- à la fin de l’installation, il est nécessaire d’installer d’autres librairies. Pour cela, relancer l’installateur (osgeo4W-setup) mais cette fois ci sélectionner “advanced installation”. Cliquer sur suivant jusqu'à arriver à une fenêtre où il est possible de filtrer et sélectionner des librairies. Trois librairies doivent ensuite être installées : shapely, geopandas et statsmodels. Pour cela :
    - rechercher les dans la barre de recherche  : entrer le nom mais inutile de taper entrer ensuite, il s’agit simplement de cliquer sur le + qui permet d’afficher les résultats de la recherche
    - l’installer si nécessaire : si aucune version de la librairie recherchée n’est installée, il faut cliquer une seule fois sur la ligne correspondant à la librairie à installer. Si une version est affichée, cela signifie que la librairie est déjà installer, aucune action n’est nécessaire. Réitérer ces deux derniers points pour chaque librairie à installer.
- Enfin, 2 autres librairies sont à installer en-dehors de l’installateur d’osgeo4W. Elles doivent cependant être installées dans le même environnement. Pour cela, il faut cette fois ci lancer le “shell osgeo4W”. Une fois lancé, il faut installer les librairies via pip :
    - pip install unidecode
    - pip install jaydebeapi

#### Vous avez un environnement Linux ou MacOS
Si vous ne souhaitez pas installer osgeo4W ou que vous utilisez un système d'exploitation linux ou MacOS, il est recommandé d'installer Anaconda. Il permet de gérer l’installation de librairies Python via la création d’environnements dédiés à un besoin donné. Il permet également de s’assurer de l’intercompatibilité des librairies entre elles dans un environnement donné. 

Pour l’utiliser :
- suiver les recommandations d'installation relatives à votre système d'exploitation : https://docs.anaconda.com/free/anaconda/install
- il s’agit maintenant de créer un nouvel environnement dédié à l’utilisation de CoolParksTool et d’installer les librairies nécessaires à son fonctionnement dans cet environnement. Pour cela :
    - ouvrez un terminal
    - créez un nouvel environnement : conda create --name coolparks
    - activez cet environnement : conda activate coolparks
    - ajoutez une nouvelle source de librairies d’où anaconda pourra télécharger des librairies : conda config --add channels conda-forge
    - installez les librairies (cela peut prendre un temps considérable de gérer les dépendances) : conda install gdal qgis=3.28.3 shapely geopandas unidecode statsmodels jaydebeapi
    - lancez QGIS via le terminal en tapant : qgis

### Installer CoolParksTool
Quelle que soit la solution choisie, vous devez maintenant avoir QGIS ouvert dans un environnement propice au bon fonctionnement de CoolParksTool. Pour installer ce dernier, deux solutions existent:
#### Installer la dernière version disponible sur le dépôt GitHub
C'est la dernière version du code qui n'a peut-être pas encore été envoyée dans les dépôts de QGIS. Elle n'est peut-être pas parfaitement fonctionnelle mais règle des problèmes rencontrés par les précédentes versions. C'est la version recommandée. Pour l'installer, télécharger [le zip du projet](https://github.com/j3r3m1/coolparkstool/archive/refs/heads/main.zip) puis:
- de lancer QGIS, d'ouvrir la fenêtre "Installer/Gérer les extensions" du menu "Extensions".
- Sélectionner "Installer depuis un zip" dans le ruban de gauche puis sélectionner le zip que vous avez téléchargé et installer le.
- un message sur fond vers vous informant du succès de l'installation doit normalement apparaître temporairement. Lorsque vous ouvrez la boîte à outil de QGIS, le plug-in CoolParks tool doit maintenant apparaître (cf. Figure ci-dessous)

#### Installer la dernière version proposée par QGIS
Il suffit :
- de lancer QGIS, d'ouvrir la fenêtre "Installer/Gérer les extensions" du menu "Extensions".
- dans "Paramètres" (ruban de droite de la fenêtre), cocher la case "Afficher les extensions expérimentales". Vous pouvez maintenant rechercher puis sélectionner "coolparkstool" puis cliquer sur "Installer le plugin".
- un message sur fond vers vous informant du succès de l'installation doit normalement apparaître temporairement. Lorsque vous ouvrez la boîte à outil de QGIS, le plug-in CoolParks tool doit maintenant apparaître (cf. Figure ci-dessous)

![image](https://github.com/j3r3m1/coolparkstool/assets/13120405/20b24f01-5c53-48ae-91ba-0c8884f7d78f)

## Utilisation
Une fois installé, CoolParksTool est prêt à être utilisé. Il vous faut maintenant préparer les données géographiques (4 couches SIG) et météorologiques (un fichier météo) nécessaires à son fonctionnement. Il n'existe pour l'instant pas de méthodologie de mise en oeuvre "Pas à pas". Cependant, vous pouvez :
- vous reporter au [rapport final de CoolParks](https://librairie.ademe.fr/6997-projet-de-recherche-coolparks.html) et plus spécifiquement la section dédiée au plug-in (section 5 - p. 96) dans lequel :
    - les fichiers d'entrée et de sortie du plug-in sont décrits,
    - le fonctionnement de l'outil est décrit.
- télécharger le [jeu de données test](https://github.com/j3r3m1/coolparkstool/tree/main/test/data/cas_atelier) :
    - couches SIG décrivant la géographie du parc et son environnement :
        - "SIG-données15parcs/limites_parcs.geojson" : fichier identifiant les limites du parc
        - "SIG-données15parcs/Cas 0/cas_0_batiments.geojson" : les bâtiments alentour au parc
        - "SIG-données15parcs/Cas 0/cas_0_couverture_arboree.geojson" : la description de la couverture arborée du parc
        - "SIG-données15parcs/Cas 0/cas_0_couverture_sol.geojson" : la description de la couverture du sol
    - fichier Météo issu du site [Shinyweather](https://www.shinyweatherdata.com/) : "Donnees_meteo.csv"

 
## Acknowledgements
This work has been performed within the research project CoolParks co-funded by the French Agency ADEME (grant number 1917C0002).
