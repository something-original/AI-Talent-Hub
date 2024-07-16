# Функция, проверяющая, является ли список частью другого списка
def is_sublist(sub: list, main: list) -> bool:
    return all(elem in main for elem in sub)

# Функция, проверяющая на nan
def check_nan(obj):
    return obj != obj

# Функция для отфильтровывания букв из этажей здания
def keep_only_numbers(input_string: str) -> str:
    return ''.join(char for char in input_string if char.isdigit())

# Функция, делающая из вложенного списка одномерный 
def flatten_list(nested_list):
    
    flat_list = []
    for sublist in nested_list:
        if isinstance(sublist, list):
            flat_list.extend(flatten_list(sublist))
        else:
            flat_list.append(sublist)
            
    return flat_list

# Функция для выбора определенного файла ФРТ
def choose_frt_file(city_region: tuple, folder: str) -> pd.DataFrame:
    
    city_name = city_region[0]
    region_name = city_region[1]
    files = os.listdir(folder)
     
    region_csv = str([file for file in files if region_name in file][0])

    frt_data = pd.read_csv(f'./{folder}/{region_csv}', sep = ',', low_memory = False)
    frt_data = frt_data[frt_data.formalname_city == city_name]
    
    changes = {'formalname_street' : 'addr:street', 'house_number' : 'addr:housenumber', 'building' : 'building_index'}
    frt_data = frt_data.rename(columns = changes)
    return frt_data

# Функция, удаляющая сокращения в адресах
def remove_shortnames(shortname: str, x: list) -> str:
    result = next((item for item in x if shortname in str(item)), '')
    return result.replace(shortname, '')

# Функция, модифицирующая адрес для соединения
def modify_address_to_join(df: pd.DataFrame) -> pd.DataFrame:
        
    df['addr:street'] = df['addr:street'].fillna('-')
    #удаление лишних пробелов
    df['addr:street'] = df['addr:street'].apply(lambda x: ' '.join(x.split()))
    df['addr:street'] = df['addr:street'].str.replace('ё', 'е')
    df['addr:street'] = df['addr:street'].apply(lambda x: x.split(' ') if x != '-' else x)
    df['street_type'] = df['addr:street'].progress_apply(
        lambda x: x if x == '-' else [elem for elem in x if elem[0].islower()]
    )
    
    df['addr:street'] = df.apply(lambda row: 
        [item for item in row['addr:street'] if item not in row['street_type']], axis = 1
    )
    df['street_type'] = df['street_type'].apply(lambda x: '-' if check_nan(x) or len(x) == 0 else x[0])
    df['addr:street'] = df['addr:street'].apply(lambda x: " ".join(x))
    changes = {'пер' : 'переулок', 'ул' : 'улица', 'мкр' : 'микрорайон', 'пл' : 'площадь',
               'тер' : 'территория', 'пр-кт' : 'проспект', 'пр' : 'проспект', 'пр-д' : 'проезд'}
    
    df['street_type'] = df['street_type'].apply(lambda x: x.replace('.', ''))
    df['street_type'] = df['street_type'].apply(lambda x: changes[x] if x in changes.keys() else x)
    
    df['addr:housenumber'] = df['addr:housenumber'].fillna('-')
    df['addr:housenumber'] = df['addr:housenumber'].apply(lambda x: x.split(' ') if x != '-' else x)
    df['number'] = df['addr:housenumber'].apply(lambda x: x[0])
    df['block'] = df['addr:housenumber'].apply(lambda x: remove_shortnames('к', x))
    df['building_index'] = df['addr:housenumber'].apply(lambda x: remove_shortnames('с', x))
    df['letter'] = df['addr:housenumber'].apply(lambda x: remove_shortnames('лит', x))
    
    df['num_indexes'] = df.groupby(['addr:street', 'number', 'block'])['letter'].transform('count')
    df['letter'] = df.apply(lambda row: '' if row['num_indexes'] == 1.0 else row['letter'], axis = 1)
    
    df.drop(columns = ['addr:housenumber', 'num_indexes'], inplace = True)
    df.rename(columns = {'number' : 'addr:housenumber'}, inplace = True)
    
    return df

