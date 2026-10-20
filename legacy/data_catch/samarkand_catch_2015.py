import pandas as pd

# === ДАННЫЕ ВОДОЕМА SAMARKAND ЗА 2015 ГОД ===

data_2015_1 = pd.DataFrame.from_dict({
                'Date': ['01.07.2015'],
                 'Place': ['Самаркандское вдхр.'],
                 'Instrument': ['Сети 20 -80мм'],
                 'Instrument_size': [100],
                'Area': [0.0],
                 'лещ': [58],
                 'судак': [9],
                 'окунь': [2],
                 'плотва': [9],
                 'щука': [1],
                 'сазан': [1],
                 'карась': [49] })
data_2015_1.insert(loc=4, column='CatchType', value='научный')
data_2015_1.loc[data_2015_1['Instrument'].str.contains('ево', na=False), 'Instrument'] = 'невод'
data_2015_1.loc[data_2015_1['Instrument'].str.contains('ет', na=False), 'Instrument'] = 'сеть'
data_2015_1.insert(loc=1, column='Year', value=2015)

 #промысловый улов
# общий улов в 2015 году
samarkand_catch_2015 = pd.concat([data_2015_1], ignore_index=True)

# Количество рыб, подвергнутых биологической обработке по возрастам
qty_treated_fish_2015 = pd.DataFrame.from_dict({
    'LessAge': ['less_2', 'less_3', 'less_4', 'less_5', 'less_6', 'less_7',
                'less_8', 'less_9', 'less_10', 'less_11', 'less_12', 'less_13',
                'less_14', 'less_15', 'less_16'],
'age': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
     'лещ': [ 0, 24, 14, 11, 5, 2, 1, 1, 0, 0, 1, 0, 0, 0, 0],
     'судак': [ 0, 0, 1, 1, 3, 2, 1, 0, 1, 0, 1, 0, 0, 0, 0],
     'окунь': [ 0, 1, 1, 0, 1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0],
     'плотва': [ 0, 2, 2, 2, 1, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0],
     'щука': [ 2, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
     'сазан': [0, 1, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0],
     'карась': [ 0, 0, 9, 11, 8, 5, 6, 5, 6, 0, 1, 0, 0, 0, 0],})
if __name__ == '__main__':
    print(samarkand_catch_2015.shape)
    print(samarkand_catch_2015.columns)
    print(samarkand_catch_2015[['Date', 'Year']])