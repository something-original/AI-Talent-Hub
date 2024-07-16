import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error

#среднее относительное отклонение
def relative_mean_deviation(y_pred, y_real):
    return sum([abs(a - b) for a, b in zip(y_real, y_pred)]) / sum(y_real)

#коэффициент вариации
def coefficient_of_variation(data):
    mean = np.mean(data)
    std_dev = np.std(data)
    return (std_dev / mean) * 100

#средняя абсолютная ошибка
def mean_absolute_error(actual, predicted):
    return np.mean([abs(a - p) for a, p in zip(actual, predicted)])


def print_metrics(y_actual, y_predicted):
    #среднеквадратичное отклонение
    rmse = round(np.sqrt(mean_squared_error(y_actual, y_predicted)), 2)
    #коэффициент корреляции
    corr_coef = round(np.corrcoef(y_actual, y_predicted)[0, 1], 2)
    #относительное среднее отклонение
    rmd = round(relative_mean_deviation(y_predicted, y_actual), 3)
    #коэффициент вариации
    coef_var = round(coefficient_of_variation(y_predicted), 2)
    #средняя абсолютная ошибка
    mae = round(mean_absolute_error(y_actual, y_predicted), 2)

    print(f'''
    среднеквадратическое отклонение {rmse}
    коэффициент корреляции {corr_coef}
    относительное среднее отклонение {rmd * 100}%
    коэффициент вариации {coef_var}
    средняя абсолютная ошибка {mae}
    ''')


# Функция для визуализации результатов
def visualize_results(y_test, y_pred):
    results = pd.DataFrame({'test' : y_test, 'pred' : y_pred, })
    results['diff_perc'] = [0 if p == 0 else 100 - int(t / p * 100) for p, t in zip(results.pred, results.test)]
    results = results[(results.diff_perc > - 100) & (results.diff_perc < 100)]
    mean_diff = np.mean([abs(x) for x in results.diff_perc])
    print(f'Среднее относительное отклонение: {mean_diff} %')
    print(f'Максимальное отклонение: {results.diff_perc.max()} %')
    print(f'Минимальное отклонение: {results.diff_perc.min()} %')
    plt.hist(list(results['diff_perc']), bins = 100)