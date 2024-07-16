import osmnx as ox
import os
import geopandas as gpd
import requests
from shapely.geometry import Polygon, Point, MultiPolygon
import pandas as pd
from shapely import wkt, polygonize
from typing import Union
from shapely.validation import make_valid


# Функция для получения полигонов по названию
def get_polygons(location_name: str) -> dict:
    
    base_url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-agent': 'Firefox/47.0'}
    params = {
        "q": location_name,
        "format": "json",
        "polygon_geojson": 1
    }

    response = requests.get(base_url, headers = headers, params=params)
    print(f'status code: {response.status_code}')
    
    return response.json() if response.status_code == 200 else {}

# Получение списка полигонов по вхродным координатам
def make_place_geometry(place_input: Union[str, list, tuple, Polygon, MultiPolygon]) -> Polygon:

    if isinstance(place_input, str):
        polygon_list = get_polygons(place_input)

        for i, item in enumerate(polygon_list):
            name = item['display_name']
            place_type = item['geojson']['type']
            if 'Россия' in item['display_name']:
                print(f'{i} ({place_type}) {name}')

        num = int(input())

        place_type = polygon_list[num]['geojson']['type']
        place_coords = polygon_list[num]['geojson']['coordinates']

        if place_type == 'MultiPolygon':
            polygons = [Polygon(place_coords[i][0]) for i in range(0, len(place_coords))]
            place_geometry = MultiPolygon(polygons)
                   
        elif place_type == 'Polygon':
            place_geometry = Polygon(place_coords[0])
                   
        else:
            print(f'Населенный пункт {place_input} не представлен в виде полигона')
            
    if isinstance(place_input, list):
        #north, south, west, east
        point_nw = Point(place_input[2], place_input[0])
        point_ne = Point(place_input[3], place_input[0])
        point_se = Point(place_input[3], place_input[1])
        point_sw = Point(place_input[2], place_input[1])
        place_geometry = Polygon([point_nw, point_ne, point_se, point_sw, point_nw])
    
    if isinstance(place_input, tuple):
        place_geometry = Polygon(place_input)

    if type(place_input) in [Polygon, MultiPolygon]:
        place_geometry = place_input
        
    place_geometry = make_valid(place_geometry)
    
    return place_geometry

# Основная функция для получения данных из OSM
def enrich_data(input_polygon: Union[Polygon, MultiPolygon, str], verbose: bool, only_people: bool, cache: bool) -> pd.DataFrame:
    
    ox.settings.use_cache = cache
    global dataframes
    global transport_districts
    global landuse_districts
    
    dataframes = {}
    transport_districts = None
    
    tags = ['building', 'amenity', 'landuse', 'shop', 'craft', 'emergency', 
            'leisure', 'office', 'industrial', 'tourism']
    
    if type(input_polygon) == str:
        input_polygon = wkt.loads(input_polygon)
    if not input_polygon.is_valid:
        input_polygon = make_valid(input_polygon)
    
    for tag in tags:
        try:
            dataframes[f'{tag}'] = ox.features_from_polygon(input_polygon, {tag: True})
            if verbose:
                print(f'{tag} successful')
        except InsufficientResponseError as e:
            if verbose:
                print(f'{tag} unsuccessful')
            continue
    
    dataframes = {k: v for k, v in dataframes.items() if len(v) > 0}
    
    cols = ['element_type', 'osmid', 'building', 'geometry', 'footprint_square',
            'addr:street', 'addr:housenumber', 'building:levels', 'building:flats']
    
    dataframes = modify_dataframes(dataframes, cols)
    main_df = dataframes['building']
    main_df = count_square(main_df).rename(columns = {'geometry_square': 'footprint_square'})
    
    landuse_districts = join_districts_parkings_playgrounds(dataframes['landuse'], ['element_type', 'osmid'])
    landuse_districts = count_square(landuse_districts).rename(columns = {'geometry_square': 'district_square_km2'})
    landuse_districts.district_square_km2 = landuse_districts.district_square_km2.apply(lambda x: round(x / (10 ** 6), 2))
    
    transport_districts = get_transport_districts_features(input_polygon)
    main_df = main_df.sjoin(dataframes['amenity'], how='left').drop(columns=['index_right'])
    cols += ['amenity']
    main_df = points_inside_building(dataframes, main_df, cols)    
     
    residential = ['house', 'detached', 'apartments', 'residential', 'dormitory', 'terrace', 'yes']
    if only_people:
        main_df = main_df[main_df.building.isin(residential)]
        
    main_df = main_df.sjoin(
        landuse_districts[['geometry', 'landuse', 'residential', 'element_type', 'osmid']], how = 'left', rsuffix = 'landuse'
    ).drop(columns = ['index_landuse']).rename(columns = {'element_type_left': 'element_type', 'osmid_left' : 'osmid'})
    
    main_df = main_df.sjoin(transport_districts[['geometry', 'district_id']], how = 'left').drop(columns = ['index_right'])
    landuse_districts.rename(columns = {'element_type': 'element_type_landuse', 'osmid': 'osmid_landuse'}, inplace = True)
    
    return main_df

# Функция для получения города и региона по полигону
def get_city_and_region_from_polygon(polygon: Union[Polygon, MultiPolygon]) -> tuple:
    
    city, region = None, None
    c = polygon.centroid
    r = requests.get(f'https://overpass-api.de/api/interpreter?data=[out:json];%20is_in({c.y},%20{c.x});%20out;').json()

    for elem in r['elements']:
        if elem['type'] == 'area' and 'admin_level' in elem['tags'].keys():
            if elem['tags']['admin_level'] == '4':
                region = elem['tags']['name']
        elif elem['type'] == 'area' and 'place' in elem['tags'].keys():
            city = elem['tags']['name']    
    
    if city != None and ' ' in city:
        city = city.split(' ')
        city = [word.replace('«', '').replace('»', '') for word in city]
        city = ' '.join([word for word in city if word[0].isupper() and word != "Городской"])
        
    if region != None and ' ' in region:
        region = region.split(' ')
        region = [word.replace('«', '').replace('»', '') for word in region]
        region = ' '.join([word for word in region if word[0].isupper() and word != "Республика"])

    return (city, region)



    
    city_name = city_region[0]
    region_name = city_region[1]
    files = os.listdir(folder)
     
    region_csv = str([file for file in files if region_name in file][0])

    frt_data = pd.read_csv(f'./{folder}/{region_csv}', sep = ',', low_memory = False)
    frt_data = frt_data[frt_data.formalname_city == city_name]
    
    changes = {'formalname_street' : 'addr:street', 'house_number' : 'addr:housenumber', 'building' : 'building_index'}
    frt_data = frt_data.rename(columns = changes)
    return frt_data

# Функция для разбиения города на транспортные районы
def make_transport_districts(polygon: Polygon) -> gpd.GeoDataFrame:
    
    graph = ox.graph_from_polygon(polygon, network_type='all')
    edges = ox.graph_to_gdfs(graph, nodes=False, edges=True)
    
    edges = edges.explode('highway')
    main_roads = ['primary', 'secondary', 'tertiary', 'residential', 'unclassified']
    edges = edges[edges.highway.isin(main_roads)]
    roads_geometry = edges.unary_union
    decomposition = polygonize(roads_geometry.geoms)
    polygons = gpd.GeoDataFrame({'geometry': decomposition.geoms})
    polygons = polygons.set_crs('EPSG:4326')
    
    polygons['district_id'] = polygons.index
    
    return polygons








