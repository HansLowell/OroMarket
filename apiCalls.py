import os
import json
import operator
import requests
import ast
from datetime import time
import pandas as pd
import numpy as np
from ast import literal_eval
#from pymongo import MongoClient

def updateMarketDatabase(db):
    headers = {'x-api-key':'put API key here'}

#########################################################################################################
# 1 get the ranked creators
#########################################################################################################

    #try:
    #    response = requests.get("https://api.originsro.org/api/v1/fame/list", headers=headers)
    #except response.RequestException:
    #    return None

    #try:
    #    response_data = response.json()
    #except (KeyError, TypeError, ValueError):
    #    return None
    with open('creators.txt', encoding='utf8') as json_file:
        response_data = json.load(json_file)

    rankedBrewers = pd.json_normalize(response_data['brewers'])
    rankedForgers = pd.json_normalize(response_data['forgers'])

#####################################################################################################################
# 2 get all shops data,  
#####################################################################################################################
    #try:
    #    response = requests.get("https://api.originsro.org/api/v1/market/list", headers=headers)
    #except response.RequestException:
    #    return None

    #try:
    #    response_data = response.json()
    #except (KeyError, TypeError, ValueError):
    #    return None

    
    with open('data.json', encoding='utf8') as json_file:
        response_data = json.load(json_file)

    df = pd.json_normalize(response_data['shops'])

#####################################################################################################################
# 3 Getting only vending shops informations.
#####################################################################################################################

    ##############################################################################
    # a) Get merchants informations.
    ##############################################################################
    vendingShopFilter = (df['type'] == 'V')     # ->    Filter: Get Vending Shop
    vendingShop = df.loc[vendingShopFilter]     # ->    Apply: Filter

                                                # Rename # -> problematic "." columns
    vendingShop = vendingShop.rename(columns = 
                                    {"location.map":"map", 
                                    "location.x":"x", 
                                    "location.y": "y"})

    ########################################################################################################
    # b) 1) Get Items informations 
    #    2) Add : merchant informations to Items.
    ########################################################################################################
    vendingItems = pd.DataFrame({'owner': vendingShop['owner'], 
                                'map':vendingShop['map'], 
                                'x':vendingShop['x'], 
                                'y': vendingShop['y'], 
                                'creation_date':vendingShop['creation_date'], 
                                'item':vendingShop['items'].explode()})         # -> Unwind item Array into Rows

    vendingItems['id'] = vendingItems.index                   # -> Keep Ids, for Merge (merchant+items).
    vendingItems2 = pd.json_normalize(vendingItems['item'])   # ->  make NEW : Item Dataframe.

    vendingItems2.sort_values(by=['item_id'],                 # ->  Sort by: ID Ascending.
                            ascending=True, 
                            inplace=True)

    vendingItems2 = vendingItems2
    vendingItems2['ref_id'] = vendingItems2.index             # -> Keep Ids, for Merge.

    vendingItems2.index = vendingItems['id']                  # -> Keep Ids, for Merge.

    vendingItems3 = pd.concat([vendingItems,                  # -> Merge.
                                vendingItems2], 
                                axis=1)
    
    del vendingItems3['item']                                 # -> Remove Extra unused Columns.
    del vendingItems3['id']

    ##########################################################
    # c) Group Items Sales by Primary Key:
    ##########################################################
    vendingItems3['cards'] = vendingItems3['cards'].astype(str) # -> Convert Array To Str, (used: For Groupby) 
                                                                                                        #(**Array is problematic.)

    vendingItems3 = vendingItems3.fillna(-1).groupby(           # -> Group Items by primary key (composed of multiple attributes)
    by=['item_id','owner', 'map', 'x', 'y', 'creation_date', 
    'price', 'refine', 'cards', 'creator', 'star_crumbs', 
    'element', 'beloved'], as_index=False)['amount'].sum()

    ###########################################################
    # d)  Add: Ranked Items informations
    ###########################################################

                                                                # -> Add : Ranked Items Column
    vendingItems3['ranked'] = (vendingItems3['creator'].isin(rankedBrewers['char_id'])|(vendingItems3['creator'].isin(rankedForgers['char_id'])))

    vendingItems3['char_id'] = vendingItems3['creator']         # ->  Change name for char_id, for Merge.
    del vendingItems3['creator']                                # ->  Remove unused column.
   
    rankedFrames = [rankedBrewers, rankedForgers]               # -> Merge both type of ranked players
    rankedPlayers = pd.concat(rankedFrames)                     # -> Apply Merge.

                                                                # -> Add: Name of ranked player, to the items they created.
    vendingItems3 = pd.merge(vendingItems3, rankedPlayers, on=['char_id'], how='outer')

    vendingItems3.dropna(subset=['item_id'], inplace=True)      # -> Remove extra null values caused by outer join.

    del vendingItems3['points']                                 # -> remove unused column

    #sorting Values by item_id
    vendingItems3.sort_values(by=['item_id'], ascending=True, inplace=True)

    vendingItems3['cards'] = vendingItems3['cards'].replace("nan", "[]")    # -> Convert back cards to Array
    vendingItems3['cards'] = vendingItems3['cards'].apply(literal_eval)

##########################################################################################################################
# 4 Getting the buying shops informations 
##########################################################################################################################
    buyingShopFilter = (df['type'] == 'B')
    buyingShop = df.loc[buyingShopFilter]
    buyingShop = buyingShop.rename(columns = {"location.map":"map", "location.x":"x", "location.y": "y"})

    buyingItems = pd.DataFrame({'owner': buyingShop['owner'], 'item':buyingShop['items'].explode()})
    buyingItems['id'] = buyingItems.index
    buyingItems2 = pd.json_normalize(buyingItems['item'])
    buyingItems2.index = buyingItems['id']
    buyingItems3 = pd.concat([buyingItems, buyingItems2], axis=1)
    del buyingItems3['item']
    del buyingItems3['id']
    buyingItems3.sort_values(by=['item_id'], ascending=True, inplace=True)

##########################################################################################################################
# 5 Updating Database
##########################################################################################################################
    db.drop_collection("available_items")
    db.drop_collection("wanted_items")
    db.drop_collection("vending_shops")
    db.drop_collection("buying_shops")
    db.drop_collection("item_references")

    available_items = db['available_items']
    wanted_items = db['wanted_items']
    vending_shops = db['vending_shops']
    buying_shops = db['buying_shops']

    vendingItems3.reset_index(inplace=True)
    vendingItems3 = vendingItems3.to_dict("records")
    available_items.insert_many(vendingItems3)
    
    buyingItems3.reset_index(inplace=True)
    buyingItems3 = buyingItems3.to_dict("records")
    wanted_items.insert_many(buyingItems3)

    buyingShop.reset_index(inplace=True)
    buyingShop = buyingShop.to_dict("records")
    buying_shops.insert_many(buyingShop)

    vendingShop.reset_index(inplace=True)
    vendingShop = vendingShop.to_dict("records")
    vending_shops.insert_many(vendingShop)


# this function get called every 12 hours, it is limited 6 time day but I think it doesn't have to be called
# that often.
def updateItemDatabase(db):

    with open('item_db.json') as f:
        file_data = json.load(f)

    all_items = file_data['items']
    db.drop_collection("item_database")
    collection = db['item_database']
    collection.insert_many(all_items)

    with open('icones.txt') as f:
        file_data = json.load(f)
    
    icons = file_data['icons']
    db.drop_collection('icons')
    collection = db['icons']
    collection.insert_many(icons)
    
if __name__ == "__main__":
    updateMarketDatabase()
    #print(vending_shops)
