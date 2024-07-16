# Функция для классификации зданий
def classify_buildings(df: gpd.GeoDataFrame, only_people: bool) -> gpd.GeoDataFrame:
       
    #определение здания по amenity и landuse
    df['building'] = df.apply(
        lambda row: 
        row['amenity'] if not check_nan(row['amenity']) 
        else row['landuse'] if not check_nan(row['landuse']) 
        and row['landuse'] not in ['non-residential', 'residential', 'allotments']
        else row['building'], axis = 1 
    )
    
    #определение частных домов
    df['building'] = df.apply(
        lambda row: 
        'house' if row['landuse'] == 'rural' or row['building'] == 'detached'
        else row['building'], axis = 1
    )
    
    #многоэтажный дом, если указано количество квартир или жилая площадь
    df['building'] = df.apply(
        lambda row: 'apartments' 
        if not check_nan(row['building:flats']) and row['building:flats'] > 0 
        or not check_nan(row['area_residential']) and row['area_residential'] > 0
        else row['building'], axis = 1
    )
     
    residential = ['house', 'detached', 'apartments', 'residential', 'dormitory', 'yes']
    
    if only_people:
        df = df[df.building.isin(residential)]
        df.residential = df.residential.apply(
            lambda x: 'urban' if x in ['apartments'] else 'rural' if x in ['gated'] else x
        )
        df.landuse = df.apply(
            lambda row: row['residential'] if not check_nan(row['residential'])
            else row['landuse'] if row['landuse'] == 'residential'
            else row['landuse'], axis = 1
        )
    
    return df

# Функция для классификации землепользования (ML)
def classify_landuse(districts: gpd.GeoDataFrame, main_df: gpd.GeoDataFrame, dataset_path: str, model_path: str) -> gpd.GeoDataFrame:
    
    ds_features = pd.read_csv(f'./{dataset_path}', sep =';')
    ds_features.landuse_people = ds_features.landuse_people.astype('category')
    ds_features['landuse_code'] = ds_features.landuse_people.cat.codes
    landuse_codes = {code : value for code, value in zip(ds_features.landuse_code, ds_features.landuse_people)}
    
    cols = ['median_levels', 'median_footprint_square', 'apartments_rate',
            'schools', 'kindergartens', 'playgrounds', 'parkings', 'building_density']
    
    if 'district_id' in districts.columns:
        index = ['district_id']
    else:
        index = ['element_type_landuse', 'osmid_landuse'] 
    
    cols += index
    districts = districts[cols]
    
    model = CatBoostClassifier()
    model.load_model(f'./{model_path}', format = 'cbm')
    pred = model.predict(districts.drop(columns = index))
    pred = pred.flatten()
    
    suffix = 'transport' if 'district_id' in districts.columns else 'landuse'
    districts[f'predicted_landuse_{suffix}'] = [landuse_codes[i] for i in pred]
    
    main_df = main_df.merge(districts[index + [f'predicted_landuse_{suffix}']], how = 'left')
    
    main_df.landuse = main_df.apply(
        lambda row: row[f'predicted_landuse_{suffix}'] if check_nan(row['landuse']) else row['landuse'], axis = 1)
    
    return main_df






