import pandas as pd

# === ДАННЫЕ ВОДОЕМА SAMARKAND ЗА 2023 ГОД ===

data_2023_1 = pd.DataFrame.from_dict({
    'Date': ['01.07.2023'],
        'Place': ['Самаркандское вдхр.'],
        'Instrument': ['Сети'],
        'Instrument_size': [50],
        'Area': [0.0],
        'лещ': [217],
        'судак': [92],
        'окунь': [24],
        'плотва': [81],
        'щука': [14],
        'сазан': [1],
        'карась': [151]})

data_2023_1.insert(loc=4, column='CatchType', value='научный')
data_2023_1.loc[data_2023_1['Instrument'].str.contains('ево', na=False), 'Instrument'] = 'невод'
data_2023_1.loc[data_2023_1['Instrument'].str.contains('ет', na=False), 'Instrument'] = 'сеть'
data_2023_1.insert(loc=1, column='Year', value=2023)

 #промысловый улов
# общий улов в 2023 году
samarkand_catch_2023 = pd.concat([data_2023_1], ignore_index=True)

# Количество рыб, подвергнутых биологической обработке по возрастам
qty_treated_fish_2023 = pd.DataFrame.from_dict({
    'LessAge': ['less_2', 'less_3', 'less_4', 'less_5',
            'less_6', 'less_7', 'less_8', 'less_9', 'less_10',
            'less_11', 'less_12', 'less_13', 'less_14', 'less_15', 'less_16'],                                                         'лещ': [0, 75, 55, 37, 25, 16, 6, 3, 0, 0, 1, 1, 0, 0, 0],
'age': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
                                                            'судак': [0, 0, 41, 26, 9, 7, 4, 3, 2, 0, 1, 1, 0, 0, 0],
                                                            'окунь': [0, 13, 4, 1, 2, 1, 1, 1, 1, 0, 1, 1, 0, 0, 0],
                                                            'плотва': [0, 37, 20, 10, 4, 3, 3, 3, 1, 0, 1, 1, 0, 0, 0],
                                                            'щука': [2, 2, 4, 3, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0],
                                                            'сазан': [0, 1, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0],
                                                            'карась': [0, 0, 84, 37, 14, 9, 5, 1, 1, 0, 1, 1, 0, 0, 0]})


if __name__ == '__main__':
    print(samarkand_catch_2023.shape)
    print(samarkand_catch_2023.columns)
    print(samarkand_catch_2023[['Date', 'Year']])