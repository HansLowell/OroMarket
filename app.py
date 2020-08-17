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
import queries



# Configure application
app = Flask(__name__)
scheduler = APScheduler()
scheduler.init_app(app)
_host = 'mongo_db'
_host2 = 'localhost'
myclient = MongoClient(host=_host2, port=27017)
db = myclient['origin_db']

updateItemDatabase(db)
updateMarketDatabase(db)

#Disabled for now.
scheduler.start()

def update_Market_database(params):
    updateMarketDatabase(params)

#def update_item_database():
#    print("updateItemDatabase call")

scheduler.add_job(id = "updateMarket", func=update_Market_database, args=[db] ,trigger='interval', seconds=30)
#scheduler.add_job(id = "update item db", func=update_item_database, trigger='interval', minutes=720)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "GET":
        return render_template("search.html")
        
    else:
        itemID_Name = request.form.get("item")
        if not itemID_Name:
            return apology("you must enter an item name or ID")

        # Setting up database collection
        itemCollection = db['item_database']
        available_items = db['available_items']

        query = {}
        # querying mongoDB

        # if item ID is provided, make a query to check id
        if itemID_Name.isnumeric():
            itemID = int(itemID_Name)
            query = {"item_id":itemID}
        else:
            # if keyword is provided make a query for keywords
            nameCaseInsentitive = re.compile(itemID_Name, re.IGNORECASE) 
            query = {"$or": [{"unique_name":{'$regex':nameCaseInsentitive}}, {"name":{'$regex':nameCaseInsentitive}}]}
        
        # apply query.
        cursor = itemCollection.find(query).limit(15)

        # convert pymongo cursor to list of dictionary
        info_list = list(cursor)

        # convert list of dict to panda dataframe
        itemsInfo = pd.DataFrame(info_list)
        
        # get all ids if items from results.
        ids = itemsInfo['item_id'].tolist()

        # make another query to get all items with those ids.
        items_query = {"item_id": {"$in": ids}}
        cursor_items = available_items.find(items_query)

        list_dictionary = list(cursor_items)
        # get another dataframe with all availbles items with those ids.
        VendingitemsData = pd.DataFrame(list_dictionary)

        # make a groupedItems dataframe to get only unique items.
        groupedItems = queries.groupUniqueItemsIn(VendingitemsData)

        # Conditions:

        excludeSlotted = request.form.get("excludeSlotted")
        if excludeSlotted == "on":
            excludeSlotted = True
        else:
            excludeSlotted = False
        refine = request.form.get("refine")
        min_price = request.form.get("min_price")
        max_price = request.form.get("max_price")
        star_crumb = request.form.get("starcrumb")
        ranked = request.form.get("ranked")
        if ranked == "on":
            ranked = True
        else:
            ranked = False
        element = request.form.get("element")

        queryRequest = {"item_id":itemID_Name, "refine":refine, "excludeSlotted":excludeSlotted, "min_price":min_price, "max_price":max_price, "star_crumb": star_crumb, 
            "ranked": ranked, "element":element}
        
        finalDF = groupedItems
        finalDF, VendingitemsData = queries.dataFiltering(finalDF, VendingitemsData, queryRequest)

        # il reste a faire attention pour les recherche de cartes, il y a encore un truc a faire avec ça
        
        display = []
        queries.AddWebDisplay_To_With_AndVendingData_AndRequest(db, display, finalDF, VendingitemsData, queryRequest)

        cardicon = """data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYBAMAAAASWSDLAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAKlBMVEX/AP8PDw/rv2tASE58h437/8fz55/M2d6zwMXY5evTm0uapqxeZ23///+rtZ3OAAAAAXRSTlMAQObYZgAAAAFiS0dEDfa0YfUAAAAJcEhZcwAAC0AAAAtAARsW6NYAAAAHdElNRQfkAg4MBCsa1BJHAAAAXklEQVQY02NgoDpgROYICSJJKDsheKJuJaEwHmNEWiacJ+SWVl7REiQI0eE5vbyiw3mVAFhGu728o8NnIUSPaPSOjo5TAlATRGN27wmEWySk7CWAsFZqIbLrBBioAQAFVRPBKyWiMQAAACV0RVh0ZGF0ZTpjcmVhdGUAMjAyMC0wMi0xNFQxMjowNDo0MyswMDowMGqlB+cAAAAldEVYdGRhdGU6bW9kaWZ5ADIwMjAtMDItMTRUMTI6MDQ6NDMrMDA6MDAb+L9bAAAAAElFTkSuQmCC"""
        
        return render_template("search.html", display=display, cardicon=cardicon, queryRequest=queryRequest)

    
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    session.clear()
    if request.method == "POST":
        if request.form['submit_button'] == 'register':
            return render_template("register.html")
        username = request.form.get("username")
        password = request.form.get("password")
        if not username:
            error = "You did not provide a username"
            return render_template("login.html", error=error)
        elif not password:
            error = "you did not provide a password"
            return render_template("login.html", error=error)
        
        userdb = db['users']
        username = username.lower()

        count = userdb.find({"username":username}).count()
        if count != 1:
            error = "Incorrect username or password"
            return render_template("login.html", error=error)
        
        userCursor = userdb.find({"username":username})
        userDict = list(userCursor)
        userDict = userDict[0]
        if not check_password_hash(userDict['password'], password):
            error = "Incorrect username or password"
            return render_template("login.html", error=error)
        
        session['username'] = userDict['username']
        session['data'] = userDict
        message = "Sucessfully logged in!"
        return render_template("index.html", message=message)

    else:
        return render_template("login.html")

