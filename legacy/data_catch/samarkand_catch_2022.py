import pandas as pd

# === ДАННЫЕ ВОДОЕМА SAMARKAND ЗА 2022 ГОД ===

data_2022_1 = pd.DataFrame.from_dict({
    'Date': ['01.07.2022'],
    'Place': ['Самаркандское вдхр.'],
    'Instrument': ['Сети'],
    'Instrument_size': [50],
'Area': [0.0],
    'лещ': [209],
    'судак': [97],
    'окунь': [28],
    'плотва': [80],
    'щука': [16],
    'сазан': [2],
    'карась': [148]})

data_2022_1.insert(loc=4, column='CatchType', value='научный')
data_2022_1.loc[data_2022_1['Instrument'].str.contains('ево', na=False), 'Instrument'] = 'невод'
data_2022_1.loc[data_2022_1['Instrument'].str.contains('ет', na=False), 'Instrument'] = 'сеть'
data_2022_1.insert(loc=1, column='Year', value=2022)

 #промысловый улов
# общий улов в 2020 году
samarkand_catch_2022 = pd.concat([data_2022_1], ignore_index=True)

# Количество рыб, подвергнутых биологической обработке по возрастам
qty_treated_fish_2022 = pd.DataFrame.from_dict({
    'LessAge': ['less_2', 'less_3', 'less_4', 'less_5',
            'less_6', 'less_7', 'less_8', 'less_9', 'less_10',
            'less_11', 'less_12', 'less_13', 'less_14', 'less_15', 'less_16'],
'age': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
    'лещ': [0, 88, 50, 35, 20, 10, 5, 1, 0, 0, 1, 1, 1, 1, 0],
                                                'судак': [0, 0, 48, 25, 10, 7, 4, 2, 1, 0, 1, 1, 1, 1, 0],
                                                'окунь': [0, 17, 5, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 0],
                                                'плотва': [0, 42, 19, 7, 4, 3, 2, 2, 1, 0, 1, 1, 1, 1, 0],
                                                'щука': [3, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0],
                                                'сазан': [0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0],
                                                'карась': [0, 0, 78, 33, 20, 9, 4, 3, 1, 0, 1, 1, 1, 1, 0]})


if __name__ == '__main__':
    print(samarkand_catch_2022.shape)
    print(samarkand_catch_2022.columns)
    print(samarkand_catch_2022[['Date', 'Year']])