import pandas as pd

# === ДАННЫЕ ВОДОЕМА SAMARKAND ЗА 2020 ГОД ===

data_2020_1 = pd.DataFrame.from_dict({
    'Date': ['01.07.2020'],
     'Place': ['Самаркандское вдхр.'],
     'Instrument': ['Сети 20 -80мм'],
     'Instrument_size': [50],
    'Area': [0.0],
     'лещ': [319],
     'судак': [97],
     'окунь': [25],
     'плотва': [68],
     'щука': [14],
     'сазан': [2],
     'карась': [166]})

data_2020_1.insert(loc=4, column='CatchType', value='научный')
data_2020_1.loc[data_2020_1['Instrument'].str.contains('ево', na=False), 'Instrument'] = 'невод'
data_2020_1.loc[data_2020_1['Instrument'].str.contains('ет', na=False), 'Instrument'] = 'сеть'
data_2020_1.insert(loc=1, column='Year', value=2020)

 #промысловый улов
# общий улов в 2020 году
samarkand_catch_2020 = pd.concat([data_2020_1], ignore_index=True)

# Количество рыб, подвергнутых биологической обработке по возрастам
qty_treated_fish_2020 = pd.DataFrame.from_dict({
    'LessAge': ['less_2', 'less_3', 'less_4', 'less_5',
            'less_6', 'less_7', 'less_8', 'less_9', 'less_10',
            'less_11', 'less_12', 'less_13', 'less_14', 'less_15', 'less_16'],
'age': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
                                        'лещ': [0, 143, 83, 53, 23, 11, 5, 1, 0, 0, 1, 1, 0, 0, 0],
                                        'судак': [0, 0, 47, 23, 17, 10, 6, 5, 3, 1, 1, 1, 0, 0, 0],
                                        'окунь': [0, 11, 5, 3, 2, 1, 1, 1, 1, 0, 1, 1, 0 , 0, 0],
                                        'плотва': [0, 38, 9, 6, 5, 4, 3, 2, 1, 0, 1, 1, 0, 0, 0],
                                        'щука': [0, 6, 3, 2, 1, 1, 1, 0 , 0, 0, 1, 1, 0 , 0, 0],
                                        'сазан': [0, 1, 5, 4, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0],
                                        'карась': [0, 0, 95, 32, 19, 11, 5, 3, 1, 0, 1, 1, 0, 0, 0],})



if __name__ == '__main__':
    print(samarkand_catch_2020.shape)
    print(samarkand_catch_2020.columns)
    print(samarkand_catch_2020[['Date', 'Year']])