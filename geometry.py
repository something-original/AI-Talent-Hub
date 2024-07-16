import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import make_valid
from math import cos, radians


# Функция для подсчета площади для объектов в датафрейме
# Считаем, что косинус не меняется в пределах местности
def count_square(dataframe: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    
    geom = dataframe.geometry[dataframe.geometry.apply(lambda x: type(x) in [Polygon, MultiPolygon])].iloc[0]
    cosine = cos(radians(geom.centroid.y))
    
    if dataframe.geometry.crs.to_epsg() != 3857:
        dataframe.geometry = dataframe.geometry.set_crs('EPSG:4326').to_crs('EPSG:3857')

    dataframe['geometry_square'] = dataframe.geometry.apply(
        lambda x: 0 if type(x) not in [Polygon, MultiPolygon] else make_valid(x).area * (cosine ** 2) 
    )
    dataframe.geometry = dataframe.geometry.set_crs('EPSG:3857').to_crs('EPSG:4326')
    
    return dataframe