@app.route("/addNotif", methods=["POST"])
@login_required
def addNotif():
    itemID_Name = request.form.get("item")
    excludeSlotted = request.form.get("excludeSlotted")
    refine = request.form.get("refine")
    min_price = request.form.get("min_price")
    max_price = request.form.get("max_price")
    star_crumb = request.form.get("starcrumb")
    ranked = request.form.get("ranked")
    element = request.form.get("element")
    queryRequest = {"item_id":itemID_Name, "refine":refine, "excludeSlotted":excludeSlotted, "min_price":min_price, "max_price":max_price, "star_crumb": star_crumb, 
            "ranked": ranked, "element":element}
    
    notification_list = session['data']['notification']
    notification_list.append(queryRequest)
    
    message = "this request was added in the notification system!"
    return render_template("search.html", message=message)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        # get the username entered in the form
        username = request.form.get("username")

        # if username was not inputted show back an error
        if not username:
            error = "You did not provide an username"
            return render_template("register.html", error=error)

        username = username.lower()
        # get the password and confirmedpassword, check if there is a value in each and that they match
        password = request.form.get("pwd")
        confirmedPassword = request.form.get("confirmpwd")
        if not password:
            error = "You did not provide a password"
            return render_template("register.html", error=error)

        if password != confirmedPassword:
            error = "Your passwords doesn't match"
            return render_template("register.html", error=error)

        if len(password) < 5:
            error = "Your password must be longer than 5 characters"
            return render_template("register.html", error=error)
        
        if len(username) < 5:
            error = "Your username must be longer than 5 characters"
            return render_template("register.html", error=error)

        email = request.form.get("email")
        if not email:
            error = "You did not provide an email address"
            return render_template("register.html", error=error)

        # Check if the username already exists in the database, if so show back an error.
        userdb = db['users']
        count = userdb.find({"username": username}).count()
        count = int(count)
        if count > 0:
            error = "username already taken"
            return render_template("register.html", error=error)
        
        # generate a hashed password to put in the database for security.
        hashpwd = generate_password_hash(password)
        # insert in DB
        userdata = {"username": username, "password": hashpwd, "email":email, "notification":[], "type": 'user'}
        userdb.insert_one(userdata)
        # show success.

        # améliorer avec le email...
        return render_template("register.html", message="The account was registered!")

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)

# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))