# Функция, соединяющая данные из ФРТ и OSM
def merge_osm_frt(df_osm: pd.DataFrame, df_frt: pd.DataFrame) -> pd.DataFrame:
        
    cols = ['addr:street', 'addr:housenumber', 'building_index', 
            'block', 'letter', 'floor_count_max', 'living_quarters_count', 'area_residential']
    
    merge_on = ['addr:street', 'addr:housenumber']
    df_osm = df_osm.merge(df_frt[cols], how = 'left', on = merge_on)
    
    df_osm['floor_count_max'] = df_osm.apply(
        lambda row: row['building:levels'] if check_nan(row['floor_count_max']) else row['floor_count_max'], axis = 1)
    df_osm['floor_count_max'] = df_osm.apply(
        lambda row: 1 if row['building'] == 'house' else row['floor_count_max'], axis = 1)
    df_osm['floor_count_max'] = [validate_levels(l) if not check_nan(l) else l for l in df_osm['floor_count_max']]
    df_osm.drop_duplicates(subset = ['element_type', 'osmid'], inplace = True)
    
    df_osm['building:levels'] = df_osm.apply(
        lambda row: row['building:levels'] if not check_nan(row['building:levels']) else row['floor_count_max'], axis = 1
    )
    df_osm['building:flats'] = df_osm.apply(
        lambda row: row['building:flats'] if check_nan(row['living_quarters_count']) or row['living_quarters_count'] == 0 
        else row['living_quarters_count'], axis = 1
    )
    df_osm.drop(columns = ['living_quarters_count', 'floor_count_max'], inplace = True)
    df_osm.rename(columns = {'block_x': 'block', 'building_index_y': 'building_index', 'letter_y':'letter'}, inplace = True)
    
    df_osm['building:flats'] = df_osm['building:flats'].replace('?', 1)
    df_osm['area_residential'] = df_osm['area_residential'].replace('', 0)
    
    df_osm = df_osm[~df_osm.osmid.apply(check_nan)]
    df_osm.osmid = df_osm.osmid.apply(lambda x: str(x).replace('.0', ''))
    
    df_osm['area_residential'] = df_osm['area_residential'].apply(
        lambda x: x if type(x) == float else float(x.replace(',', '.')))
    
    cols = [column for column in df_osm.columns if all(['index' not in column, 'letter' not in column, 'block' not in column])]
    df_osm = df_osm[cols]
    
    return df_osm

# Функция для выделения признаков сформированных районов
def extract_districts_features(main_df: gpd.GeoDataFrame, district_df: gpd.GeoDataFrame, groupby: Union[list, str]) -> gpd.GeoDataFrame:
    
    tmp = main_df.copy()
    cols = ['building', 'building:levels', 'footprint_square']
    
    if type(groupby) == str:
        cols += [groupby]
    else:
        cols += groupby
    
    tmp = district_df.merge(tmp[cols], on = groupby, how = 'right')
    tmp['geometry'] = tmp.geometry.apply(lambda x: str(x))
    
    if type(groupby) == list:
        landuse = pd.DataFrame(
            tmp.groupby(groupby).agg(
                landuse = ('landuse', 'first'),
                residential = ('residential', 'first')
            )
        ).reset_index().drop(columns = ['osmid_landuse', 'element_type_landuse'])

    tmp = gpd.GeoDataFrame(
        tmp.groupby(groupby).agg(
            geometry = ('geometry', 'first'),
            parkings = ('parkings', 'first'),
            playgrounds = ('playgrounds', 'first'),
            kindergartens = ('kindergartens', 'first'),
            schools = ('schools', 'first'),
            district_square_km2 = ('district_square_km2', 'first'),
            median_levels = ('building:levels', np.median),
            median_footprint_square = ('footprint_square', np.median),
            total_buildings = ('building', 'count'),
            apartments_number = ('building', lambda x: x.str.contains('apartments').sum())
        )
    ).reset_index()
    
    if type(groupby) == list:
        tmp = pd.concat([tmp, landuse], axis = 1)
    
    tmp.geometry = tmp.geometry.apply(lambda x: wkt.loads(x))
    tmp = gpd.GeoDataFrame(tmp).set_geometry('geometry').set_crs('EPSG:4326')
    
    tmp['building_density'] = tmp.apply(
        lambda row: -1 if row['district_square_km2'] == 0 else row['total_buildings'] / row['district_square_km2'], axis=1)
    tmp['median_levels'].fillna(0, inplace = True)
    tmp['apartments_rate'] = tmp.apply(
        lambda row: 0 if row['total_buildings'] == 0 else round(row['apartments_number'] / row['total_buildings'], 2), axis=1
    )
    to_drop = ['total_buildings', 'district_square_km2', 'apartments_number']
    tmp.drop(columns = to_drop, inplace = True)
    
    cols = list(set(tmp.columns))
    tmp = tmp[cols]
    
    return tmp









