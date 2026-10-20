import pandas as pd

# === ДАННЫЕ ВОДОЕМА SAMARKAND ЗА 2021 ГОД ===

data_2021_1 = pd.DataFrame.from_dict({
    'Date': ['01.07.2021'],
    'Place': ['Самаркандское вдхр.'],
    'Instrument': ['Сеть 20 - 80 мм'],
    'Instrument_size': [50],
    'Area': [0.0],
    'лещ': [295],
    'судак': [133],
    'окунь': [34],
    'плотва': [95],
    'щука': [18],
    'сазан': [1],
    'карась': [182]})

data_2021_1.insert(loc=4, column='CatchType', value='научный')
data_2021_1.loc[data_2021_1['Instrument'].str.contains('ево', na=False), 'Instrument'] = 'невод'
data_2021_1.loc[data_2021_1['Instrument'].str.contains('ет', na=False), 'Instrument'] = 'сеть'
data_2021_1.insert(loc=1, column='Year', value=2021)

 #промысловый улов
# общий улов в 2020 году
samarkand_catch_2021 = pd.concat([data_2021_1], ignore_index=True)

# Количество рыб, подвергнутых биологической обработке по возрастам
qty_treated_fish_2021 = pd.DataFrame.from_dict({
    'LessAge': ['less_2', 'less_3', 'less_4', 'less_5',
            'less_6', 'less_7', 'less_8', 'less_9', 'less_10',
            'less_11', 'less_12', 'less_13', 'less_14', 'less_15', 'less_16'],
'age': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
    'лещ': [0, 131, 77, 48, 24, 10, 3, 2, 0, 0, 1, 1, 0, 0, 0],
                                            'судак': [0, 0, 67, 31, 16, 9, 5, 3, 2, 0, 1, 1, 0, 0, 0],
                                            'окунь': [0, 16, 9, 2, 2, 2, 1, 1, 1, 0, 1, 1, 0, 0, 0],
                                            'плотва': [0, 49, 22, 9, 5, 4, 4, 1, 1, 0, 1, 1, 0, 0, 0],
                                            'щука': [9, 2, 3, 2, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0],
                                            'сазан': [0, 3, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0],
                                            'карась': [0, 0, 97, 40, 22, 12, 5, 4, 2, 0, 1, 1, 0, 0, 0]})


if __name__ == '__main__':
    print(samarkand_catch_2021.shape)
    print(samarkand_catch_2021.columns)
    print(samarkand_catch_2021[['Date', 'Year']])