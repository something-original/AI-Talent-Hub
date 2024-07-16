
import geopandas as gpd
import numpy as np
import pandas as pd
from typing import Union

# Функция для получения корректного числа этажей в здании (также используется для коррекции квартир в здании)
def validate_levels(levels: Union[str, float]) -> int:
    
    if check_nan(levels):
        levels = 0
        
    if isinstance(levels, str):
        if levels.isnumeric():
            levels = int(levels)
        elif any([';' in levels, '-' in levels, ', ' in levels]):
            levels = levels.replace(';', '*').replace('-', '*').replace(', ', '*')
            levels = levels.split('*')
            if '' in levels:
                levels.remove('')
            levels = list(map(lambda x: int(keep_only_numbers(x)), levels))
            levels = int(round(np.mean(levels), 0))
        elif any([',' in levels, '.' in levels]):
            levels = levels.replace(',', '.')
            levels = int(round(float(levels), 0))
        else:
            levels = keep_only_numbers(levels)
            if levels == '':
                levels = 1
            levels = int(levels)
            
    if isinstance(levels, float):
        levels = int(round(levels, 0))
        
    return levels

# Функция для предподготовки датафрейма со зданиями
def building_df_preprocess(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    
    df = df.reset_index()
    df.drop_duplicates(inplace = True, subset = ['element_type', 'osmid'])
    df = df[df.element_type.isin(['way', 'relation'])]
    
    if 'building:levels' in df.columns:
        df['building:levels'] = [validate_levels(l) for l in df['building:levels']]
    if 'building:flats' in df.columns:
        df['building:flats'] = [validate_levels(f) for f in df['building:flats']]
    else:
        df['building:flats'] = 0
            
    columns = [column for column in columns if column in df.columns]
    df = df[columns]
    
    return df

# Функция для модификации датафреймов
def modify_dataframes(dataframes: dict, columns: list) -> dict:
    
    extra_dfs = {}
    
    for k in dataframes.keys():
        
        df = dataframes[k]
        if k == 'building':
            df = building_df_preprocess(df, columns)
        else:
            df = df.reset_index()
            df = gpd.GeoDataFrame(df)
        if k not in ['building', 'landuse', 'amenity']:
            df = df[['geometry', k]]
        if k == 'landuse':
            df = df[['element_type', 'osmid', 'geometry', 'landuse', 'residential']]
        if k == 'amenity':
            df = df[['geometry', 'element_type', 'amenity']]
            extra_dfs['parkings'] = df[df.amenity == 'parking'][['geometry']]            
            extra_dfs['amenity_point'] = df[df.element_type == 'node'][['geometry', 'amenity']]
            extra_dfs['amenity_point'].rename(columns = {'amenity' : 'amenity_point'}, inplace = True)
            df = df[df.element_type != 'node'][['geometry', 'amenity']]
        if k == 'leisure':
            extra_dfs['playgrounds'] = df[df.leisure == 'playground'][['geometry']]
            
        dataframes[k] = df
    
    dataframes = {**dataframes, **extra_dfs}
    return dataframes

# Вспомогательная функция, которая возвращает все точки внутри здания
def points_inside_building(dataframes: dict, df_buildings: gpd.GeoDataFrame, cols: list) -> gpd.GeoDataFrame:
    
    for k in dataframes.keys():
        if k not in ['building', 'landuse', 'amenity', 'playgrounds', 'parkings']:
            df_buildings = df_buildings.sjoin(dataframes[k], how='left')
            indexes = [column for column in df_buildings.columns if column in ['index', 'index_right', 'index_left']]
            df_buildings.drop(columns=indexes, inplace=True)
            tmp = df_buildings.groupby(['element_type', 'osmid'])[k].agg(
                lambda x: x.tolist()).reset_index()
            df_buildings = df_buildings.merge(tmp, how='left', on=['element_type', 'osmid'])
            df_buildings.drop(columns=[f'{k}_x'], inplace=True)
            df_buildings.rename(columns = {f'{k}_y' : f'{k}'}, inplace=True)
            df_buildings.drop_duplicates(subset=['element_type', 'osmid'], inplace = True)
            df_buildings = gpd.GeoDataFrame(df_buildings).set_geometry('geometry').set_crs('EPSG:4326')

    extra_columns = [column for column in df_buildings.columns if column not in cols]
    points = df_buildings[extra_columns].copy()
    cols = [col for col in cols if col in df_buildings.columns]
    df_buildings = df_buildings[cols]

    points = points.progress_apply(
        lambda row: flatten_list([row[col] for col in extra_columns if not check_nan(row[col])]), axis=1)
    df_buildings['points_inside'] = points
    df_buildings.points_inside = df_buildings.points_inside.apply(lambda x: [i for i in x if type(i) != int])
    df_buildings.points_inside = df_buildings.points_inside.apply(
        lambda x: [elem for elem in x if type(elem) == str and elem != 'yes'])

    return df_buildings

# Функция, соединяющая транспортные районы и фичи
def join_districts_parkings_playgrounds(districts: gpd.GeoDataFrame, group_by: Union[list, str]) -> gpd.GeoDataFrame:
    
    districts = districts.sjoin(dataframes['parkings'], how = 'left', rsuffix = 'parking')
    districts = districts.sjoin(dataframes['playgrounds'], how = 'left', rsuffix = 'playground')
    schools = dataframes['amenity'][dataframes['amenity'].amenity == 'school'][['geometry']]
    kindergartens = dataframes['amenity'][dataframes['amenity'].amenity == 'kindergarten'][['geometry']]
    districts = districts.sjoin(schools, how = 'left', rsuffix = 'school')
    districts = districts.sjoin(kindergartens, how = 'left', rsuffix = 'kindergarten')
    
    if is_sublist(['landuse', 'residential'], districts.columns):
        districts = gpd.GeoDataFrame(
            districts.groupby(group_by).agg(
                parkings = ('index_parking', 'nunique'),
                playgrounds = ('index_playground', 'nunique'),
                geometry = ('geometry', 'first'),
                landuse = ('landuse', 'first'),
                residential = ('residential', 'first'),
                kindergartens = ('index_kindergarten', 'nunique'),
                schools = ('index_school', 'nunique')
            )
        )
        
    else:
        districts = gpd.GeoDataFrame(
            districts.groupby(group_by).agg(
                parkings = ('index_parking', 'nunique'),
                playgrounds = ('index_playground', 'nunique'),
                geometry = ('geometry', 'first'),
                kindergartens = ('index_kindergarten', 'nunique'),
                schools = ('index_school', 'nunique')
            )
        )
    
    districts = districts.reset_index().set_geometry('geometry').set_crs('EPSG:4326')
    
    return districts

