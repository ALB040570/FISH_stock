import pandas as pd

# === ДАННЫЕ ВОДОЕМА SAMARKAND ЗА 2018 ГОД ===

data_2018_1 = pd.DataFrame.from_dict({
    'Date': ['01.07.2018'],
    'Place': ['Самаркандское'],
    'Instrument': ['Сети 20 -80мм'],
    'Instrument_size': [50],
'Area': [0.0],
    'лещ': [52],
    'судак': [12],
    'окунь': [6],
    'плотва': [16],
    'щука': [3],
    'сазан': [2],
    'карась': [56]
})

data_2018_1.insert(loc=4, column='CatchType', value='научный')
data_2018_1.loc[data_2018_1['Instrument'].str.contains('ево', na=False), 'Instrument'] = 'невод'
data_2018_1.loc[data_2018_1['Instrument'].str.contains('ет', na=False), 'Instrument'] = 'сеть'
data_2018_1.insert(loc=1, column='Year', value=2018)

 #промысловый улов
# общий улов в 2018 году
samarkand_catch_2018 = pd.concat([data_2018_1], ignore_index=True)

# Количество рыб, подвергнутых биологической обработке по возрастам
qty_treated_fish_2018 = pd.DataFrame.from_dict({
    'LessAge': ['less_2', 'less_3', 'less_4', 'less_5',
            'less_6', 'less_7', 'less_8', 'less_9', 'less_10',
            'less_11', 'less_12', 'less_13', 'less_14', 'less_15', 'less_16'],
'age': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
                                        'лещ': [0, 22, 14, 8, 5, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0],
                                        'судак': [0, 1, 2, 5, 2, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0],
                                        'окунь': [0,1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0],
                                        'плотва': [0, 6, 3, 3, 2, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0],
                                        'щука': [0,0,0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 0, 0],
                                        'сазан': [1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 0, 0],
                                        'карась': [0, 0, 12, 9, 10, 8, 6, 6, 5, 0, 1, 1, 1, 0, 0]})


if __name__ == '__main__':
    print(samarkand_catch_2018.shape)
    print(samarkand_catch_2018.columns)
    print(samarkand_catch_2018[['Date', 'Year']])