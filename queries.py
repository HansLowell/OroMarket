import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from flask_apscheduler import APScheduler
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required
import datetime
from apiCalls import updateMarketDatabase, updateItemDatabase
import pymongo as pym
from pymongo import MongoClient
import re
import numpy as np
import pandas as pd
from ast import literal_eval

def groupUniqueItemsIn(data_frame):
        groupedItems = data_frame.copy()

        del groupedItems['owner']
        del groupedItems['map']
        del groupedItems['x']
        del groupedItems['y']
        del groupedItems['creation_date']
        del groupedItems['price']
        del groupedItems['name']
        del groupedItems['char_id']
        del groupedItems['_id']
        del groupedItems['index']

        # array en String pour faire un groupby.
        groupedItems = groupedItems.assign(cards=lambda d: d['cards'].astype(str))

        groupedItems.reset_index(drop=True)
        groupedItems = groupedItems.fillna(-1).groupby(by=['item_id', 'refine', 'cards', 'star_crumbs',
                                                             'element', 'beloved', 'ranked'], as_index=False)['amount'].sum()
        groupedItems['group'] = True
        return groupedItems

def priceFilterApplier(PFrame, price, minmax):
    if minmax == "min":
        min_price = int(price)
        minPriceFilter = PFrame['price'] > min_price
        PFrame = PFrame.loc[minPriceFilter]
    else:
        max_price = int(price)
        maxPriceFilter = PFrame['price'] < max_price
        PFrame = PFrame.loc[maxPriceFilter]
    return PFrame

def dataFiltering(finalDF, VendingitemsData, queryRequest):

    excludeSlotted = queryRequest['excludeSlotted']
    refine = queryRequest['refine']
    min_price = queryRequest['min_price']
    max_price = queryRequest['max_price']
    element = queryRequest['element']
    star_crumb = queryRequest['star_crumb']
    ranked = queryRequest['ranked']

    if excludeSlotted == True:
        finalDF = finalDF[finalDF.cards.map(len) == 2]

    if ranked == True:
        rankedFilter = finalDF['ranked'] == True
        finalDF = finalDF.loc[rankedFilter]
    

    if refine == "None":
        refineFilter = finalDF['refine'] == -1
        finalDF = finalDF.loc[refineFilter]
    elif refine == "":
        pass
    elif refine == " ":
        pass
    else:
        filternumber = int(refine[-2:])
        refineFilter = finalDF['refine'] == filternumber
        finalDF = finalDF.loc[refineFilter]

        
    if min_price != "":
        VendingitemsData = priceFilterApplier(VendingitemsData, min_price, "min")
        
    if max_price != "":
        VendingitemsData = priceFilterApplier(VendingitemsData, max_price, "max")

    if element != "":
        elementFilter = finalDF['element'] == element
        finalDF = finalDF.loc[elementFilter]

    if star_crumb != "":
        star_crumb = int(star_crumb)
        starFilter = finalDF['star_crumbs'] == star_crumb
        finalDF = finalDF.loc[starFilter]
    
    del VendingitemsData['_id']
    del VendingitemsData['index']

    VendingitemsData['cards'] = VendingitemsData['cards'].astype(str)
    VendingitemsData['refine']= VendingitemsData['refine'].astype(int)
    VendingitemsData['star_crumbs']= VendingitemsData['star_crumbs'].astype(int)
    VendingitemsData['x']= VendingitemsData['x'].astype(int)
    VendingitemsData['y']= VendingitemsData['y'].astype(int)
    VendingitemsData['price'] = VendingitemsData['price'].astype(int)

    VendingitemsData.sort_values(by=['price'], ascending=True, inplace=True)

    VendingitemsData['price'] = VendingitemsData['price'].astype(str)
    VendingitemsData['price'] = VendingitemsData['price'].apply(lambda x: re.sub(r'(?<!^)(?=(\d{3})+$)', r'.', x))

    finalDF['cards'] = finalDF['cards'].astype(str)
    finalDF['refine']= finalDF['refine'].astype(int)
    finalDF['star_crumbs']= finalDF['star_crumbs'].astype(int)
    
    return finalDF, VendingitemsData

def AddWebDisplay_To_With_AndVendingData_AndRequest(db, display, data_frame, VendingitemsData, queryRequest):

    itemCollection = db['item_database']
    iconsCollection = db['icons']
    available_items = db['available_items']

    liste = data_frame.to_dict('records')
    for ite in liste:
        icon = {}
        iteminfo = {}
        # add icon
        query = {"item_id": ite['item_id']}
        icData = iconsCollection.find(query)
        itData = itemCollection.find(query)
        for icons in icData:
            icon = icons['icon']
        # add item info
        for data in itData:
            iteminfo = data

        sales = []

            # find all of those item in sale.
        salesItemsFilter = ((VendingitemsData['item_id'] == ite['item_id']) & (VendingitemsData['refine'] == ite['refine']) & (VendingitemsData['cards'] == ite['cards']) & (VendingitemsData['star_crumbs'] == ite['star_crumbs']) & (VendingitemsData['element'] == ite['element']) & (VendingitemsData['beloved'] == ite['beloved']) & (VendingitemsData['ranked'] == ite['ranked']))
        salesItems = VendingitemsData.loc[salesItemsFilter]
        items = salesItems.to_dict('records')
        for item in items:
            sales.append(item)
            
        cards = literal_eval(ite['cards'])
        cardnb = []
        for card in cards:
            query = {"item_id": card}
            cardCursor = itemCollection.find(query)
            for data in cardCursor:
                cardnb.append(data)

        insertedcard = False
        if len(cardnb) > 0:
            insertedcard = True

        dictonary = {'icon':icon, 'raw_data': ite, 'data': iteminfo, 'sales':sales, 'cards': cardnb, 'insertedcard': insertedcard}
        display.append(dictonary)

        if iteminfo['type'] == 'IT_CARD' and queryRequest['excludeSlotted'] == False:
            newQuery = {"cards":{"$elemMatch":{"$eq":ite['item_id']}}}
            nCursor = available_items.find(newQuery)
            cardList = list(nCursor)
            if len(cardList) > 0:
                cardPD = pd.DataFrame(cardList)
                groupedCardPD = groupUniqueItemsIn(cardPD)
                groupedCardPD, cardPD = dataFiltering(groupedCardPD, cardPD, queryRequest)
                AddWebDisplay_To_With_AndVendingData_AndRequest(db, display, groupedCardPD, cardPD, queryRequest)