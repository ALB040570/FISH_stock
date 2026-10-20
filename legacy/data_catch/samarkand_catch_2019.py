import pandas as pd

# === ДАННЫЕ ВОДОЕМА SAMARKAND ЗА 2019 ГОД ===

data_2019_1 = pd.DataFrame.from_dict({
            'Date': ['01.07.2019'],
            'Place': ['Самаркандское вдхр.'],
            'Instrument': ['Сети 20 -80мм'],
            'Instrument_size': [50],
    'Area': [0.0],
            'лещ': [273],
            'судак': [40],
            'окунь': [87],
            'плотва': [51],
            'щука': [4],
            'сазан': [11],
            'карась': [383]})

data_2019_1.insert(loc=4, column='CatchType', value='научный')
data_2019_1.loc[data_2019_1['Instrument'].str.contains('ево', na=False), 'Instrument'] = 'невод'
data_2019_1.loc[data_2019_1['Instrument'].str.contains('ет', na=False), 'Instrument'] = 'сеть'
data_2019_1.insert(loc=1, column='Year', value=2019)

 #промысловый улов
# общий улов в 2019 году
samarkand_catch_2019 = pd.concat([data_2019_1], ignore_index=True)

# Количество рыб, подвергнутых биологической обработке по возрастам
qty_treated_fish_2019 = pd.DataFrame.from_dict({
    'LessAge': ['less_2', 'less_3', 'less_4', 'less_5',
            'less_6', 'less_7', 'less_8', 'less_9', 'less_10',
            'less_11', 'less_12', 'less_13', 'less_14', 'less_15', 'less_16'],
'age': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
                                        'лещ': [0, 115, 72, 48, 24, 9, 4, 1, 0, 0, 1, 1, 1, 1, 0],
                                        'судак': [0, 0, 10, 8, 6, 6, 5, 4, 1, 0, 1, 1, 1, 1, 0],
                                        'окунь': [0,38, 20, 6, 5, 5, 5, 5, 3, 0, 1, 1, 1, 1, 0],
                                        'плотва': [0, 27, 9, 8, 3, 3, 1, 0, 0, 0, 1, 1, 1, 1, 0],
                                        'щука': [0,0,0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 0],
                                        'сазан': [0, 2, 3, 4, 4, 4, 3, 0, 0, 0, 1, 1, 1, 1, 0],
                                        'карась': [0, 0, 82, 89, 75, 61, 46, 20, 10, 0, 1, 1, 1, 1, 0]})



if __name__ == '__main__':
    print(samarkand_catch_2019.shape)
    print(samarkand_catch_2019.columns)
    print(samarkand_catch_2019[['Date', 'Year']])