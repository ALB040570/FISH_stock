import pandas as pd

# === ДАННЫЕ ВОДОЕМА SAMARKAND ЗА 2024 ГОД ===

data_2024_1 = pd.DataFrame.from_dict({
        'Date': ['01.07.2024'],
        'Place': ['Самаркандское вдхр.'],
        'Instrument': ['Сети'],
        'Instrument_size': [50],
        'Area': [0.0],
        'лещ': [22],
        'судак': [4],
        'окунь': [31],
        'плотва': [31],
        'щука': [1]})

data_2024_1.insert(loc=4, column='CatchType', value='научный')
data_2024_1.loc[data_2024_1['Instrument'].str.contains('ево', na=False), 'Instrument'] = 'невод'
data_2024_1.loc[data_2024_1['Instrument'].str.contains('ет', na=False), 'Instrument'] = 'сеть'
data_2024_1.insert(loc=1, column='Year', value=2024)

 #промысловый улов
# общий улов в 2024 году
samarkand_catch_2024 = pd.concat([data_2024_1], ignore_index=True)

# Количество рыб, подвергнутых биологической обработке по возрастам
qty_treated_fish_2024 = pd.DataFrame.from_dict({
    'LessAge': ['less_2', 'less_3', 'less_4', 'less_5',
            'less_6', 'less_7', 'less_8', 'less_9', 'less_10',
            'less_11', 'less_12', 'less_13', 'less_14', 'less_15', 'less_16'],
'age': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
    'лещ': [0, 0, 18, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0],
                                                            'судак': [0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0],
                                                            'окунь': [0, 0, 6, 5, 5, 5, 4, 3, 3, 0, 1, 1, 0, 0, 0],
                                                            'плотва': [37, 20, 10, 4, 3, 3, 3, 1, 0, 0, 1, 1, 0, 0, 0],
                                                            'щука': [0, 0, 2, 12, 6, 5, 3, 3, 0, 0, 1, 1, 0, 0, 0]})


if __name__ == '__main__':
    print(samarkand_catch_2024.shape)
    print(samarkand_catch_2024.columns)
    print(samarkand_catch_2024[['Date', 'Year']])