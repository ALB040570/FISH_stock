import pandas as pd

# === ДАННЫЕ ВОДОЕМА SAMARKAND ЗА 2016 ГОД ===

data_2016_1 = pd.DataFrame.from_dict({
                                    'Date': ['01.07.2016'],
                                     'Place': ['Самаркандское вдхр.'],
                                     'Instrument': ['Сети 20 -80мм'],
                                     'Instrument_size': [50],
                                    'Area': [0.0],
                                     'лещ': [53],
                                     'судак': [10],
                                     'окунь': [3],
                                     'плотва': [10],
                                     'щука': [1],
                                     'сазан': [1],
                                     'карась': [57] })

data_2016_1.insert(loc=4, column='CatchType', value='научный')
data_2016_1.loc[data_2016_1['Instrument'].str.contains('ево', na=False), 'Instrument'] = 'невод'
data_2016_1.loc[data_2016_1['Instrument'].str.contains('ет', na=False), 'Instrument'] = 'сеть'
data_2016_1.insert(loc=1, column='Year', value=2016)

 #промысловый улов
# общий улов в 2016 году
samarkand_catch_2016 = pd.concat([data_2016_1], ignore_index=True)

# Количество рыб, подвергнутых биологической обработке по возрастам
qty_treated_fish_2016 = pd.DataFrame.from_dict({
    'LessAge': ['less_2', 'less_3', 'less_4', 'less_5',
            'less_6', 'less_7', 'less_8', 'less_9', 'less_10',
            'less_11', 'less_12', 'less_13', 'less_14', 'less_15', 'less_16'],
'age': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
             'лещ': [0, 23, 13, 9, 4, 2, 1, 1, 0, 0, 1, 1, 1, 0, 0],
             'судак': [0, 0, 1, 2, 3, 2, 1, 1, 0, 0, 1, 1, 1, 0, 0],
             'окунь': [ 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0],
             'плотва': [0, 3, 2, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0],
             'щука': [ 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0],
             'сазан': [0, 1, 1, 0, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0],
             'карась': [0, 0, 10, 11, 11, 8, 11, 3, 3, 0, 1, 1, 1, 0, 0]})


if __name__ == '__main__':
    print(samarkand_catch_2016.shape)
    print(samarkand_catch_2016.columns)
    print(samarkand_catch_2016[['Date', 'Year']])