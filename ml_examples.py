import optuna
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score
from catboost import CatBoostRegressor
from sklearn import ensemble
from sklearn.model_selection import train_test_split, RandomizedSearchCV

test = pd.read_csv('people_houses.csv', sep = ';')

X = test[['geometry_square', 'building', 'building:levels', 'building:flats', 'landuse']]
y = test['people']

X.building = X.building.astype('category')
X['building_code'] = X.building.cat.codes
building_codes = {code : value for code, value in zip(X.building_code, X.building)}
X.landuse = X.landuse.astype('category')
X['landuse_code'] = X.landuse.cat.codes
landuse_codes = {code : value for code, value in zip(X.landuse_code, X.landuse)}
X.drop(columns = ['building', 'landuse'], inplace = True)

X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=42, shuffle=True, train_size=0.7) 


def optuna_optimize(trial):
    params = {}
    params['learning_rate'] = trial.suggest_float('learning_rate', low = 0.001, high = 0.003, step = 0.001)
    params['n_estimators'] = trial.suggest_int('n_estimators', low = 1030, high = 1070, step = 5)
    params['depth'] = trial.suggest_int('depth', low = 6, high = 10, step = 1)
    
    model = CatBoostRegressor(**params)
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    score = r2_score(y_test, y_pred)
    
    return score

study = optuna.create_study(study_name='test_study', direction = 'maximize')

model = CatBoostRegressor(**study.best_params)
model.fit(X_train, y_train)


rs_space = {
    'max_depth': list(np.arange(1, 100, step=5)) + [None],
    'n_estimators': np.arange(1, 1000, step=10),
    'max_features': ['log2', 'sqrt', 1/3, None],
    'criterion': ['absolute_error', 'squared_error', 'friedman_mse', 'poisson'],
    'min_samples_leaf': np.arange(1, 10, step=1),
    'min_samples_split': np.arange(2, 20, step=1),
    'bootstrap': [True, False]
}

people_tree1 = ensemble.RandomForestRegressor()
rand_rf = RandomizedSearchCV(
    people_tree1, rs_space, n_iter= 50, scoring = 'neg_mean_absolute_error', n_jobs=-1, cv=5
)
model_rand_rf = rand_rf.fit(X_train, y_train)
best_params = model_rand_rf.best_params_















