import pandas as pd
from collector import enrich_data, make_place_geometry, get_city_and_region_from_polygon
from utils import choose_frt_file, modify_address_to_join, merge_osm_frt


places = ['Екатеринбург', 'Пермь', 'Алапаевск', 'Верхняя Пышма', 'Нижний Тагил']
for place in places:
    print(f'Сбор данных: {place}')
    tmp_place_geometry = make_place_geometry(place)
    tmp_osm_data = enrich_data(tmp_place_geometry, only_people = False, verbose = True, cache = True)
    current_city_region = get_city_and_region_from_polygon(tmp_place_geometry)
    extra_data = choose_frt_file(current_city_region, 'frt_datasets')
    tmp_osm_data = modify_address_to_join(tmp_osm_data)
    tmp_osm_data = merge_osm_frt(df_osm = tmp_osm_data, df_frt = extra_data)
    tmp_osm_data.to_csv(f'{place}.csv', sep = ';', index = False)



def get_landuse_data(places: list) -> pd.DataFrame:
    
    full_districts_df = pd.DataFrame()
    for place_name in places:
        place_geometry = make_place_geometry(place_name)
        print(f'Загрузка данных: {place_name}')
        try:
            tmp_data_osm = enrich_data(place_geometry, verbose = True, only_people = True, cache = True)
        except KeyError as k:
            continue
        tmp_city_reg = get_city_and_region_from_polygon(place_geometry)
        tmp_extra_data = choose_frt_file(tmp_city_reg, 'frt_datasets')
        tmp_data_osm = modify_address_to_join(tmp_data_osm)
        tmp_data_osm = merge_osm_frt(df_osm = tmp_data_osm, df_frt = tmp_extra_data)
        tmp_data_osm['str_geom'] = [str(x) for x in tmp_data_osm.geometry]
        tmp = extract_districts_features(tmp_data_osm, landuse_districts, ['element_type_landuse', 'osmid_landuse'])
        tmp = tmp[~(tmp.residential.isnull()) | (tmp.landuse != 'residential')]
        tmp.residential = tmp.residential.replace(
            {'apartments' : 'urban', 'single_family' : 'rural', 'detached' : 'rural', 'gated' : 'rural'})
        full_districts_df = pd.concat([full_districts_df, tmp])
        
    return full_districts_df